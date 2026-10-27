"""Integration tests: load shark_matrix in real Home Assistant with mocked API.

Uses the captured device document as the mocked API response, so the full
component + client code path runs (auth refresh, headers, parsing, entity
creation, state mapping, services) deterministically, with no network.
"""
import base64
import json
import pathlib
import re
from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shark_matrix.api import SkegoxClient
from custom_components.shark_matrix.const import (
    CONF_HOUSEHOLD_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)

FIXTURE = json.loads((pathlib.Path(__file__).parent / "fixture_device.json").read_text())
HOUSEHOLD = FIXTURE["householdId"]
USER_ID = FIXTURE["userId"]
SERIAL = FIXTURE["registry"]["serialNumber"]


def _b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


# A structurally-valid (unsigned) JWT whose 'sub' yields the fixture user id.
FAKE_ID_TOKEN = ".".join(
    [_b64({"alg": "RS256", "typ": "JWT"}), _b64({"sub": f"auth0|{USER_ID}"}), "sig"]
)


def _mock_api(m: aioresponses) -> None:
    m.post(
        "https://login.sharkninja.com/oauth/token",
        payload={
            "id_token": FAKE_ID_TOKEN,
            "access_token": "x",
            "refresh_token": "rotated-rt",
            "expires_in": 86400,
            "token_type": "Bearer",
        },
        repeat=True,
    )
    m.get(
        re.compile(r"https://stakra\.slatra\.thor\.skegox\.com/devicesEndUserController/[^/]+/users/.*"),
        payload={"items": [FIXTURE], "totalCount": 1},
        repeat=True,
    )
    m.get(
        re.compile(r"https://stakra\.slatra\.thor\.skegox\.com/devicesEndUserController/[^/]+/devices/[^/?]+$"),
        payload=FIXTURE,
        repeat=True,
    )


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REFRESH_TOKEN: "seed-refresh-token", CONF_HOUSEHOLD_ID: HOUSEHOLD},
        unique_id="test",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities_load(hass: HomeAssistant) -> None:
    """Component loads, discovers the robot, and maps real state correctly."""
    with aioresponses() as m:
        _mock_api(m)
        await _setup(hass)

    vac = hass.states.get("vacuum.robot_vacuum")
    assert vac is not None, "vacuum entity not created"
    assert vac.state == "docked"
    assert vac.attributes["battery_level"] == 100
    assert vac.attributes["rooms"] == ["Kitchen", "Living Room"]
    assert vac.attributes["error_code"] == 0

    battery = hass.states.get("sensor.robot_vacuum_battery")
    assert battery is not None and int(float(battery.state)) == 100

    err = hass.states.get("sensor.robot_vacuum_error_code")
    assert err is not None and err.state == "0"


async def test_refresh_token_rotation_persisted(hass: HomeAssistant) -> None:
    """A rotated refresh token from the auth server is written back to the entry."""
    with aioresponses() as m:
        _mock_api(m)
        entry = await _setup(hass)
    assert entry.data[CONF_REFRESH_TOKEN] == "rotated-rt"


async def test_start_command(hass: HomeAssistant, monkeypatch) -> None:
    """vacuum.start issues PATCH desired {Operating_Mode: 2}."""
    with aioresponses() as m:
        _mock_api(m)
        await _setup(hass)

        mock = AsyncMock()
        monkeypatch.setattr(SkegoxClient, "async_set_desired", mock)
        await hass.services.async_call(
            "vacuum", "start", {"entity_id": "vacuum.robot_vacuum"}, blocking=True
        )
        await hass.async_block_till_done()

    assert mock.await_count >= 1
    _, desired = mock.await_args.args
    assert desired == {"Operating_Mode": 2}


async def test_return_to_base_command(hass: HomeAssistant, monkeypatch) -> None:
    """vacuum.return_to_base issues PATCH desired {Operating_Mode: 3}."""
    with aioresponses() as m:
        _mock_api(m)
        await _setup(hass)

        mock = AsyncMock()
        monkeypatch.setattr(SkegoxClient, "async_set_desired", mock)
        await hass.services.async_call(
            "vacuum", "return_to_base", {"entity_id": "vacuum.robot_vacuum"}, blocking=True
        )
        await hass.async_block_till_done()

    _, desired = mock.await_args.args
    assert desired == {"Operating_Mode": 3}


async def test_config_flow(hass: HomeAssistant) -> None:
    """The UI config flow validates the token/household and creates an entry."""
    with aioresponses() as m:
        _mock_api(m)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_REFRESH_TOKEN: "my-refresh-token", CONF_HOUSEHOLD_ID: HOUSEHOLD},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert "Robot Vacuum" in result2["title"]
    assert result2["data"][CONF_HOUSEHOLD_ID] == HOUSEHOLD
