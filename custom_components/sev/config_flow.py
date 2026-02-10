"""Config flow for the SEV integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .api import SevApiClient, SevApiError

_LOGGER = logging.getLogger(__name__)


class SevConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SEV."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step (user form)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input.get(CONF_USERNAME, "").strip()
            password = user_input.get(CONF_PASSWORD, "")
            if not username:
                errors["base"] = "invalid_username"
            elif not password:
                errors["base"] = "invalid_password"
            else:
                session = aiohttp_client.async_get_clientsession(self.hass)
                client = SevApiClient(username=username, password=password, session=session)
                try:
                    await client._login()
                except SevApiError as e:
                    _LOGGER.warning("SEV login failed: %s", e)
                    errors["base"] = "invalid_auth"
                if not errors:
                    return self.async_create_entry(
                        title=f"SEV ({username})",
                        data={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=user_input.get(CONF_USERNAME, "") if user_input else ""): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "docs_url": "https://api.sev.fo",
            },
        )
