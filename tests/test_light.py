"""What Home Assistant shows and what reaches the light.

Asserts on the entity state Home Assistant publishes and on the value sent
to the device, the two places the built-in integration got the strip wrong.
"""

from homeassistant.components.light import (
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_ON,
    ColorMode,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import BULB_ID, STRIP_ID, setup_entry

STRIP = "light.living_accent_lights"
BULB = "light.test_bulb"


async def test_strip_shows_rgb_only(
    hass: HomeAssistant, fake_cloud, config_entry
) -> None:
    await setup_entry(hass, config_entry)
    state = hass.states.get(STRIP)
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGB]
    assert state.attributes[ATTR_COLOR_MODE] == ColorMode.RGB
    assert state.attributes["color_profile"] == "rgb"
    assert state.attributes["color_profile_source"] == "known_model"


async def test_rgbcw_bulb_unchanged(
    hass: HomeAssistant, fake_cloud, config_entry
) -> None:
    await setup_entry(hass, config_entry)
    state = hass.states.get(BULB)
    assert state is not None
    assert set(state.attributes[ATTR_SUPPORTED_COLOR_MODES]) == {
        ColorMode.RGBW,
        ColorMode.COLOR_TEMP,
    }


async def test_rgb_sends_zero_white(
    hass: HomeAssistant, fake_cloud, config_entry
) -> None:
    await setup_entry(hass, config_entry)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: STRIP, ATTR_RGB_COLOR: (10, 20, 30)},
        blocking=True,
    )
    device = fake_cloud.device_clients[STRIP_ID]
    device.async_set_rgbw.assert_awaited_once_with((10, 20, 30, 0))
    assert hass.states.get(STRIP).attributes[ATTR_RGB_COLOR] == (10, 20, 30)


async def test_color_temp_on_strip_becomes_rgb(
    hass: HomeAssistant, fake_cloud, config_entry
) -> None:
    """A scene asking for warm white must not send CCT to an RGB strip."""

    await setup_entry(hass, config_entry)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: STRIP, ATTR_COLOR_TEMP_KELVIN: 2700},
        blocking=True,
    )
    device = fake_cloud.device_clients[STRIP_ID]
    device.async_set_cct.assert_not_awaited()
    device.async_set_rgbw.assert_awaited_once()
    sent = device.async_set_rgbw.await_args.args[0]
    assert sent[3] == 0
    assert sent[0] > sent[2]


async def test_bulb_still_gets_cct(
    hass: HomeAssistant, fake_cloud, config_entry
) -> None:
    await setup_entry(hass, config_entry)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: BULB, ATTR_COLOR_TEMP_KELVIN: 3000},
        blocking=True,
    )
    fake_cloud.device_clients[BULB_ID].async_set_cct.assert_awaited_once_with(3000)
