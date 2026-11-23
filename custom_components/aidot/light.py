"""AiDot lights, with color controls that match the hardware.

Copied from the built-in integration at Home Assistant 2026.11.2. The one
behavior change is where supported color modes come from: see
capabilities.py for why the cloud flag alone is wrong for some strips.
"""

from typing import Any, override

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .capabilities import PROFILE_MODES, profile_source, resolve_profile
from .const import CONF_COLOR_OVERRIDES, DOMAIN
from .coordinator import AidotConfigEntry, AidotDeviceUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AidotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Light."""
    coordinator = entry.runtime_data
    overrides: dict[str, str] = entry.options.get(CONF_COLOR_OVERRIDES, {})
    async_add_entities(
        AidotLight(
            device_coordinator,
            overrides.get(device_coordinator.device_client.info.dev_id),
        )
        for device_coordinator in coordinator.device_coordinators.values()
    )


class AidotLight(CoordinatorEntity[AidotDeviceUpdateCoordinator], LightEntity):
    """Representation of a Aidot Wi-Fi Light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: AidotDeviceUpdateCoordinator,
        override: str | None = None,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        info = coordinator.device_client.info
        self._attr_unique_id = info.dev_id
        if hasattr(info, "cct_max"):
            self._attr_max_color_temp_kelvin = info.cct_max
        if hasattr(info, "cct_min"):
            self._attr_min_color_temp_kelvin = info.cct_min

        model_id = info.model_id
        manufacturer = model_id.split(".")[0]
        model = model_id[len(manufacturer) + 1 :]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            connections={(CONNECTION_NETWORK_MAC, info.mac)},
            manufacturer=manufacturer,
            model=model,
            name=info.name,
            hw_version=info.hw_version,
        )
        if info.preset_names:
            self._attr_effect_list = info.preset_names
            self._attr_supported_features = LightEntityFeature.EFFECT

        # python-aidot sets enable_cct for every RGBW product, so it cannot
        # say whether a CCT service exists. cct_min is set only when the
        # record has one, which makes it the real signal.
        self.color_profile = resolve_profile(
            model_id, info.enable_rgbw, hasattr(info, "cct_min"), override
        )
        # Shown on the entity so anyone can see which source won without
        # reading logs: the profile in use and where it came from.
        self._attr_extra_state_attributes = {
            "color_profile": str(self.color_profile),
            "color_profile_source": profile_source(model_id, override),
        }
        modes = PROFILE_MODES[self.color_profile]
        self._attr_supported_color_modes = set(modes)
        # Start in the color mode, not temperature, when a light has both:
        # that is what the built-in integration did for RGBW lights.
        for mode in (ColorMode.RGBW, ColorMode.RGB, ColorMode.COLOR_TEMP):
            if mode in modes:
                self._attr_color_mode = mode
                break
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        self._update_status()

    def _update_status(self) -> None:
        """Update light status from coordinator data."""
        data = self.coordinator.data
        self._attr_is_on = data.on
        self._attr_brightness = data.dimming
        self._attr_color_temp_kelvin = data.cct
        self._attr_rgbw_color = data.rgbw
        # The device always reports a 4-channel value. An RGB strip has no
        # white channel, so only the first three mean anything.
        self._attr_rgb_color = tuple(data.rgbw[:3])
        self._attr_effect = data.effect or None

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.online

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update."""
        self._update_status()
        super()._handle_coordinator_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, applying any requested brightness and color."""
        # Brightness is independent of color: a scene sends both at once, and
        # the color must not be dropped just because brightness came with it.
        handled_command = False
        client = self.coordinator.device_client
        data = self.coordinator.data
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
            await client.async_set_brightness(brightness)
            data.dimming = brightness
            self._attr_brightness = brightness
            handled_command = True

        # Home Assistant converts a temperature request to RGB before it gets
        # here when COLOR_TEMP is not supported, so this branch only runs for
        # lights that have a real white channel pair.
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp_kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
            await client.async_set_cct(color_temp_kelvin)
            data.cct = color_temp_kelvin
            self._attr_color_temp_kelvin = color_temp_kelvin
            self._attr_color_mode = ColorMode.COLOR_TEMP
            data.effect = ""
            self._attr_effect = None
            handled_command = True

        if ATTR_RGBW_COLOR in kwargs:
            rgbw_color = kwargs.get(ATTR_RGBW_COLOR)
            await client.async_set_rgbw(rgbw_color)
            data.rgbw = rgbw_color
            self._attr_rgbw_color = rgbw_color
            self._attr_color_mode = ColorMode.RGBW
            data.effect = ""
            self._attr_effect = None
            handled_command = True

        if ATTR_RGB_COLOR in kwargs:
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            # The protocol has one 32-bit RGBW field. White is sent as 0 so
            # an RGB strip never sees a value for a channel it lacks.
            rgbw_color = (red, green, blue, 0)
            await client.async_set_rgbw(rgbw_color)
            data.rgbw = rgbw_color
            self._attr_rgbw_color = rgbw_color
            self._attr_rgb_color = (red, green, blue)
            self._attr_color_mode = ColorMode.RGB
            data.effect = ""
            self._attr_effect = None
            handled_command = True

        if ATTR_EFFECT in kwargs:
            effect = kwargs.get(ATTR_EFFECT)
            await client.async_set_effect(effect)
            data.effect = effect
            self._attr_effect = effect
            handled_command = True

        if not handled_command:
            # Nothing was requested to apply, so just switch it on.
            await client.async_turn_on()

        data.on = True
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.device_client.async_turn_off()
        self.coordinator.data.on = False
        self._attr_is_on = False
        self.async_write_ha_state()
