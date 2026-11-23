"""Walk the living room strip through each color channel, one at a time.

The AiDot cloud record cannot say whether a strip has a white LED, and Home
Assistant now hides white from it, so the only way to know is to drive each
channel by itself and look. This sends red, green, blue and then white alone
straight to the strip over its local connection (the same one Home Assistant
uses), at full brightness, and asks what you see. A strip with no white LED
goes dark, or shows nothing new, on the white step.

After each step it also prints what the strip reports back, so the answer is
the strip's own value, not only what was sent.

When it ends, or on Ctrl+C, the strip goes back to the color, brightness and
on/off state it had before. Home Assistant may show the strip as unavailable
for a few seconds while this script holds the connection, and reconnects on
its own.

Run from the repo root (credentials from .env: AIDOT_USERNAME, AIDOT_PASSWORD):

  uv run --no-project --with python-aidot==0.3.59 python scripts/channel_walk.py

Interactive by default: type what you see after each step, Enter to go on.
`--hold 8` runs unattended instead, holding each step for 8 seconds, for
when someone else is watching the strip.
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

import aiohttp
from aidot.client import AidotClient

MODEL_ID = "LK.light.A001818"

STEPS = [
    ("red only", (255, 0, 0, 0)),
    ("green only", (0, 255, 0, 0)),
    ("blue only", (0, 0, 255, 0)),
    ("white channel only", (0, 0, 0, 255)),
]


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def channels(rgbw: tuple[int, int, int, int]) -> str:
    red, green, blue, white = rgbw
    return f"red {red:3} green {green:3} blue {blue:3} white {white:3}"


async def wait_for(predicate, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.2)
    return predicate()


async def ask(prompt: str) -> str:
    return (await asyncio.to_thread(input, prompt)).strip()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--hold", type=float, help="seconds per step, no prompts")
    args = parser.parse_args()

    # The library logs its protocol traffic at WARNING, passwords included.
    logging.getLogger("aidot").setLevel(logging.CRITICAL)
    load_env(Path(".env"))
    username = os.environ.get("AIDOT_USERNAME")
    password = os.environ.get("AIDOT_PASSWORD")
    if not username or not password:
        print("Set AIDOT_USERNAME and AIDOT_PASSWORD in .env (the AiDot app login).")
        return 2

    async with aiohttp.ClientSession() as session:
        client = AidotClient(
            session=session,
            country_code=os.environ.get("AIDOT_COUNTRY", "US"),
            username=username,
            password=password,
        )
        await client.async_post_login()
        devices = []
        for house in await client.async_get_houses():
            devices.extend(await client.async_get_devices(house["id"]) or [])
        strip_record = next((d for d in devices if d.get("modelId") == MODEL_ID), None)
        if strip_record is None:
            print(f"No {MODEL_ID} found on this AiDot account.")
            await client.async_cleanup()
            return 2

        # Creating the device client starts the local login to the strip.
        strip = client.get_device_client(strip_record)
        # Count the strip's own status reports, so a step can tell "the strip
        # answered with this value" from "the strip did not answer at all".
        reports = [0]

        def on_report(_status) -> None:
            reports[0] += 1

        strip.on_status_update = on_report
        print(
            f"Connecting to {strip_record.get('name')} at "
            f"{(strip_record.get('properties') or {}).get('ipAddress')}"
        )
        if not await wait_for(lambda: strip.connect_and_login, 15):
            print(
                "Could not log in to the strip on the LAN (port 10000). Is this machine on the home network?"
            )
            await client.async_cleanup()
            return 2
        # The login asks the strip for its current state; give it a moment.
        await asyncio.sleep(1.5)
        before = (strip.status.on, strip.status.dimming, strip.status.rgbw)
        print(
            f"Before: on={before[0]} brightness={before[1]}/255 {channels(before[2])}"
        )

        results = []
        try:
            await strip.async_set_brightness(255)
            for number, (name, rgbw) in enumerate(STEPS, start=1):
                count = reports[0]
                await strip.async_set_rgbw(rgbw)
                answered = await wait_for(lambda c=count: reports[0] > c, 3)
                await asyncio.sleep(0.3)
                reported = strip.status.rgbw if answered else None
                print(f"\nStep {number} of {len(STEPS)}: {name}")
                print(f"  sent:     {channels(rgbw)}")
                print(
                    f"  strip says: {channels(reported) if reported else 'no report within 3 s'}"
                )
                if args.hold:
                    await asyncio.sleep(args.hold)
                    seen = "(unattended)"
                else:
                    seen = await ask("  What does the strip show? ") or "(no answer)"
                results.append((name, rgbw, reported, seen))
        finally:
            on, dimming, rgbw = before
            await strip.async_set_rgbw(rgbw)
            await strip.async_set_brightness(dimming)
            if not on:
                await strip.async_turn_off()
            await asyncio.sleep(1.0)
            print(f"\nRestored: on={on} brightness={dimming}/255 {channels(rgbw)}")
            await strip.close()
            await client.async_cleanup()

    print("\nSummary")
    for name, rgbw, reported, seen in results:
        said = channels(reported) if reported else "no report"
        print(f"  {name:20} strip says {said:40}  you saw: {seen}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
