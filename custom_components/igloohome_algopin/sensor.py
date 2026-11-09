"""Sensors for each selected lock.

Website PIN link is a URL from the configured website status endpoint.
Door codes exposes a count plus a ``markdown`` attribute that lists PIN
digits returned by the access API. API access ends is the account
``endsAt`` timestamp. There is no API status sensor.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRAND, DOMAIN, VERSION
from .coordinator import IglooCoordinator
from .snapshot import AccountSnapshot, LockView, door_codes_markdown, entity_locks

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="website_pin_link",
        translation_key="website_pin_link",
        icon="mdi:link-variant",
    ),
    SensorEntityDescription(
        key="door_codes",
        translation_key="door_codes",
        icon="mdi:dialpad",
    ),
    SensorEntityDescription(
        key="api_access_ends",
        translation_key="api_access_ends",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-end",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: IglooCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    locks = entity_locks(coordinator.data) if coordinator.data is not None else ()
    async_add_entities(
        IglooLockSensor(coordinator, entry, description, lock)
        for lock in locks
        for description in SENSORS
    )


class IglooLockSensor(CoordinatorEntity[IglooCoordinator], SensorEntity):
    """One value for a selected lock."""

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({"markdown"})

    def __init__(
        self,
        coordinator: IglooCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
        lock: LockView,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = lock.device_id
        self._attr_unique_id = f"{entry.entry_id}-{lock.device_id}-{description.key}"
        if lock.device_name == lock.device_id:
            device_name = lock.device_id
        else:
            device_name = f"{lock.device_name} ({lock.device_id})"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, lock.device_id)},
            manufacturer=BRAND,
            name=device_name,
            sw_version=VERSION,
        )

    def _lock(self) -> LockView | None:
        data: AccountSnapshot | None = self.coordinator.data
        if data is None:
            return None
        return next((item for item in data.locks if item.device_id == self._device_id), None)

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        lock = self._lock()
        if lock is None:
            return False
        key = self.entity_description.key
        if key == "door_codes":
            return lock.door_codes_ok
        if key == "website_pin_link":
            return lock.website_ok
        return True

    @property
    def native_value(self):
        data: AccountSnapshot = self.coordinator.data
        lock = self._lock()
        key = self.entity_description.key
        if key == "api_access_ends":
            return data.ends_at
        if lock is None:
            return None
        if key == "door_codes":
            if not lock.door_codes_ok:
                return None
            return len(lock.door_codes)
        if key == "website_pin_link":
            return lock.pin_link
        return None

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        if self.entity_description.key != "door_codes":
            return None
        lock = self._lock()
        if lock is None or not lock.door_codes_ok:
            return None
        return {"markdown": door_codes_markdown(lock.door_codes)}
