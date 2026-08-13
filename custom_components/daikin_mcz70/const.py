"""Constants for the Daikin MCZ70 integration."""

from datetime import timedelta

DOMAIN = "daikin_mcz70"

CONF_IP_ADDRESS = "ip_address"
CONF_CLIENT_ID = "client_id"
CONF_UUID = "uuid"
CONF_CLIENT_SECRET = "client_secret"
CONF_TERMINAL_ID = "terminal_id"
CONF_PORT = "port"
CONF_ID = "id"
CONF_SPW = "spw"
CONF_APW = "apw"
CONF_REDIRECT_URI = "redirect_uri"

# Public constants embedded in the Daikin Smart APP APK (extractable by
# anyone via APK analysis; not user-specific secrets). Used as defaults in
# the config flow so most users do not need to enter them. Overridable in
# the config form.
DEFAULT_CLIENT_ID = "i66rposkjbceagakohlncsnus"
DEFAULT_CLIENT_SECRET = "bp3c3lpt05tnoimqpsq1c73uhegl9vhei0voks58bphlqisjjqd"
DEFAULT_REDIRECT_URI = "daikinsmartapp://callback"
# Server does not validate the uuid: real-device testing proved arbitrary
# values still issue codes (probe_uuid.py). Extracted from the authorize
# query of the Daikin Smart APP APK; overridable in the config form.
DEFAULT_UUID = "49ffb6aa-88fe-4fb4-a9aa-63499e130f51"

CLOUD_API_BASE = "https://api.daikinsmartdb.jp"

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=2)

# Token persistence keys (stored in config entry data)
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_TOKEN_EXPIRY = "token_expiry"
