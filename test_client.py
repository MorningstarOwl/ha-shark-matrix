"""Standalone test for the skegox client against the live API.

Read-only (list + get device). Does NOT send commands.
Usage: pass an id_token (or a refresh token) + household id via env/args.
"""
import asyncio
import importlib.util
import os
import sys
import types

import aiohttp  # noqa: E402

# Load shark_matrix.{const,api} directly, WITHOUT running the package __init__.py
# (which imports homeassistant). This lets us test the client standalone.
_BASE = os.path.join(os.path.dirname(__file__), "custom_components", "shark_matrix")
_pkg = types.ModuleType("shark_matrix")
_pkg.__path__ = [_BASE]
sys.modules["shark_matrix"] = _pkg
for _name in ("const", "api"):
    _spec = importlib.util.spec_from_file_location(
        f"shark_matrix.{_name}", os.path.join(_BASE, f"{_name}.py")
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[f"shark_matrix.{_name}"] = _mod
    _spec.loader.exec_module(_mod)
api = sys.modules["shark_matrix.api"]

HOUSEHOLD = os.environ["HH"]
ID_TOKEN = os.environ.get("IDTOKEN")
REFRESH = os.environ.get("REFRESH")


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        auth = api.SkegoxAuth(session, refresh_token=REFRESH, id_token=ID_TOKEN)
        client = api.SkegoxClient(session, auth, HOUSEHOLD)

        print("user_id:", await auth.async_user_id())
        if REFRESH:
            tok = await auth.async_id_token()
            print("refreshed id_token len:", len(tok), "| new refresh_token:",
                  (auth.refresh_token or "")[:12], "...")

        print("\n-- list_devices --")
        devices = await client.async_list_devices()
        for d in devices:
            print(f"  {d.name} | serial={d.serial} | model={d.model} | online={d.online}")

        if devices:
            serial = devices[0].serial
            print(f"\n-- get_device({serial}) --")
            dev = await client.async_get_device(serial)
            print(f"  name={dev.name} battery={dev.battery} online={dev.online}")
            print(f"  operating_mode={dev.operating_mode} power_mode={dev.power_mode}")
            print(f"  docked={dev.docked} charging={dev.charging} error_code={dev.error_code}")
            print(f"  rooms={dev.rooms}")


asyncio.run(main())
