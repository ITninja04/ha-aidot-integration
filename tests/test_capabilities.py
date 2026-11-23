"""The profile decision, source by source.

Guards against the built-in behavior coming back: an RGB strip whose cloud
record says RGBW being offered a white channel and color temperature.
"""

from custom_components.aidot.capabilities import (
    AUTO,
    ColorProfile,
    profile_source,
    resolve_profile,
)


def test_known_rgb_strip_is_rgb_despite_cloud_rgbw() -> None:
    assert resolve_profile("LK.light.A001818", True, True, None) is ColorProfile.RGB
    assert profile_source("LK.light.A001818", None) == "known_model"


def test_unknown_model_follows_record() -> None:
    assert resolve_profile("LK.light.OTHER", True, True, None) is ColorProfile.RGBCW
    assert resolve_profile("LK.light.OTHER", False, True, None) is ColorProfile.CCT
    assert (
        resolve_profile("LK.light.OTHER", False, False, None) is ColorProfile.DIMMABLE
    )
    assert profile_source("LK.light.OTHER", None) == "cloud"


def test_rgbw_without_cct_service_has_no_color_temp() -> None:
    """The built-in integration adds color temp here; the record does not."""

    assert resolve_profile("LK.light.OTHER", True, False, None) is ColorProfile.RGBW


def test_user_choice_beats_known_model() -> None:
    assert (
        resolve_profile("LK.light.A001818", True, True, "rgbcw") is ColorProfile.RGBCW
    )
    assert profile_source("LK.light.A001818", "rgbcw") == "options"


def test_auto_and_unknown_choice_fall_back() -> None:
    assert resolve_profile("LK.light.A001818", True, True, AUTO) is ColorProfile.RGB
    assert (
        resolve_profile("LK.light.OTHER", True, True, "sparkly") is ColorProfile.RGBCW
    )
    assert profile_source("LK.light.OTHER", "sparkly") == "cloud"
