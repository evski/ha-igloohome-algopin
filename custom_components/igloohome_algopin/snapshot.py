"""Account snapshot shown in Home Assistant.

Create and revoke service responses are not stored here. Door-code digits
listed by the access API are kept on the lock so the door codes sensor can
show them, and ``DoorCode`` hides those digits in ``repr``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from .models import is_offered

_DEVICE_ID = re.compile(r"^[A-Za-z0-9]{4,32}$")


def parse_chosen(options: dict) -> tuple[tuple[str, str], ...]:
    """Lock ids saved from a setup GET. Accepts ``{device_id, device_name}`` or a bare id."""

    raw = options.get("locks") or []
    if not isinstance(raw, list):
        return ()
    chosen: list[tuple[str, str]] = []
    for item in raw:
        if isinstance(item, str) and _DEVICE_ID.fullmatch(item):
            chosen.append((item, item))
            continue
        if not isinstance(item, dict):
            continue
        device_id = item.get("device_id")
        if not isinstance(device_id, str) or not _DEVICE_ID.fullmatch(device_id):
            continue
        name = item.get("device_name")
        chosen.append((device_id, name.strip() if isinstance(name, str) and name.strip() else device_id))
    return tuple(chosen)


@dataclass(frozen=True)
class DoorCode:
    """One PIN row from GET /home/devices/{deviceId}/access?accessType=pin."""

    code_id: str
    name: str
    pin: str
    pin_type: str
    start: str | None
    end: str | None

    def __repr__(self) -> str:
        return (
            f"DoorCode(code_id={self.code_id!r}, name={self.name!r}, "
            f"pin='[redacted]', pin_type={self.pin_type!r})"
        )


@dataclass(frozen=True)
class LockView:
    """A lock the user chose from a real device list."""

    device_id: str
    device_name: str
    device_type: str
    table_prefix: str | None
    bridge_ids: tuple[str, ...]
    door_codes: tuple[DoorCode, ...] = ()
    door_codes_ok: bool = False
    pin_link: str | None = None
    website_configured: bool = False
    website_ok: bool = True


@dataclass(frozen=True)
class AccountSnapshot:
    """Billing status and chosen locks. No credentials."""

    status: str
    ends_at: datetime | None
    tier: str | None
    locks: tuple[LockView, ...]
    devices_fresh: bool


def entity_locks(snapshot: AccountSnapshot) -> tuple[LockView, ...]:
    """Selected locks that may receive a device and sensors.

    The snapshot already keeps only ids the user chose that support-pins
    still returns. This drops anything the prefix table or ``type`` denies,
    so a Bridge, a Fob, or an AlgoPIN-no prefix never becomes an entity.
    """

    return tuple(lock for lock in snapshot.locks if is_offered(lock.device_id, lock.device_type))


def _md_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def door_codes_markdown(codes: tuple[DoorCode, ...]) -> str:
    """Markdown table of door codes, including PIN digits, for the sensor attribute."""

    if not codes:
        return "No door codes."
    lines = [
        "| Name | PIN | Type | Start | End |",
        "| --- | --- | --- | --- | --- |",
    ]
    for code in codes:
        lines.append(
            "| "
            + " | ".join(
                (
                    _md_cell(code.name or "-"),
                    _md_cell(code.pin),
                    _md_cell(code.pin_type or "-"),
                    _md_cell(code.start or "-"),
                    _md_cell(code.end or "-"),
                )
            )
            + " |"
        )
    return "\n".join(lines)


def diagnostics_payload(snapshot: AccountSnapshot) -> dict:
    """Diagnostics fields that are safe to download.

    PIN digits, the website bearer token, and PIN links are omitted. A link
    can be a secret URL, and the door-code table is already on the entity.
    """

    return {
        "status": snapshot.status,
        "ends_at": snapshot.ends_at.isoformat() if snapshot.ends_at else None,
        "tier": snapshot.tier,
        "devices_fresh": snapshot.devices_fresh,
        "locks": [
            {
                "device_id": lock.device_id,
                "device_name": lock.device_name,
                "device_type": lock.device_type,
                "table_prefix": lock.table_prefix,
                "bridge_ids": list(lock.bridge_ids),
                "door_code_count": len(lock.door_codes) if lock.door_codes_ok else None,
                "website_configured": lock.website_configured,
                "pin_link_present": bool(lock.pin_link),
            }
            for lock in entity_locks(snapshot)
        ],
    }
