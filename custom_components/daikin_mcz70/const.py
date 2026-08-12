"""Constants for the Daikin MCZ70 integration."""

from datetime import timedelta

DOMAIN = "daikin_mcz70"

CONF_IP_ADDRESS = "ip_address"
CONF_CODE = "code"
CONF_CLIENT_ID = "client_id"
CONF_UUID = "uuid"
CONF_CLIENT_SECRET = "client_secret"
CONF_TERMINAL_ID = "terminal_id"
CONF_PORT = "port"
CONF_ID = "id"
CONF_SPW = "spw"

CLOUD_API_BASE = "https://api.daikinsmartdb.jp"

DEFAULT_UPDATE_INTERVAL = timedelta(seconds=2)

# Token persistence keys (stored in config entry data)
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_TOKEN_EXPIRY = "token_expiry"
