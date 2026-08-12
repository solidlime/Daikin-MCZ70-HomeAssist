"""Daikin MCZ70 Air Purifier integration.

Reads state via the local device API (no auth, 2s polling).
Writes via the Daikin Smart DB cloud API (Bearer auth); local writes are
disabled on this device (404).

Derived from https://github.com/hgn32/daikin-aircleaner (MIT license).
"""

from __future__ import annotations

import asyncio
import logging
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CLOUD_API_BASE,
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_CODE,
    CONF_ID,
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_REFRESH_TOKEN,
    CONF_SPW,
    CONF_APW,
    CONF_TERMINAL_ID,
    CONF_TOKEN_EXPIRY,
    CONF_UUID,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.FAN, Platform.BINARY_SENSOR, Platform.SELECT, Platform.SENSOR]

_RETRY_DELAYS = (1, 2, 4)

_WRITE_TIMEOUT = aiohttp.ClientTimeout(total=10)
_WRITE_RATE_LIMIT = timedelta(seconds=30)
_TOKEN_SAFETY_MARGIN = timedelta(seconds=60)
_REFRESH_LOOP_RETRY = 300.0
_REFRESH_LOOP_MAX_WAIT = 3600.0

_LOGIN_URL = f"{CLOUD_API_BASE}/premise/dsiot/login"
_TOKEN_URL = f"{CLOUD_API_BASE}/premise/dsiot/token"


class CloudError(Exception):
    """Cloud API error."""


def _parse_key_value(text: str) -> dict:
    """Parse a Daikin 'key=value,key=value' response body."""
    result = {}
    for pair in text.split(","):
        if "=" not in pair:
            continue
        key, val = pair.split("=", 1)
        result[key] = urllib.parse.unquote(val, encoding="UTF-8")
    return result


def current_params(coordinator) -> dict:
    """Full control info from the latest coordinator data (single source of truth)."""
    d = coordinator.data or {}
    return {
        "pow": d.get("pow", "1"),
        "mode": d.get("mode", "0"),
        "airvol": d.get("airvol", "0"),
        "humd": d.get("humd", "0"),
    }


def device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Daikin MCZ70",
        manufacturer="Daikin",
        model="MCZ704A",
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    local = LocalAPI(entry.data[CONF_IP_ADDRESS], async_get_clientsession(hass))
    cloud = CloudAPI(hass, entry, async_get_clientsession(hass))

    async def async_update_data() -> dict:
        try:
            return await local.get()
        except Exception as err:
            raise UpdateFailed(err) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=DEFAULT_UPDATE_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "local": local,
        "cloud": cloud,
        "coordinator": coordinator,
        "cloud_refresh_task": asyncio.create_task(cloud.token_refresh_loop()),
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    task = hass.data[DOMAIN][entry.entry_id].get("cloud_refresh_task")
    if task is not None:
        task.cancel()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class LocalAPI:
    """Local device API. Read-only; set endpoints return 404 on this device."""

    def __init__(self, address: str, session: aiohttp.ClientSession) -> None:
        self._address = address
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=5)

    async def _get(self, url: str) -> str:
        last_err: Exception
        for i, delay in enumerate((0, *_RETRY_DELAYS)):
            if delay:
                await asyncio.sleep(delay)
            try:
                async with self._session.get(url, timeout=self._timeout) as resp:
                    resp.raise_for_status()
                    return await resp.text()
            except Exception as err:
                last_err = err
                _LOGGER.debug("Request %s attempt %d failed: %s", url, i + 1, err)
        raise last_err

    async def get_basic_info(self) -> dict | None:
        """Fetch /common/basic_info (used by the config flow)."""
        try:
            text = await self._get(f"http://{self._address}/common/basic_info")
            return _parse_key_value(text)
        except Exception as err:
            _LOGGER.error("Failed to get basic_info: %s", err)
        return None

    async def get(self) -> dict:
        response: dict = {}
        for ep in ("get_control_info", "get_unit_status", "get_sensor_info", "get_device_setting"):
            try:
                text = await self._get(f"http://{self._address}/cleaner/{ep}")
            except Exception as err:
                _LOGGER.error("Failed to fetch %s: %s", ep, err)
                continue
            response.update(_parse_key_value(text))
        response.setdefault("led_dsp", "0")
        return response


class CloudAPI:
    """Daikin Smart DB cloud API. Used for all writes.

    Tokens are persisted in the config entry data via async_update_entry,
    so they survive restarts. A background task refreshes the access token
    before it expires (expiry - 60s); writes also refresh on demand and
    re-login with the saved authorization code if a 401 occurs.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry | None,
        session: aiohttp.ClientSession,
        data: dict | None = None,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._session = session
        self._data = data or {}
        self._lock = asyncio.Lock()
        self._last_write_ts = 0.0
        entry_data = entry.data if entry is not None else self._data
        self._access_token: str | None = entry_data.get(CONF_ACCESS_TOKEN)
        self._refresh_token: str | None = entry_data.get(CONF_REFRESH_TOKEN)
        expiry = entry_data.get(CONF_TOKEN_EXPIRY)
        self._expiry: datetime | None = datetime.fromisoformat(expiry) if expiry else None

    def _conf(self, key: str) -> str:
        source = self._entry.data if self._entry is not None else self._data
        return source.get(key, "")

    async def _persist_tokens(self) -> None:
        if self._entry is None:
            return
        data = dict(self._entry.data)
        data[CONF_ACCESS_TOKEN] = self._access_token
        data[CONF_REFRESH_TOKEN] = self._refresh_token
        data[CONF_TOKEN_EXPIRY] = self._expiry.isoformat()
        await self._hass.config_entries.async_update_entry(self._entry, data=data)

    async def _apply_tokens(self, tokens: dict) -> None:
        access = tokens.get("access_token")
        if not access:
            raise CloudError(f"no access_token in response: {tokens}")
        self._access_token = access
        self._refresh_token = tokens.get("refresh_token") or self._refresh_token
        expires_in = int(tokens.get("expires_in", 3600))
        self._expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        await self._persist_tokens()
        _LOGGER.debug("Cloud tokens updated, access token valid for %ss", expires_in)

    async def login(self) -> None:
        """Authenticate with the saved authorization code."""
        body = {
            "grant_type": "authorization_code",
            "code": self._conf(CONF_CODE),
            "client_id": self._conf(CONF_CLIENT_ID),
            "uuid": self._conf(CONF_UUID),
            "client_secret": self._conf(CONF_CLIENT_SECRET),
        }
        try:
            async with self._session.post(_LOGIN_URL, json=body, timeout=_WRITE_TIMEOUT) as resp:
                resp.raise_for_status()
                tokens = await resp.json()
        except Exception as err:
            raise CloudError(f"login failed: {err}") from err
        await self._apply_tokens(tokens)

    async def _refresh(self) -> None:
        if not self._refresh_token:
            raise CloudError("no refresh token available")
        body = {"grant_type": "refresh_token", "refresh_token": self._refresh_token}
        try:
            async with self._session.post(_TOKEN_URL, json=body, timeout=_WRITE_TIMEOUT) as resp:
                resp.raise_for_status()
                tokens = await resp.json()
        except Exception as err:
            raise CloudError(f"token refresh failed: {err}") from err
        await self._apply_tokens(tokens)

    async def _ensure_token(self) -> None:
        """Refresh when close to expiry, otherwise login. Caller holds the lock."""
        now = datetime.now(timezone.utc)
        if self._access_token and self._expiry and now < self._expiry - _TOKEN_SAFETY_MARGIN:
            return
        if self._refresh_token:
            try:
                await self._refresh()
                return
            except Exception as err:
                _LOGGER.warning("Cloud token refresh failed, trying login: %s", err)
        try:
            await self.login()
        except Exception as err:
            _LOGGER.error(
                "Cloud login failed: %s. Re-enter the cloud credentials via "
                "Settings > Devices > Daikin MCZ70 > Options.",
                err,
            )
            raise

    async def _reauthenticate(self) -> None:
        """Force token renewal on 401 (refresh, falling back to login)."""
        self._access_token = None
        await self._ensure_token()

    async def _authorized_get(self, path: str, params: dict) -> str:
        await self._ensure_token()
        for attempt in range(3):
            query = {
                **params,
                "id": self._conf(CONF_ID),
                "spw": self._conf(CONF_SPW),
                "terminalid": self._conf(CONF_TERMINAL_ID),
                "port": self._conf(CONF_PORT),
            }
            if apw := self._conf(CONF_APW):
                query["apw"] = apw
            self._last_write_ts = time.monotonic()
            try:
                async with self._session.get(
                    f"{CLOUD_API_BASE}{path}",
                    params=query,
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=_WRITE_TIMEOUT,
                ) as resp:
                    if resp.status == 401:
                        if attempt < 2:
                            await self._reauthenticate()
                            continue
                        _LOGGER.error(
                            "Cloud authentication failed after refresh/login retries. "
                            "Re-enter the cloud credentials via Settings > Devices > Daikin MCZ70 > Options."
                        )
                        raise CloudError("cloud authentication failed")
                    resp.raise_for_status()
                    text = await resp.text()
                    if text != "ret=OK":
                        raise CloudError(f"{path} returned {text!r}")
                    return text
            except CloudError:
                raise
            except Exception as err:
                raise CloudError(f"{path} request failed: {err}") from err
        raise CloudError("unreachable")

    async def set_control_info(self, params: dict) -> str:
        """Write pow/mode/airvol/humd via the cloud API."""
        async with self._lock:
            await self._wait_rate_limit()
            return await self._authorized_get("/cleaner/set_control_info", params)

    async def set_device_setting(self, params: dict) -> str:
        """Write device settings (e.g. led_dsp) via the cloud API."""
        async with self._lock:
            await self._wait_rate_limit()
            return await self._authorized_get("/cleaner/set_device_setting", params)

    async def _wait_rate_limit(self) -> None:
        remaining = _WRITE_RATE_LIMIT.total_seconds() - (time.monotonic() - self._last_write_ts)
        if remaining > 0:
            _LOGGER.debug("Cloud write rate limited: waiting %.1fs", remaining)
            await asyncio.sleep(remaining)

    def _seconds_until_refresh(self) -> float:
        if self._access_token and self._expiry:
            target = self._expiry - _TOKEN_SAFETY_MARGIN
            delta = (target - datetime.now(timezone.utc)).total_seconds()
            if delta > 0:
                return min(delta, _REFRESH_LOOP_MAX_WAIT)
        return _REFRESH_LOOP_RETRY

    async def token_refresh_loop(self) -> None:
        """Proactively refresh the access token before it expires."""
        while True:
            await asyncio.sleep(self._seconds_until_refresh())
            try:
                async with self._lock:
                    await self._ensure_token()
            except Exception as err:
                _LOGGER.warning("Token refresh task failed: %s", err)
