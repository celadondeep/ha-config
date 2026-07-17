"""Constants for the ESO Energy Consumption integration."""

DOMAIN = "eso"

# Account configuration
CONF_OBJECTS = "objects"
CONF_CONSUMED = "consumed"
CONF_RETURNED = "returned"
CONF_COST = "cost"
CONF_PRICE_ENTITY = "price_entity"
CONF_PRICE_CURRENCY = "price_currency"

# IMAP (two-factor) configuration
CONF_IMAP = "imap"
CONF_IMAP_HOST = "host"
CONF_IMAP_PORT = "port"
CONF_IMAP_SENDER = "sender"
CONF_IMAP_FOLDER = "folder"
CONF_USE_IMAP = "use_imap"

# Defaults
DEFAULT_IMAP_HOST = "imap.gmail.com"
DEFAULT_IMAP_PORT = 993
DEFAULT_IMAP_SENDER = "savitarna@eso.lt"
DEFAULT_IMAP_FOLDER = "INBOX"
DEFAULT_PRICE_CURRENCY = "EUR"

# Persisted authenticated session (see ESOClient)
SESSION_FILE = "eso_session.json"

# ESO energy series keys
POWER_CONSUMED = "P+"
POWER_RETURNED = "P-"
ENERGY_TYPE_MAP = {
    CONF_CONSUMED: POWER_CONSUMED,
    CONF_RETURNED: POWER_RETURNED,
}

# 3 hour pause between fetch retries
RETRY_DELAY_SECONDS = 3 * 3600

# Subentry type: one metering point (object) per subentry
SUBENTRY_TYPE_OBJECT = "object"

# Dispatcher signal fired after the stored-bank series is refreshed
def signal_stored_updated(entry_id: str) -> str:
    return f"{DOMAIN}_{entry_id}_stored_updated"


# Dispatcher signal fired after the inbox messages are refreshed
def signal_messages_updated(entry_id: str) -> str:
    return f"{DOMAIN}_{entry_id}_messages_updated"


# Event fired on the HA bus for every message not seen before
EVENT_NEW_MESSAGE = "eso_new_message"
# Event fired for every planned-outage window newly seen on the dashboard
EVENT_PLANNED_OUTAGE = "eso_planned_outage"
# Matytų pranešimų id sąrašas (kad įvykiai nešaudytų pakartotinai)
SEEN_MESSAGES_FILE = "eso_seen_messages.json"


# Service to trigger an on-demand import
SERVICE_IMPORT_NOW = "import_now"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_DATE_FROM = "date_from"
ATTR_DATE_TO = "date_to"
