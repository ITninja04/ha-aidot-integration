# AiDot (color fix) for Home Assistant

A drop-in replacement for Home Assistant's built-in AiDot integration that
shows each light with the color controls it really has.

The built-in integration offers color plus white plus color temperature
(RGBW and color temp) for every AiDot light whose cloud record has a color
service. An RGB-only strip then shows a white slider and a color temperature
wheel it cannot follow, and scenes that set a white temperature send it the
wrong thing. This integration fixes that and leaves everything else as the
built-in one does it.

## What changes

- Color temperature is offered only when the light's AiDot cloud record lists
  a color temperature service. Lights that only list the color service show
  color (and white) without a temperature wheel.
- Known models whose cloud record cannot tell RGB from RGBW are corrected from
  a small list. Today that list has one entry, the LK A001818 "Smart Light
  Strip-10ft", which is RGB only.
- Any light can be set by hand: Settings > Devices and services > AiDot >
  Configure, pick the light, pick what it can do. Saving reloads the
  integration.
- An RGB-only light that gets a white temperature request (from a scene, for
  example) gets the nearest RGB color instead.
- Each light shows `color_profile` (what it was set to) and
  `color_profile_source` (`options`, `known_model` or `cloud`) as attributes,
  so you can see why it looks the way it does.

## What does not change

Login, the device list, the local connection to each light, effects, and the
entity and device IDs are the built-in integration's, copied from Home
Assistant 2026.11.2. An existing AiDot setup keeps its entities, automations
and dashboards.

## Limits

- The AiDot cloud record cannot say whether a light has a white LED. If your
  light shows a white slider it does not have, set it to "Color only (RGB)"
  in Configure, and please open an issue with the model so it can be added to
  the list.
- If an older RGBW bulb lost its color temperature wheel after switching to
  this integration, its cloud record does not list a temperature service. Set
  it to "Color plus tunable white (RGBCW)" in Configure.
- Tested against Home Assistant 2026.10.4 in automated tests and 2026.11.2 on
  a live install. Older releases are not supported.
- Home Assistant shows a warning at startup that a custom integration
  replaces the built-in `aidot`. That is expected.

## Install

1. In Home Assistant, open Settings > Marketplace, open the menu, choose
   Custom repositories, and add `https://github.com/ITninja04/ha-aidot-integration`
   as an Integration.
2. Install "AiDot (color fix)" and restart Home Assistant.
3. If AiDot was already set up, nothing else is needed: the existing entry is
   picked up. Otherwise add AiDot from Settings > Devices and services.

To go back to the built-in integration, remove this one from the Marketplace
and restart.

## Development

Tests: `uv sync && uv run pytest` (Python 3.14.2 or newer), or `scripts/check.sh`
for lint, format and tests together.
`scripts/dump_devices.py` prints what the AiDot cloud says about each of your
lights, with keys and passwords removed, which is the first thing to look at
when a light shows the wrong controls.
`scripts/channel_walk.py` drives the A001818 strip through red, green, blue
and white one at a time over its local connection, shows what the strip
reports back for each, and asks what you see. It puts the strip back as it
was when it ends.

## License

Apache 2.0, the same license as the Home Assistant code this is based on. The
integration started as a copy of Home Assistant's `aidot` integration
(2026.11.2). Measured after the changes: `coordinator.py` matches it line for
line, `light.py` 54% and `config_flow.py` 63% of lines.
