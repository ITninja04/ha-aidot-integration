"""The aidot integration.

Same setup as the built-in integration in Home Assistant 2026.11.2, written
with the 2026.10 forms (a no-op lambda instead of async_noop, and
async_unload_platforms returning a bool) so it loads on 2026.10 as well.
Both forms are accepted by 2026.11.2.
"""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AidotConfigEntry, AidotDeviceManagerCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]

# python-aidot 0.3.59 logs its protocol traffic at WARNING, and those lines
# include each light's local login password (getDevAttrReq payloads) and
# every discovery broadcast. Seen in Ozzie's HA system log on 2026-11-23.
# Filtering only the password would still leave the log flooded, so the
# library is held to ERROR. Its real failures still show. To see the traffic
# when debugging, raise it again with the logger.set_level action
# (aidot: debug); that call wins because it runs after this import.
logging.getLogger("aidot").setLevel(logging.ERROR)


async def async_setup_entry(hass: HomeAssistant, entry: AidotConfigEntry) -> bool:
    """Set up aidot from a config entry."""

    coordinator = AidotDeviceManagerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Keeps the device list refresh running: a coordinator with no
    # listeners never polls.
    entry.async_on_unload(coordinator.async_add_listener(lambda: None))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AidotConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_cleanup()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
