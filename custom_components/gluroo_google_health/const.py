"""Constants for Gluroo Google Health Sync."""

DOMAIN = "gluroo_google_health"
DEFAULT_TITLE = "Gluroo Google Health Sync"

CONF_GLUROO_URL = "gluroo_url"
CONF_GLUROO_TOKEN = "gluroo_token"
CONF_POLL_INTERVAL = "poll_interval"
CONF_SYNC_GOOGLE = "sync_google"

DEFAULT_POLL_INTERVAL = 60
MIN_POLL_INTERVAL = 30
MAX_POLL_INTERVAL = 900

OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH2_TOKEN = "https://oauth2.googleapis.com/token"
WRITE_SCOPE = (
    "https://www.googleapis.com/auth/"
    "googlehealth.health_metrics_and_measurements.writeonly"
)

GOOGLE_HEALTH_BASE = "https://health.googleapis.com/v4/users/me/dataTypes"
