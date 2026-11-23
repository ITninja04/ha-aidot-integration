"""Config flow for Aidot integration.

The login steps are the built-in integration's, unchanged from Home
Assistant 2026.11.2, so an existing AiDot entry keeps working when this
custom integration takes over the domain. The options flow is new: it lets
the user correct a light's color controls when the cloud record is wrong
(see capabilities.py).
"""

from collections.abc import Mapping
from typing import Any, override

from aidot.client import AidotClient
from aidot.const import CONF_ID, DEFAULT_COUNTRY_CODE, SUPPORTED_COUNTRY_CODES
from aidot.exceptions import AidotUserOrPassIncorrect
from aiohttp import ClientError
import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_COUNTRY_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .capabilities import AUTO, ColorProfile
from .const import CONF_COLOR_OVERRIDES, CONF_COLOR_PROFILE, CONF_DEVICE, DOMAIN

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(
            CONF_COUNTRY_CODE,
            default=DEFAULT_COUNTRY_CODE,
        ): selector.CountrySelector(
            selector.CountrySelectorConfig(
                countries=SUPPORTED_COUNTRY_CODES,
            )
        ),
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)

REAUTH_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_PASSWORD)): str}
)


class AidotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle aidot config flow."""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AidotOptionsFlow:
        """Return the options flow."""
        return AidotOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = AidotClient(
                session=async_get_clientsession(self.hass),
                country_code=user_input[CONF_COUNTRY_CODE],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            login_info, errors = await self._async_login(client)
            if login_info is not None:
                await self.async_set_unique_id(login_info[CONF_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{user_input[CONF_USERNAME]} {user_input[CONF_COUNTRY_CODE]}",
                    data=login_info,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            client = AidotClient(
                session=async_get_clientsession(self.hass),
                token=dict(reauth_entry.data),
            )
            client.update_password(user_input[CONF_PASSWORD])
            login_info, errors = await self._async_login(client)
            if login_info is not None:
                await self.async_set_unique_id(login_info[CONF_ID])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=login_info
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={CONF_USERNAME: reauth_entry.data[CONF_USERNAME]},
        )

    async def _async_login(
        self, client: AidotClient
    ) -> tuple[dict[str, Any] | None, dict[str, str]]:
        """Log in and return the login info or the errors."""
        try:
            login_info = await client.async_post_login()
        except AidotUserOrPassIncorrect:
            return None, {"base": "invalid_auth"}
        except TimeoutError, ClientError:
            return None, {"base": "cannot_connect"}
        finally:
            # The client starts LAN discovery once it has login info
            await client.async_cleanup()
        return login_info, {}


PROFILE_OPTIONS = [AUTO, *(profile.value for profile in ColorProfile)]


class AidotOptionsFlow(OptionsFlowWithReload):
    """Pick a light, then pick the color controls it really has.

    Two steps instead of one form with a field per light: field labels in an
    options form cannot carry device names, so a one-page form would show
    raw device ids. Saving reloads the entry so the entity picks up its new
    supported color modes, which Home Assistant reads only at setup.
    """

    _device_id: str | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the light to change."""
        coordinator = getattr(self.config_entry, "runtime_data", None)
        devices = (
            {
                dev_id: device_coordinator.device_client.info.name or dev_id
                for dev_id, device_coordinator in coordinator.device_coordinators.items()
            }
            if coordinator is not None
            else {}
        )
        if not devices:
            return self.async_abort(reason="no_devices")
        if user_input is not None:
            self._device_id = user_input[CONF_DEVICE]
            return await self.async_step_color()

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_DEVICE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=dev_id, label=name)
                                for dev_id, name in sorted(
                                    devices.items(), key=lambda item: item[1]
                                )
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_color(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the color profile for the selected light."""
        assert self._device_id is not None
        overrides: dict[str, str] = dict(
            self.config_entry.options.get(CONF_COLOR_OVERRIDES, {})
        )
        if user_input is not None:
            choice = user_input[CONF_COLOR_PROFILE]
            if choice == AUTO:
                overrides.pop(self._device_id, None)
            else:
                overrides[self._device_id] = choice
            return self.async_create_entry(
                data={**self.config_entry.options, CONF_COLOR_OVERRIDES: overrides}
            )

        return self.async_show_form(
            step_id="color",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_COLOR_PROFILE,
                        default=overrides.get(self._device_id, AUTO),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=PROFILE_OPTIONS,
                            translation_key=CONF_COLOR_PROFILE,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )
