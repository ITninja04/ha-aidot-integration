"""Decide which color controls an AiDot light really has.

The built-in integration (Home Assistant 2026.11.2, python-aidot 0.3.59)
reads one flag from the cloud product record: if the product lists a
`control.light.rgbw` service, the light is shown as RGBW plus color
temperature. There is no RGB-only path. An RGB strip that speaks the RGBW
protocol, like the LK A001818 in the living room, therefore shows a white
slider and a color temperature wheel it cannot honor, and scenes that set a
temperature drive it to the wrong color.

Measured on 2026-11-23 against the AiDot cloud for that strip (product
"Smart Light Strip-10ft", firmware 3.11.47): its serviceModules list
`control.light.rgbw` and no `control.light.cct`. python-aidot sets its CCT
flag for any RGBW product anyway (device_client.py, DeviceInformation), so
the color temperature controls come from the library, not from the record.
The record cannot say whether the color field drives a white LED: the RGB
strip and an RGBW strip would both list only `control.light.rgbw`.

So the answer comes from three sources, strongest first:

1. A per-device choice the user made in the integration options.
2. KNOWN_MODELS below, for models seen in the field to differ from what the
   cloud claims. Each entry names the evidence.
3. The cloud record, with color temperature offered only when the product
   really lists a `control.light.cct` service. This is the one change for
   lights with no override: an RGBW product without that service now shows
   RGBW alone instead of RGBW plus color temperature. If some older bulb
   lists only RGBW yet does take CCT, the options flow puts it back.

What is not known: whether any AiDot product record distinguishes RGB from
RGBW. The A001818 record does not, so the table and the options are the
only way to drop the white channel.
"""

from __future__ import annotations

from enum import StrEnum

from homeassistant.components.light import ColorMode


class ColorProfile(StrEnum):
    """The color shapes an AiDot light can have."""

    RGBCW = "rgbcw"
    RGBW = "rgbw"
    RGB_CCT = "rgb_cct"
    RGB = "rgb"
    CCT = "cct"
    DIMMABLE = "dimmable"


AUTO = "auto"

PROFILE_MODES: dict[ColorProfile, set[ColorMode]] = {
    ColorProfile.RGBCW: {ColorMode.RGBW, ColorMode.COLOR_TEMP},
    ColorProfile.RGBW: {ColorMode.RGBW},
    ColorProfile.RGB_CCT: {ColorMode.RGB, ColorMode.COLOR_TEMP},
    ColorProfile.RGB: {ColorMode.RGB},
    ColorProfile.CCT: {ColorMode.COLOR_TEMP},
    ColorProfile.DIMMABLE: {ColorMode.BRIGHTNESS},
}

# Keyed by the full cloud model id (`modelId`, e.g. "LK.light.A001818").
KNOWN_MODELS: dict[str, ColorProfile] = {
    # "Smart Light Strip-10ft", the living room accent strip. Its cloud
    # record lists only control.light.rgbw, which cannot tell RGB from RGBW
    # (record saved in tests/fixtures/lk_a001818.json). Ozzie reported on
    # 2026-11-23 that the strip is RGB only and the white and color
    # temperature controls cause problems.
    "LK.light.A001818": ColorProfile.RGB,
}


def cloud_profile(has_rgbw_service: bool, has_cct_service: bool) -> ColorProfile:
    """Return the profile the product record supports."""

    if has_rgbw_service and has_cct_service:
        return ColorProfile.RGBCW
    if has_rgbw_service:
        return ColorProfile.RGBW
    if has_cct_service:
        return ColorProfile.CCT
    return ColorProfile.DIMMABLE


def resolve_profile(
    model_id: str | None,
    has_rgbw_service: bool,
    has_cct_service: bool,
    override: str | None,
) -> ColorProfile:
    """Pick the profile for one device, user choice first."""

    if override is not None and override != AUTO:
        try:
            return ColorProfile(override)
        except ValueError:
            # A stored value from a future version: fall through to auto
            # rather than refusing to set up the light.
            pass
    if model_id is not None and model_id in KNOWN_MODELS:
        return KNOWN_MODELS[model_id]
    return cloud_profile(has_rgbw_service, has_cct_service)


def profile_source(model_id: str | None, override: str | None) -> str:
    """Name which of the three sources decided the profile."""

    if override is not None and override != AUTO and override in set(ColorProfile):
        return "options"
    if model_id is not None and model_id in KNOWN_MODELS:
        return "known_model"
    return "cloud"
