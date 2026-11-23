"""The aidot integration.

Same setup as the built-in integration in Home Assistant 2026.11.2, written
with the 2026.10 forms (a no-op lambda instead of async_noop, and
async_unload_platforms returning a bool) so it loads on 2026.10 as well.
Both forms are accepted by 2026.11.2.
"""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AidotConfigEntry, AidotDeviceManagerCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]


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
