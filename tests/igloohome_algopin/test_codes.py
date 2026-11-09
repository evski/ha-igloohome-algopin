"""Door codes and the optional website PIN link. No network and no real token."""

from __future__ import annotations

import json
import logging

import pytest

from custom_components.igloohome_algopin.api import (
    API_ROOT,
    DoorCode,
    IglooPaymentError,
    WebsiteConfigError,
    WebsiteStatusError,
    clean_website_settings,
    parse_pin_links,
)
from custom_components.igloohome_algopin.snapshot import diagnostics_payload, door_codes_markdown

from test_api import PIN, FakeResponse, client_with, token_route

LOCK = "IGB4example"
OTHER = "IGP1example"
WEBSITE = "https://locks.example/api/status"
WEBSITE_TOKEN = "website-token-example"
PIN_LINK = "https://locks.example/pins/example"


def _health_routes():
    return {
        ("POST", "https://auth.igloohome.co/oauth2/token"): token_route(),
        ("GET", f"{API_ROOT}/server-health"): FakeResponse(200, {"status": "active", "endsAt": None}),
        ("GET", f"{API_ROOT}/devices/support-pins"): FakeResponse(
            200,
            {
                "nextCursor": "",
                "payload": [
                    {"deviceId": LOCK, "deviceName": "Front door", "type": "Lock", "linkedDevices": []},
                    {"deviceId": OTHER, "deviceName": "Side door", "type": "Lock", "linkedDevices": []},
                ],
            },
        ),
        ("GET", f"{API_ROOT}/devices"): FakeResponse(200, {"nextCursor": "", "payload": []}),
    }


def test_website_settings_reject_incomplete_values_and_keep_a_saved_token():
    assert clean_website_settings("", "") == ("", "")
    assert clean_website_settings(" https://locks.example/api/status ", " abc ") == (WEBSITE, "abc")
    with pytest.raises(WebsiteConfigError):
        clean_website_settings("https://user:secret@locks.example/status", "abc")
    with pytest.raises(WebsiteConfigError):
        clean_website_settings("ftp://locks.example/status", "abc")
    with pytest.raises(WebsiteConfigError):
        clean_website_settings(WEBSITE, "")
    assert clean_website_settings(WEBSITE, "", saved_token=WEBSITE_TOKEN) == (WEBSITE, WEBSITE_TOKEN)
    assert clean_website_settings("", "", saved_token=WEBSITE_TOKEN) == ("", "")


def test_markdown_lists_pin_digits_and_escapes_table_pipes():
    codes = (
        DoorCode("id-1", "Guest | stay", "1357902", "duration", "2026-07-01T14:00:00+00:00", None),
    )
    markdown = door_codes_markdown(codes)
    assert "1357902" in markdown
    assert "Guest \\| stay" in markdown
    assert "| duration |" in markdown
    assert door_codes_markdown(()) == "No door codes."
    assert "1357902" not in repr(codes[0])


def test_pin_links_accept_a_list_or_a_map_and_drop_non_http_links():
    listed = parse_pin_links(
        {"locks": [{"device_id": LOCK, "pin_link": PIN_LINK}, {"deviceId": OTHER, "url": "javascript:alert(1)"}]}
    )
    assert listed == {LOCK: PIN_LINK}
    mapped = parse_pin_links({"locks": {LOCK: {"pinLink": PIN_LINK}, OTHER: PIN_LINK}})
    assert mapped == {LOCK: PIN_LINK, OTHER: PIN_LINK}
    assert parse_pin_links({"ok": True}) is None
    assert parse_pin_links([]) is None


@pytest.mark.asyncio
async def test_door_codes_follow_the_access_query_and_stay_out_of_diagnostics(caplog):
    caplog.set_level(logging.DEBUG)
    pages = {"n": 0}

    def access(kwargs):
        assert kwargs["params"]["accessType"] == "pin"
        pages["n"] += 1
        if pages["n"] == 1:
            return FakeResponse(
                200,
                {
                    "nextCursor": "page-2",
                    "payload": [
                        {
                            "id": "code-1",
                            "accessType": "pin",
                            "name": "Guest",
                            "pin": PIN,
                            "pinType": "duration",
                            "startDate": "2026-07-01T14:00:00+00:00",
                            "endDate": "2026-07-02T14:00:00+00:00",
                        },
                        {"accessType": "ekey", "name": "Not a pin"},
                    ],
                },
            )
        return FakeResponse(
            200,
            {
                "nextCursor": "",
                "payload": [
                    {
                        "id": "code-2",
                        "name": "Cleaner",
                        "pin": "2468",
                        "pinType": "permanent",
                        "startDateTime": "2026-08-01T00:00:00+00:00",
                        "endDateTime": "2026-08-02T00:00:00+00:00",
                    }
                ],
            },
        )

    routes = _health_routes()
    routes[("GET", f"{API_ROOT}/devices/{LOCK}/access")] = access
    routes[("GET", f"{API_ROOT}/devices/{OTHER}/access")] = FakeResponse(404, {"message": "not found device"})
    client, session = client_with(routes)

    snapshot = await client.fetch_snapshot({LOCK, OTHER})

    lock = next(item for item in snapshot.locks if item.device_id == LOCK)
    assert lock.door_codes_ok is True
    assert [code.pin for code in lock.door_codes] == [PIN, "2468"]
    assert lock.door_codes[0].start == "2026-07-01T14:00:00+00:00"
    assert lock.door_codes[1].pin_type == "permanent"
    other = next(item for item in snapshot.locks if item.device_id == OTHER)
    assert other.door_codes_ok is False
    assert other.door_codes == ()
    access_calls = [call for call in session.calls if call[1].endswith("/access")]
    assert len(access_calls) == 3
    markdown = door_codes_markdown(lock.door_codes)
    assert PIN in markdown
    encoded = json.dumps(diagnostics_payload(snapshot))
    assert PIN not in encoded
    assert "2468" not in encoded
    assert WEBSITE_TOKEN not in encoded
    assert PIN not in caplog.text
    assert "2468" not in caplog.text


@pytest.mark.asyncio
async def test_website_status_uses_its_bearer_token_and_does_not_reauth(caplog):
    caplog.set_level(logging.DEBUG)

    def website(kwargs):
        assert kwargs["headers"]["Authorization"] == f"Bearer {WEBSITE_TOKEN}"
        assert kwargs["headers"]["Accept"] == "application/json"
        return FakeResponse(200, {"locks": [{"device_id": LOCK, "pin_link": PIN_LINK}]})

    routes = _health_routes()
    routes[("GET", f"{API_ROOT}/devices/{LOCK}/access")] = FakeResponse(200, {"nextCursor": "", "payload": []})
    routes[("GET", f"{API_ROOT}/devices/{OTHER}/access")] = FakeResponse(200, {"nextCursor": "", "payload": []})
    routes[("GET", WEBSITE)] = website
    client, _session = client_with(routes)

    snapshot = await client.fetch_snapshot(
        {LOCK, OTHER},
        website_status_url=WEBSITE,
        website_bearer_token=WEBSITE_TOKEN,
    )

    by_id = {lock.device_id: lock for lock in snapshot.locks}
    assert by_id[LOCK].pin_link == PIN_LINK
    assert by_id[LOCK].website_configured is True
    assert by_id[LOCK].website_ok is True
    assert by_id[OTHER].pin_link is None
    assert WEBSITE_TOKEN not in caplog.text
    encoded = json.dumps(diagnostics_payload(snapshot))
    assert WEBSITE_TOKEN not in encoded
    assert PIN_LINK not in encoded
    assert by_id[LOCK].pin_link and "pin_link_present" in encoded


@pytest.mark.asyncio
async def test_website_http_error_marks_the_link_unavailable_without_raising():
    routes = _health_routes()
    routes[("GET", f"{API_ROOT}/devices/{LOCK}/access")] = FakeResponse(200, {"nextCursor": "", "payload": []})
    routes[("GET", f"{API_ROOT}/devices/{OTHER}/access")] = FakeResponse(200, {"nextCursor": "", "payload": []})
    routes[("GET", WEBSITE)] = FakeResponse(401, {"error": "bad token"})
    client, _session = client_with(routes)

    snapshot = await client.fetch_snapshot(
        {LOCK},
        website_status_url=WEBSITE,
        website_bearer_token=WEBSITE_TOKEN,
    )

    assert snapshot.locks[0].website_ok is False
    assert snapshot.locks[0].pin_link is None
    assert snapshot.locks[0].door_codes_ok is True


@pytest.mark.asyncio
async def test_access_payment_error_is_not_swallowed():
    routes = _health_routes()
    routes[("GET", f"{API_ROOT}/devices/{LOCK}/access")] = FakeResponse(402, {"error": "trial ended"})
    client, _session = client_with(routes)
    with pytest.raises(IglooPaymentError):
        await client.fetch_snapshot({LOCK})


@pytest.mark.asyncio
async def test_fetch_pin_links_rejects_a_body_without_locks():
    client, _session = client_with({("GET", WEBSITE): FakeResponse(200, {"status": "ok"})})
    with pytest.raises(WebsiteStatusError):
        await client.fetch_pin_links(WEBSITE, WEBSITE_TOKEN)
