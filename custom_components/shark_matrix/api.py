"""Async client for the SharkNinja 'skegox' AWS IoT backend.

Reverse-engineered from the SharkClean Android app 6.30.0. Covers the newer
AWS-hosted backend (``*.skegox.com``) used by migrated devices such as the
Shark Matrix RV2500 / RV230B. This is NOT the legacy Ayla backend that
``sharkiq`` talks to.

Auth: an Auth0 refresh token is exchanged for a short-lived ``id_token`` (JWT),
which is sent as a Bearer token together with a static ``x-api-key`` and a
timestamp. There is no request signing.
"""
from __future__ import annotations

import base64
import datetime
import json
import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_BASE,
    API_KEY,
    AUTH_HOST,
    CALLER,
    CLIENT_ID,
    OAUTH_SCOPE,
    OP_PAUSE,
    OP_RETURN,
    OP_START,
    OP_STOP,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class SkegoxAuthError(Exception):
    """Authentication / token refresh failed."""


class SkegoxApiError(Exception):
    """A skegox API call failed."""


def _sn_date() -> str:
    """x-sn-date: ISO-8601 'basic' UTC, e.g. 20261027T201410Z."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _jwt_claims(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


class SkegoxAuth:
    """Holds the Auth0 refresh token and mints id_tokens on demand.

    Pass ``id_token`` directly (without a refresh token) only for testing.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        refresh_token: str | None = None,
        *,
        id_token: str | None = None,
        client_id: str = CLIENT_ID,
    ) -> None:
        self._session = session
        self._refresh_token = refresh_token
        self._client_id = client_id
        self._id_token = id_token
        self._expires_at = time.time() + 3600 if id_token else 0.0
        self._user_id: str | None = None

    @property
    def refresh_token(self) -> str | None:
        """Current refresh token (updated if the server rotates it)."""
        return self._refresh_token

    async def async_id_token(self) -> str:
        """Return a valid id_token, refreshing if necessary."""
        if self._id_token and time.time() < self._expires_at - 60:
            return self._id_token
        if not self._refresh_token:
            raise SkegoxAuthError("id_token expired and no refresh token available")
        await self._async_refresh()
        return self._id_token  # type: ignore[return-value]

    async def _async_refresh(self) -> None:
        url = f"https://{AUTH_HOST}/oauth/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self._client_id,
            "refresh_token": self._refresh_token,
            "scope": OAUTH_SCOPE,
        }
        try:
            async with self._session.post(
                url, json=payload, timeout=REQUEST_TIMEOUT
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    raise SkegoxAuthError(f"token refresh failed ({resp.status}): {data}")
        except aiohttp.ClientError as err:
            raise SkegoxAuthError(f"token refresh connection error: {err}") from err

        if "id_token" not in data:
            raise SkegoxAuthError(f"token refresh response had no id_token: {data}")
        self._id_token = data["id_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
        # Auth0 refresh-token rotation: keep the new one.
        if data.get("refresh_token"):
            self._refresh_token = data["refresh_token"]
        self._user_id = None

    async def async_user_id(self) -> str:
        """User id = the Auth0 'sub' with the 'auth0|' prefix stripped."""
        if self._user_id is None:
            token = await self.async_id_token()
            sub = _jwt_claims(token).get("sub", "")
            self._user_id = sub.split("|", 1)[-1]
        return self._user_id


class SharkDevice:
    """Thin view over a skegox device document."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    # --- identity ---
    @property
    def serial(self) -> str:
        return self.raw.get("registry", {}).get("serialNumber") or self.raw.get("serialNumber", "")

    @property
    def name(self) -> str:
        return self.raw.get("metadata", {}).get("deviceName") or self.serial

    @property
    def model(self) -> str:
        reg = self.raw.get("registry", {})
        return reg.get("modelNumber") or reg.get("Device_Model_Number", "")

    @property
    def firmware(self) -> str:
        return self.raw.get("registry", {}).get("Robot_Firmware_Version", "")

    @property
    def mac(self) -> str:
        return self.raw.get("registry", {}).get("macAddress", "")

    @property
    def online(self) -> bool:
        return bool(self.raw.get("connectivityStatus", {}).get("connected", False))

    # --- shadow access ---
    @property
    def _reported(self) -> dict[str, Any]:
        return self.raw.get("shadow", {}).get("properties", {}).get("reported", {})

    def prop(self, name: str, default: Any = None) -> Any:
        """Read a reported shadow property's value (unwrapping {value,updatedAt})."""
        val = self._reported.get(name)
        if isinstance(val, dict) and "value" in val:
            return val["value"]
        return default if val is None else val

    # --- common state ---
    @property
    def _telemetry(self) -> dict[str, Any]:
        return self.raw.get("telemetry", {})

    @property
    def battery(self) -> int | None:
        # Battery_Capacity is reported under telemetry (bare value), not the shadow.
        v = self._telemetry.get("Battery_Capacity")
        if v is None:
            v = self.prop("Battery_Capacity")
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def rssi(self) -> int | None:
        v = self._telemetry.get("RSSI")
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def operating_mode(self) -> int | None:
        v = self.prop("Operating_Mode")
        return int(v) if v is not None else None

    @property
    def power_mode(self) -> int | None:
        v = self.prop("Power_Mode")
        return int(v) if v is not None else None

    @property
    def docked(self) -> bool:
        return bool(self.prop("DockedStatus", False))

    @property
    def charging(self) -> bool:
        return bool(self.prop("Charging_Status", False))

    @property
    def error_code(self) -> int:
        try:
            return int(self.prop("Error_Code", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def rooms(self) -> list[str]:
        """Parsed from Robot_Room_List like '4014FFE9:Kitchen:Living Room'."""
        raw = self.prop("Robot_Room_List", "") or ""
        parts = str(raw).split(":")
        return [p for p in parts[1:] if p] if len(parts) > 1 else []


class SkegoxClient:
    """Client for one household."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth: SkegoxAuth,
        household_id: str,
    ) -> None:
        self._session = session
        self._auth = auth
        self._household = household_id

    async def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {await self._auth.async_id_token()}",
            "x-api-key": API_KEY,
            "x-iotn-caller": CALLER,
            "x-sn-date": _sn_date(),
            "accept-encoding": "gzip, deflate",
            "accept": "application/json",
            "user-agent": USER_AGENT,
        }

    async def _request(
        self, method: str, path: str, *, params=None, json_body=None
    ) -> Any:
        url = f"{API_BASE}{path}"
        headers = await self._headers()
        if json_body is not None:
            headers["content-type"] = "application/json"
        try:
            async with self._session.request(
                method, url, headers=headers, params=params, json=json_body,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                text = await resp.text()
                if resp.status == 401:
                    raise SkegoxAuthError(f"401 from {path}: {text[:200]}")
                if resp.status >= 400:
                    raise SkegoxApiError(f"{resp.status} from {method} {path}: {text[:300]}")
                return json.loads(text) if text else {}
        except aiohttp.ClientError as err:
            raise SkegoxApiError(f"connection error on {method} {path}: {err}") from err

    async def async_list_devices(self) -> list[SharkDevice]:
        """List devices in the household (summary; includeShadow=false)."""
        user_id = await self._auth.async_user_id()
        data = await self._request(
            "GET",
            f"/devicesEndUserController/{self._household}/users/{user_id}",
            params={
                "includeRegistry": "true",
                "includeConnectivityStatus": "true",
                "includeShadow": "false",
            },
        )
        items = data.get("items", data if isinstance(data, list) else [])
        return [SharkDevice(it) for it in items]

    async def async_get_device(self, serial: str) -> SharkDevice:
        """Full device document including the shadow (reported + desired)."""
        data = await self._request(
            "GET", f"/devicesEndUserController/{self._household}/devices/{serial}"
        )
        return SharkDevice(data)

    async def async_set_desired(self, serial: str, desired: dict[str, Any]) -> SharkDevice:
        """Write bare values into the device's desired shadow (the control path)."""
        body = {"shadow": {"properties": {"desired": desired}}}
        data = await self._request(
            "PATCH", f"/devicesEndUserController/{self._household}/devices/{serial}",
            json_body=body,
        )
        return SharkDevice(data)

    # --- high-level commands ---
    async def async_start(self, serial: str) -> None:
        await self.async_set_desired(serial, {"Operating_Mode": OP_START})

    async def async_pause(self, serial: str) -> None:
        await self.async_set_desired(serial, {"Operating_Mode": OP_PAUSE})

    async def async_stop(self, serial: str) -> None:
        await self.async_set_desired(serial, {"Operating_Mode": OP_STOP})

    async def async_return_to_base(self, serial: str) -> None:
        await self.async_set_desired(serial, {"Operating_Mode": OP_RETURN})

    async def async_set_power_mode(self, serial: str, power_mode: int) -> None:
        await self.async_set_desired(serial, {"Power_Mode": power_mode})
