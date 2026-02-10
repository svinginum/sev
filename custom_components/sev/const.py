"""Constants for the SEV integration."""

DOMAIN = "sev"
NAME = "SEV"

API_BASE_URL = "https://api.sev.fo/api/CustomerRESTApi"

# Rate limit: max 10 API calls per 5 minutes
SCAN_INTERVAL_MINUTES = 30  # Conservative to stay under limit

# Config keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# API response keys
ATTR_METER_ID = "meter_id"
ATTR_READINGS = "readings"
ATTR_TIME_STAMP = "time_stamp"
ATTR_READING = "reading"
ATTR_CUMULATIVE_VALUE = "cumulative_value"
ATTR_UNIT = "unit"
ATTR_PRICE_UNIT = "price_unit"
ATTR_TARIF = "tarif"
