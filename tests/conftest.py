"""Stand-ins for the AiDot cloud and the lights, so tests run offline.

Capability detection is not faked: devices go through python-aidot's real
DeviceInformation, so a test sees exactly the flags the library derives from
a product record. Only the network side (login, device list, the LAN socket)
is replaced.

STRIP_DEVICE carries the real A001818 product record from the AiDot cloud
(tests/fixtures/lk_a001818.json, pulled 2026-11-23 with
scripts/dump_devices.py, device identity replaced). BULB_DEVICE is made up:
no RGBCW product has been dumped yet.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from aidot.const import CONF_DEVICE_LIST
from aidot.device_client import DeviceInformation, DeviceStatusData
import pytest

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

DOMAIN = "aidot"

STRIP_ID = "strip-a001818"
BULB_ID = "bulb-rgbcw"

STRIP_DEVICE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "lk_a001818.json").read_text()
)

BULB_DEVICE: dict[str, Any] = {
    "id": BULB_ID,
    "mac": "aa:bb:cc:00:00:02",
    "modelId": "LK.light.TESTBULB",
    "name": "Test Bulb",
    "hardwareVersion": None,
    "type": "light",
    "aesKey": ["0123456789abcdef"],
    "product": {
        "serviceModules": [
            {"identity": "control.light.rgbw"},
            {
                "identity": "control.light.cct",
                "properties": [{"minValue": 2700, "maxValue": 6500}],
            },
        ]
    },
}


class FakeDeviceClient:
    """A light that records what it was told to do."""

    def __init__(self, device: dict[str, Any]) -> None:
        self.info = DeviceInformation(device)
        self.status = DeviceStatusData()
        self.status.online = True
        self.status.on = True
        self.on_status_update = None
        self.async_set_rgbw = AsyncMock()
        self.async_set_cct = AsyncMock()
        self.async_set_brightness = AsyncMock()
        self.async_set_effect = AsyncMock()
        self.async_turn_on = AsyncMock()
        self.async_turn_off = AsyncMock()


class FakeAidotClient:
    """The cloud side: hands out the device list and device clients."""

    devices: list[dict[str, Any]] = []
    device_clients: dict[str, FakeDeviceClient] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.login_info = {"accessToken": "token", "id": "user-1"}

    def set_token_fresh_cb(self, callback: Any) -> None:
        pass

    async def async_post_login(self) -> dict[str, Any]:
        return self.login_info

    async def async_get_all_device(self) -> dict[str, Any]:
        return {CONF_DEVICE_LIST: [dict(device) for device in self.devices]}

    def get_device_client(self, device: dict[str, Any]) -> FakeDeviceClient:
        client = self.device_clients.get(device["id"])
        if client is None:
            client = FakeDeviceClient(device)
            self.device_clients[device["id"]] = client
        return client

    async def async_cleanup(self) -> None:
        pass


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/aidot instead of the built-in integration."""


@pytest.fixture
def fake_cloud() -> type[FakeAidotClient]:
    """Patch the cloud client with the two test devices."""

    FakeAidotClient.devices = [STRIP_DEVICE, BULB_DEVICE]
    FakeAidotClient.device_clients = {}
    with patch("custom_components.aidot.coordinator.AidotClient", FakeAidotClient):
        yield FakeAidotClient


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """An entry shaped like the login info the built-in integration stores."""

    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="user-1",
        title="test US",
        data={
            "id": "user-1",
            "accessToken": "token",
            "username": "test",
            "password": "pw",
            "region": "us",
            "country": "United States",
        },
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry and wait for its lights."""

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
