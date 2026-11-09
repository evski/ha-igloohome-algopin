"""Constants for the Igloo AlgoPIN integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "igloohome_algopin"
BRAND = "igloohome"
VERSION = "0.1.1"

# Home Assistant core pins igloohome-api==0.1.1 for the built-in igloohome
# integration. A custom integration cannot pin ==0.1.2 in the same environment.
# 0.1.2 only adds lastSync datetime parsing, which this integration does not
# use. Auth.request and the AlgoPIN scopes are already on 0.1.1. See api.py.
IGLOOHOME_API_REQUIREMENT = "igloohome-api>=0.1.1"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_LOCKS = "locks"
CONF_DEVICE_ID = "device_id"
CONF_ACCESS_NAME = "access_name"
CONF_START = "start"
CONF_END = "end"
CONF_VARIANCE = "variance"
CONF_BRIDGE_ID = "bridge_id"
CONF_PIN = "pin"
CONF_WEBSITE_STATUS_URL = "website_status_url"
CONF_WEBSITE_TOKEN = "website_bearer_token"

SERVICE_CREATE_HOURLY = "create_hourly_algopin"
SERVICE_CREATE_DAILY = "create_daily_algopin"
SERVICE_REVOKE = "revoke_algopin"

PLATFORMS: list[str] = ["sensor"]

# Documented client-credentials lifetime is 86400 seconds. Refresh early.
TOKEN_SKEW = timedelta(seconds=60)
POLL_INTERVAL = timedelta(minutes=30)

# Current igloohome home API. igloohome-api 0.1.2 still targets the legacy host.
API_ROOT = "https://api.igloohome.co/home"

HOURLY_MIN_HOURS = 1
HOURLY_MAX_HOURS = 672
DAILY_MIN_DAYS = 29
DAILY_MAX_DAYS = 367
HOURLY_PAST_GRACE = timedelta(hours=1)
