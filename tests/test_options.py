"""The options flow changes what the entity offers after the reload.

Prevents a saved choice that is stored but never reaches the entity, which
is the failure a user would see as "I picked RGB and nothing changed".
"""

from homeassistant.components.light import ATTR_SUPPORTED_COLOR_MODES, ColorMode
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import STRIP_ID, setup_entry

STRIP = "light.living_accent_lights"


async def _choose(hass: HomeAssistant, entry, profile: str) -> None:
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"device": STRIP_ID}
    )
    assert result["step_id"] == "color"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"color_profile": profile}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_override_applies_after_reload(
    hass: HomeAssistant, fake_cloud, config_entry
) -> None:
    await setup_entry(hass, config_entry)
    await _choose(hass, config_entry, "rgb_cct")
    assert config_entry.options["color_overrides"] == {STRIP_ID: "rgb_cct"}
    state = hass.states.get(STRIP)
    assert set(state.attributes[ATTR_SUPPORTED_COLOR_MODES]) == {
        ColorMode.RGB,
        ColorMode.COLOR_TEMP,
    }
    assert state.attributes["color_profile_source"] == "options"


async def test_auto_clears_override(
    hass: HomeAssistant, fake_cloud, config_entry
) -> None:
    await setup_entry(hass, config_entry)
    await _choose(hass, config_entry, "rgbw")
    await _choose(hass, config_entry, "auto")
    assert config_entry.options["color_overrides"] == {}
    state = hass.states.get(STRIP)
    assert state.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.RGB]
