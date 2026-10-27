# Shark Matrix (AWS) — Home Assistant custom integration

Control a **Shark Matrix RV2500 / RV230B** (and likely other SharkNinja robots on
the newer **AWS "skegox" backend**) from Home Assistant.

This is **not** the Ayla backend that the built-in `sharkiq` / HA "Shark IQ"
integration uses. Devices migrated to SharkNinja's AWS IoT platform don't appear
in Ayla at all, so `sharkiq` can't see them — hence this integration. It was built
from a clean-room reverse-engineering of the SharkClean 6.30.0 Android app.

## What works
- Vacuum entity: **start, pause, stop, return-to-dock, set suction (fan speed)**, state, battery.
- Sensors: battery %, error code, Wi-Fi signal (RSSI).
- Cloud polling every 30 s (`GET` device shadow); commands via `PATCH` desired shadow.

## How it talks to the robot
- **Auth:** an Auth0 *refresh token* is exchanged for a short-lived `id_token` (JWT),
  sent as `Authorization: Bearer` with a static `x-api-key` and a timestamp. No request signing.
- **Read:** `GET …/devices/{serial}` → shadow `reported` state.
- **Control:** `PATCH …/devices/{serial}` with `{"shadow":{"properties":{"desired":{"Operating_Mode":2}}}}`.
- `Operating_Mode`: `0`=stop, `1`=pause, `2`=start, `3`=return to dock.

## Install
Copy `custom_components/shark_matrix/` into your HA `config/custom_components/`
directory and restart Home Assistant. Then **Settings → Devices & Services → Add
Integration → “Shark Matrix (AWS)”.**

You'll be asked for two things:

### 1. Auth0 refresh token
Run the included helper (stdlib only, run it anywhere with Python 3):
```bash
python3 get_credentials.py
```
It prints a login URL — open it in your browser, sign in to SharkClean (you clear
Cloudflare/2FA yourself), then paste back the `com.sharkninja.shark://…?code=…`
URL the browser tries to open. It prints your `refresh_token`.

(Password/ROPC grants are blocked by Auth0 bot detection, so this interactive
login is the supported way to mint a token. Use a token you obtained **for this
purpose** — Auth0 rotates refresh tokens, so sharing one session's token between
HA and the phone app can log the other out. A separate login for HA avoids that.)

### 2. Household ID
This is the SharkNinja "household" your robot belongs to (looks like
`01EXAMPLEHOUSEHOLDID000000`). The app caches it and there's no public discovery
endpoint yet, so for now you provide it. You can read it from a quick capture of
the app's API traffic (any request path contains `/devicesEndUserController/{householdId}/…`),
or from the project's reverse-engineering notes if it was captured for your account.
*(Auto-discovery is a TODO — see below.)*

Devices (serials) are then discovered automatically within the household.

## Known limitations / TODO
- **Household auto-discovery**: not implemented (no discovery endpoint found yet).
- **`Power_Mode` → suction mapping** (Eco/Normal/Max ↔ ints) is inferred; `Normal`
  was observed as `0`. Verify and adjust `POWER_MODES` in `const.py` if needed.
- **Realtime**: uses polling. The app's WebSocket (`bifrost.skegox.com`) carried no
  app-level messages in captures, so polling is the reliable path.
- Room/zone cleaning (`Areas_To_Clean` / `CleanRoomCommand`), maps, and schedules
  are exposed in the shadow but not yet surfaced as HA controls.

## Files
```
custom_components/shark_matrix/
  api.py          skegox client: auth refresh, GET device, PATCH desired, device model
  coordinator.py  polling DataUpdateCoordinator
  __init__.py     setup/unload, device discovery, refresh-token persistence
  config_flow.py  UI config (refresh token + household id)
  vacuum.py       the robot vacuum entity
  sensor.py       battery / error / rssi sensors
  entity.py       shared base entity + device info
  const.py        endpoints, keys, enums
get_credentials.py   one-time refresh-token helper (PKCE login)
test_client.py       standalone read-only client test (set HH + IDTOKEN/REFRESH env)
tests/               Home Assistant integration tests (pytest-homeassistant-custom-component)
```

## Testing
The integration is exercised inside real Home Assistant (loaded as a custom
component) with the API mocked from a captured device document:
```bash
uv venv --python 3.13 .venv-ha
uv pip install --python .venv-ha/bin/python pytest-homeassistant-custom-component aioresponses
.venv-ha/bin/python -m pytest tests/ -v
```
Covered: config flow, entity creation + state mapping, start / return-to-base
commands, and refresh-token rotation persistence. (The live API itself is
verified separately by `test_client.py`, which hits the real endpoint.)

## Disclaimer
Unofficial, not affiliated with SharkNinja. Uses a private API that may change at
any time. For personal use with your own account/device.
