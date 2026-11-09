"""Config flow. Locks come from GET /home/devices/support-pins. No built-in lock."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import (
    Device,
    IglooApiError,
    IglooAuthError,
    IglooClient,
    IglooConnectionError,
    IglooError,
    IglooPaymentError,
    WebsiteConfigError,
    clean_website_settings,
)
from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_LOCKS,
    CONF_WEBSITE_STATUS_URL,
    CONF_WEBSITE_TOKEN,
    DOMAIN,
)
from .models import device_label, is_offered

_LOGGER = logging.getLogger(__name__)


def _password() -> TextSelector:
    return TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _client(hass, client_id: str, client_secret: str) -> IglooClient:
    return IglooClient(async_get_clientsession(hass), client_id, client_secret)


def _selectable(devices: list[Device]) -> list[Device]:
    """Devices the support-pins payload still allows the user to choose."""

    return [device for device in devices if is_offered(device.device_id, device.device_type)]


def _lock_schema(
    devices: list[Device],
    default: list[str] | None = None,
    website_url: str | None = None,
) -> vol.Schema:
    options = {
        device.device_id: device_label(device.device_name, device.device_id, device.device_type)
        for device in devices
    }
    key = vol.Required(CONF_LOCKS, default=default) if default else vol.Required(CONF_LOCKS)
    fields: dict = {key: cv.multi_select(options)}
    if website_url is not None:
        fields[vol.Optional(CONF_WEBSITE_STATUS_URL, default=website_url)] = cv.string
        fields[vol.Optional(CONF_WEBSITE_TOKEN, default="")] = _password()
    return vol.Schema(fields)


def _website_options(url: object, token: object, entry_options: dict) -> tuple[str, str]:
    saved_token = entry_options.get(CONF_WEBSITE_TOKEN, "")
    return clean_website_settings(
        str(url or ""),
        str(token or ""),
        saved_token=saved_token if isinstance(saved_token, str) else "",
    )


def _error_key(err: IglooError) -> str:
    if isinstance(err, IglooAuthError):
        return "invalid_auth"
    if isinstance(err, IglooPaymentError):
        return "payment_required"
    if isinstance(err, IglooConnectionError):
        return "cannot_connect"
    return "unknown"


class IglooConfigFlow(ConfigFlow, domain=DOMAIN):
    """Client credentials, then a multi-select of locks the API returned."""

    VERSION = 1

    def __init__(self) -> None:
        self._client_id = ""
        self._client_secret = ""
        self._devices: list[Device] = []
        self._selected: list[Device] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: dict[str, str] = {}
        if user_input is not None:
            client_id = str(user_input[CONF_CLIENT_ID]).strip()
            client_secret = str(user_input[CONF_CLIENT_SECRET])
            try:
                devices = await _client(self.hass, client_id, client_secret).list_algopin_devices()
            except IglooError as err:
                _LOGGER.debug("igloohome setup failed: %s", err)
                errors["base"] = _error_key(err)
            else:
                selectable = _selectable(devices)
                if not selectable:
                    errors["base"] = "no_devices"
                else:
                    await self.async_set_unique_id(client_id)
                    self._abort_if_unique_id_configured()
                    self._client_id = client_id
                    self._client_secret = client_secret
                    self._devices = selectable
                    return await self.async_step_locks()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): cv.string,
                    vol.Required(CONF_CLIENT_SECRET): _password(),
                }
            ),
            errors=errors,
        )

    async def async_step_locks(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: dict[str, str] = {}
        if user_input is not None:
            requested = set(user_input.get(CONF_LOCKS) or [])
            known = {device.device_id: device for device in self._devices}
            if not requested or not requested <= set(known):
                errors["base"] = "select_lock" if requested <= set(known) else "unknown"
            else:
                self._selected = [known[device_id] for device_id in requested]
                return await self.async_step_website()
        return self.async_show_form(
            step_id="locks",
            data_schema=_lock_schema(self._devices),
            errors=errors,
        )

    async def async_step_website(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                url, token = clean_website_settings(
                    str(user_input.get(CONF_WEBSITE_STATUS_URL, "")),
                    str(user_input.get(CONF_WEBSITE_TOKEN, "")),
                )
            except WebsiteConfigError:
                errors["base"] = "invalid_website"
            else:
                selected = self._selected
                title = selected[0].device_name if len(selected) == 1 else "Igloo AlgoPIN"
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_CLIENT_ID: self._client_id,
                        CONF_CLIENT_SECRET: self._client_secret,
                    },
                    options={
                        CONF_LOCKS: [
                            {"device_id": device.device_id, "device_name": device.device_name}
                            for device in selected
                        ],
                        CONF_WEBSITE_STATUS_URL: url,
                        CONF_WEBSITE_TOKEN: token,
                    },
                )
        return self.async_show_form(
            step_id="website",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_WEBSITE_STATUS_URL, default=""): cv.string,
                    vol.Optional(CONF_WEBSITE_TOKEN, default=""): _password(),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> dict[str, Any]:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await _client(
                    self.hass,
                    entry.data[CONF_CLIENT_ID],
                    user_input[CONF_CLIENT_SECRET],
                ).server_health()
            except IglooError as err:
                errors["base"] = _error_key(err)
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_CLIENT_SECRET: user_input[CONF_CLIENT_SECRET]},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_CLIENT_SECRET): _password()}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> IglooOptionsFlow:
        return IglooOptionsFlow()


class IglooOptionsFlow(OptionsFlow):
    """Replace the chosen locks with a fresh account list."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: dict[str, str] = {}
        entry = self.config_entry
        try:
            devices = _selectable(
                await _client(
                    self.hass,
                    entry.data[CONF_CLIENT_ID],
                    entry.data[CONF_CLIENT_SECRET],
                ).list_algopin_devices()
            )
        except IglooAuthError as err:
            _LOGGER.debug("igloohome options refresh failed: %s", err)
            errors["base"] = "invalid_auth"
            devices = []
        except IglooPaymentError as err:
            _LOGGER.debug("igloohome options refresh failed: %s", err)
            errors["base"] = "payment_required"
            devices = []
        except IglooConnectionError as err:
            _LOGGER.debug("igloohome options refresh failed: %s", err)
            errors["base"] = "cannot_connect"
            devices = []
        except IglooApiError as err:
            _LOGGER.debug("igloohome options refresh failed: %s", err)
            errors["base"] = "unknown"
            devices = []

        if user_input is not None and not errors:
            requested = set(user_input.get(CONF_LOCKS) or [])
            known = {device.device_id: device for device in devices}
            if not requested or not requested <= set(known):
                errors["base"] = "select_lock" if requested <= set(known) else "unknown"
            else:
                try:
                    url, token = _website_options(
                        user_input.get(CONF_WEBSITE_STATUS_URL, ""),
                        user_input.get(CONF_WEBSITE_TOKEN, ""),
                        dict(entry.options),
                    )
                except WebsiteConfigError:
                    errors["base"] = "invalid_website"
                else:
                    selected = [known[device_id] for device_id in requested]
                    return self.async_create_entry(
                        title="",
                        data={
                            CONF_LOCKS: [
                                {"device_id": device.device_id, "device_name": device.device_name}
                                for device in selected
                            ],
                            CONF_WEBSITE_STATUS_URL: url,
                            CONF_WEBSITE_TOKEN: token,
                        },
                    )

        if not devices and not errors:
            return self.async_abort(reason="no_devices")
        if not devices:
            return self.async_show_form(step_id="init", data_schema=vol.Schema({}), errors=errors)

        current = [
            item["device_id"]
            for item in entry.options.get(CONF_LOCKS, [])
            if isinstance(item, dict) and item.get("device_id") in {device.device_id for device in devices}
        ]
        saved_url = entry.options.get(CONF_WEBSITE_STATUS_URL, "")
        return self.async_show_form(
            step_id="init",
            data_schema=_lock_schema(
                devices,
                current or None,
                website_url=saved_url if isinstance(saved_url, str) else "",
            ),
            errors=errors,
        )
