"""Config and options flows for Gluroo Google Health Sync."""

from collections.abc import Mapping
import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow, SOURCE_REAUTH
from homeassistant.const import CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_GLUROO_TOKEN,
    CONF_GLUROO_URL,
    CONF_POLL_INTERVAL,
    CONF_SYNC_GOOGLE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TITLE,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
    WRITE_SCOPE,
)

_LOGGER = logging.getLogger(__name__)


class GlurooConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle Gluroo credentials followed by Google OAuth."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        super().__init__()
        self._gluroo_data: dict[str, str] = {}

    @property
    def logger(self) -> logging.Logger:
        """Return the integration logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Request only the Google Health write scope."""
        return {"scope": WRITE_SCOPE, "access_type": "offline", "prompt": "consent"}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect the Gluroo Global Connect URL and token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            base_url = str(user_input[CONF_GLUROO_URL]).strip().rstrip("/")
            parsed = urlparse(base_url)
            token = str(user_input[CONF_GLUROO_TOKEN]).strip()
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                errors[CONF_GLUROO_URL] = "invalid_url"
            elif parsed.query or parsed.fragment:
                errors[CONF_GLUROO_URL] = "url_must_not_include_token"
            elif not token:
                errors[CONF_GLUROO_TOKEN] = "required"
            else:
                self._gluroo_data = {
                    CONF_GLUROO_URL: base_url,
                    CONF_GLUROO_TOKEN: token,
                }
                return await self.async_step_pick_implementation()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GLUROO_URL): str,
                    vol.Required(CONF_GLUROO_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Reauthorize Google without discarding Gluroo credentials."""
        self._gluroo_data = {
            CONF_GLUROO_URL: str(entry_data[CONF_GLUROO_URL]),
            CONF_GLUROO_TOKEN: str(entry_data[CONF_GLUROO_TOKEN]),
        }
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthorization."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({}))
        return await self.async_step_pick_implementation()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create or update the fully configured entry."""
        scopes = data.get(CONF_TOKEN, {}).get("scope", "").split()
        if WRITE_SCOPE not in scopes:
            return self.async_abort(reason="missing_write_scope")
        merged = {**self._gluroo_data, **data}
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=merged)
        return self.async_create_entry(
            title=DEFAULT_TITLE,
            data=merged,
            options={CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL, CONF_SYNC_GOOGLE: True},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the poll/sync options flow."""
        return GlurooOptionsFlow()


class GlurooOptionsFlow(OptionsFlow):
    """Adjust polling and Google upload behavior."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=self.config_entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)),
                vol.Required(
                    CONF_SYNC_GOOGLE,
                    default=self.config_entry.options.get(CONF_SYNC_GOOGLE, True),
                ): cv.boolean,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
