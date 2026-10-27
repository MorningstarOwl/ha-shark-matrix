"""Constants for the Shark Matrix (SharkNinja AWS / skegox) integration."""

DOMAIN = "shark_matrix"

# --- Auth0 (SharkNinja tenant) ---
AUTH_HOST = "login.sharkninja.com"
CLIENT_ID = "wsguxrqm77mq4LtrTrwg8ZJUxmSrexGi"
OAUTH_SCOPE = "openid profile email offline_access"

# --- skegox AWS API (reverse-engineered from SharkClean 6.30.0) ---
API_BASE = "https://stakra.slatra.thor.skegox.com"
API_KEY = "QQdbSrgicK2PxvACI1a2P5AN2xgO78Lw1VvnYczb"
CALLER = "ENDUSER_MOBILEAPP"
USER_AGENT = "snjs"

# config entry keys
CONF_REFRESH_TOKEN = "refresh_token"
CONF_HOUSEHOLD_ID = "household_id"

DEFAULT_SCAN_INTERVAL = 30  # seconds

# --- Operating_Mode enum (2 & 3 confirmed via live capture; 0/1 per classic SharkIQ) ---
OP_STOP = 0
OP_PAUSE = 1
OP_START = 2
OP_RETURN = 3

# --- Power_Mode (suction). 0 observed while UI = "Normal"; verify Eco/Max mapping. ---
POWER_MODES = {
    "Eco": 1,
    "Normal": 0,
    "Max": 2,
}
POWER_MODES_REVERSE = {v: k for k, v in POWER_MODES.items()}
