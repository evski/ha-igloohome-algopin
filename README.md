# Igloo AlgoPIN

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Release](https://img.shields.io/github/v/release/evski/ha-igloohome-algopin)](https://github.com/evski/ha-igloohome-algopin/releases)
[![Validate](https://github.com/evski/ha-igloohome-algopin/actions/workflows/validate.yaml/badge.svg)](https://github.com/evski/ha-igloohome-algopin/actions/workflows/validate.yaml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home Assistant custom integration that creates hourly and daily [igloohome AlgoPIN](https://docs.igloohome.co/home/algopin-codes) guest codes, lists the PIN codes currently on each selected lock, and can show a website link for each lock.

The igloohome cloud creates the code. This integration does not run a PIN algorithm locally, and it does not add lock, unlock, or battery entities.

## Igloo individual API

You need an [igloohome individual API](https://docs.igloohome.co/home/individual-account) client that uses client credentials. The client ID and client secret come from that client. This integration calls `https://api.igloohome.co/home` and `https://auth.igloohome.co`. It does not use the iglooworks API.

igloohome documents a 30-day trial and then USD $2 per active lock per month. HTTP 402 means billing rejected the call.

Home Assistant installs the pinned dependency `igloohome-api==0.1.2` from the manifest when the integration is set up. You do not install that package yourself.

## Install

Home Assistant 2025.1 or newer.

### HACS (custom repository)

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=evski&repository=ha-igloohome-algopin&category=integration)

Or: HACS → ⋮ → **Custom repositories** → add `https://github.com/evski/ha-igloohome-algopin` as an **Integration**. Install **Igloo AlgoPIN** and restart Home Assistant.

### Manual

Copy `custom_components/igloohome_algopin` into `/config/custom_components/igloohome_algopin` and restart Home Assistant.

Home Assistant loads `/config/custom_components/igloohome_algopin/manifest.json`.

## Configuration

[![Open your Home Assistant instance and start setting up Igloo AlgoPIN.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=igloohome_algopin)

Or **Settings → Devices & services → Add integration → Igloo AlgoPIN**.

| Step | What to enter |
|---|---|
| Client ID and client secret | The individual API client credentials. |
| Locks | Devices returned by `GET /home/devices/support-pins`. There is no built-in lock. Bridge and Fob devices are not offered, and a prefix the supported-devices table marks AlgoPIN no is not offered. |
| Website status URL | Optional. Leave empty to skip the Website PIN link sensor's request. |
| Website bearer token | Sent as `Authorization: Bearer` when the URL is set. Leave both website fields empty to skip. On the options screen, leave the token blank to keep the saved token. |

The picker stores `deviceId` and `deviceName` only. Battery, pairing time, the internal id, and home id from the device list are not stored. Compare an unfamiliar device id with [Supported devices](https://docs.igloohome.co/home/supported-devices). Prefix IGB4 on that table is Deadbolt 2S Metal Grey, AlgoPIN yes. A retail name is not a device id.

Open **Configure** on the integration to change the selected locks or the website status endpoint.

### Website status endpoint

When a URL and bearer token are set, each refresh sends:

```http
GET <website status URL>
Authorization: Bearer <website bearer token>
Accept: application/json
```

The body that sets a link is:

```json
{
  "locks": [
    {
      "device_id": "IGB4example",
      "pin_link": "https://locks.example/pins/example"
    }
  ]
}
```

`device_id` is the igloohome device id of a lock you selected. `pin_link` must be an `http` or `https` URL. A `locks` object keyed by device id is also accepted. Locks missing from the body have an unknown Website PIN link. A failed request makes that sensor unavailable and does not mark the igloohome login as expired.

The URL is whatever status endpoint you run. Nothing in this integration hardcodes a site, a token, or a device id.

## Entities

Each selected lock gets these sensors. They refresh every 30 minutes, and again after a create or revoke service succeeds.

| Sensor | Entity | State | Details |
|---|---|---|---|
| Website PIN link | `sensor.<lock>_website_pin_link` | PIN link URL | From the website status endpoint. Unknown when that lock has no link. |
| Door codes | `sensor.<lock>_door_codes` | Number of PIN codes | Attribute `markdown` is a table of name, PIN, type, start, and end. |
| API access ends | `sensor.<lock>_api_access_ends` | Timestamp | `endsAt` from `GET /home/server-health`. The same account value is shown on each selected lock. |

Door codes come from `GET /home/devices/{deviceId}/access?accessType=pin`. The `markdown` attribute contains the PIN digits so a dashboard can print `{{ state_attr('sensor.front_door_door_codes', 'markdown') }}`. That attribute is left out of recorded history. The count in the state is recorded. Treat the live attribute as secret.

There is no API status sensor.

## Services

The create services return the new PIN only in the service response (`SupportsResponse.ONLY`). The integration does not write that response to its own store, the logbook, or an event. Home Assistant still keeps the response in the trace of the script or automation that called the service. The door codes sensor can list the same PIN later, once the access API returns it.

| Service | What it does | Response |
|---|---|---|
| `igloohome_algopin.create_hourly_algopin` | `POST /home/devices/{deviceId}/algopin/hourly`. No Bridge is used. | `pin`, `pin_id` |
| `igloohome_algopin.create_daily_algopin` | `POST /home/devices/{deviceId}/algopin/daily`. No Bridge is used. | `pin`, `pin_id` |
| `igloohome_algopin.revoke_algopin` | Asks a linked Bridge to delete a PIN (job type 5, `jobData.pin`, 4 to 9 digits). | `job_id`, `completed`, `job_status` |

Enter start and end in the Home Assistant timezone. They are converted to UTC and sent as `YYYY-MM-DDTHH:00:00+00:00`. A time that is not on a UTC hour is rejected rather than rounded.

Hourly duration is 1 to 672 hours, and the start may be at most 1 hour in the past. Daily duration is 29 to 367 whole UTC days, and the UTC hour of the start and the end must match. Variance is 1, 2, or 3.

Revoke needs a Bridge id that the latest device list linked to the lock. Pass `bridge_id` when more than one Bridge is linked. HTTP 406 means the Bridge is offline or the lock is not linked, and the code stays on the lock. A job id does not mean the lock deleted the code. The published 256-hour deletion limit is not applied here, because create responses are not stored.

`device_id` on each service accepts the Home Assistant device of a lock chosen during setup.

## Releasing

Create the GitHub release after the Validate workflow on that commit has succeeded.

1. Set `version` in `custom_components/igloohome_algopin/manifest.json` and `VERSION` in `const.py` to the new version, and add that version to `CHANGELOG.md`.
2. Merge the change to `main`.
3. Wait until the Validate workflow on that commit succeeds. The hassfest job, the HACS job, and the tests job all have to pass. `.github/workflows/validate.yaml` does not set `ignore`.
4. Create a GitHub release of that commit. Name it `v` plus the manifest version (for example `v0.1.1`) and target `main`.

## License

[MIT](LICENSE)
