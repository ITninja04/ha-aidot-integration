"""Dump what the AiDot cloud says about each light, with secrets removed.

Capability detection in this integration is driven entirely by the cloud's
product record (serviceModules and their properties). When a strip shows the
wrong color modes in Home Assistant, the first question is what that record
actually contains, and the HA UI cannot show it. This prints it.

Usage (from the repo root, credentials in .env as AIDOT_USERNAME and
AIDOT_PASSWORD, optional AIDOT_COUNTRY, default US):

  uv run --with python-aidot==0.3.59 python scripts/dump_devices.py > devices.json

The output keeps product and service data but drops aesKey, password and
token fields, so it can be pasted into an issue or a test fixture.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import aiohttp
from aidot.client import AidotClient
from aidot.const import CONF_DEVICE_LIST

SECRET_KEYS = {
    "aesKey",
    "password",
    "accessToken",
    "refreshToken",
    "token",
    "terminalId",
}


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def scrub(value):
    if isinstance(value, dict):
        return {
            k: ("<redacted>" if k in SECRET_KEYS else scrub(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


async def main() -> int:
    load_env(Path(".env"))
    username = os.environ.get("AIDOT_USERNAME")
    password = os.environ.get("AIDOT_PASSWORD")
    if not username or not password:
        print(
            "Set AIDOT_USERNAME and AIDOT_PASSWORD in .env (the AiDot app login).",
            file=sys.stderr,
        )
        return 2
    country = os.environ.get("AIDOT_COUNTRY", "US")
    async with aiohttp.ClientSession() as session:
        client = AidotClient(
            session=session, country_code=country, username=username, password=password
        )
        await client.async_post_login()
        data = await client.async_get_all_device()
        await client.async_cleanup()
    devices = []
    for device in data.get(CONF_DEVICE_LIST, []):
        # Effects are large and not part of capability detection.
        device.pop("effects", None)
        devices.append(device)
    print(json.dumps(scrub(devices), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
