# Changelog

## 0.1.1

First standalone release.

- Sensors on each selected lock: Website PIN link, Door codes, and API access ends.
- Website PIN link reads an optional website REST status endpoint with a bearer token.
- Door codes lists PINs from `GET /home/devices/{deviceId}/access?accessType=pin` and puts that list in a `markdown` attribute.
- Services: `create_hourly_algopin`, `create_daily_algopin`, and `revoke_algopin`.
- Requires an igloohome individual API client. Home Assistant installs `igloohome-api==0.1.2` from the manifest.
