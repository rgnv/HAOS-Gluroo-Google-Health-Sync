"""Gluroo Google Health Sync integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import GoogleHealthApi, GlurooApi
from .const import CONF_GLUROO_TOKEN, CONF_GLUROO_URL, CONF_SYNC_GOOGLE, DOMAIN
from .coordinator import GlurooCoordinator, GoogleUploader

PLATFORMS = ("sensor",)


@dataclass
class RuntimeData:
    """Runtime state for a configured Gluroo account."""

    coordinator: GlurooCoordinator
    uploader: GoogleUploader


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration domain."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gluroo polling and optional Google Health uploads."""
    session = aiohttp_client.async_get_clientsession(hass)
    gluroo_api = GlurooApi(
        session,
        str(entry.data[CONF_GLUROO_URL]),
        str(entry.data[CONF_GLUROO_TOKEN]),
    )
    coordinator = GlurooCoordinator(hass, entry, gluroo_api)

    google_api: GoogleHealthApi | None = None
    if entry.options.get(CONF_SYNC_GOOGLE, True):
        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(hass, entry)
        google_api = GoogleHealthApi(session, OAuth2Session(hass, entry, implementation))

    uploader = GoogleUploader(hass, entry, google_api)
    runtime = RuntimeData(coordinator=coordinator, uploader=uploader)
    entry.runtime_data = runtime
    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        raise ConfigEntryNotReady(str(err)) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async def sync_google_and_refresh_status() -> None:
        """Sync readings and refresh the status sensor after uploader state changes."""
        await uploader.async_sync(coordinator.data)
        coordinator.async_update_listeners()

    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: hass.async_create_task(sync_google_and_refresh_status())
        )
    )
    await sync_google_and_refresh_status()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Gluroo account."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
