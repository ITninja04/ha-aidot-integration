"""The library's protocol chatter stays out of the Home Assistant log.

python-aidot logs device login passwords at WARNING. This fails if those
lines can reach the log again, for example if the logger line in __init__.py
is dropped while syncing with upstream.
"""

import logging

import pytest

from homeassistant.core import HomeAssistant

from .conftest import setup_entry


async def test_library_warnings_hidden(
    hass: HomeAssistant, fake_cloud, config_entry, caplog: pytest.LogCaptureFixture
) -> None:
    await setup_entry(hass, config_entry)
    caplog.clear()
    logging.getLogger("aidot.device_client").warning("send_action {'password': 'x'}")
    logging.getLogger("aidot.device_client").error("connect failed")
    messages = [record.getMessage() for record in caplog.records]
    assert "send_action {'password': 'x'}" not in messages
    assert "connect failed" in messages
