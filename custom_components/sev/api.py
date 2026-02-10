"""SEV REST API client."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from .const import API_BASE_URL

_LOGGER = logging.getLogger(__name__)


class SevApiError(Exception):
    """SEV API exception."""


class SevApiClient:
    """Client for the SEV Customer REST API."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the SEV API client."""
        self._username = username
        self._password = password
        self._session = session
        self._jwt: str | None = None
        self._token_expires: datetime | None = None

    async def _ensure_token(self) -> str:
        """Get valid JWT, refreshing if close to expiry (token valid 4 hours)."""
        now = datetime.utcnow()
        # Refresh when within 30 min of expiry to avoid mid-request expiry
        refresh_cutoff = self._token_expires - timedelta(minutes=30) if self._token_expires else None
        if self._jwt and refresh_cutoff and now < refresh_cutoff:
            return self._jwt
        if self._jwt and self._token_expires and now < self._token_expires:
            try:
                self._jwt = await self._refresh_token()
                self._token_expires = now + timedelta(hours=4)
                return self._jwt
            except SevApiError:
                pass
        self._jwt = await self._login()
        self._token_expires = now + timedelta(hours=4)
        return self._jwt

    async def _login(self) -> str:
        """Authenticate and return JWT."""
        url = f"{API_BASE_URL}/login_and_get_jwt_token"
        headers = {
            "Content-Type": "application/json-patch+json",
            "accept": "*/*",
        }
        payload = {
            "user_name": self._username,
            "password": self._password,
        }
        async with self._session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise SevApiError(f"Login failed: {resp.status} - {text}")
            token = (await resp.text()).strip().strip('"')
            if not token:
                raise SevApiError("Login returned empty token")
            return token

    async def _refresh_token(self) -> str:
        """Refresh JWT using current token."""
        if not self._jwt:
            return await self._login()
        url = f"{API_BASE_URL}/refresh_jwt_key_token"
        headers = {
            "Content-Type": "application/json-patch+json",
            "accept": "*/*",
            "Authorization": f"Bearer {self._jwt}",
        }
        async with self._session.post(url, headers=headers) as resp:
            if resp.status != 200:
                raise SevApiError(f"Refresh failed: {resp.status}")
            token = (await resp.text()).strip().strip('"')
            if not token:
                raise SevApiError("Refresh returned empty token")
            return token

    async def _post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> list[dict] | dict:
        """POST to API with Bearer token."""
        token = await self._ensure_token()
        url = f"{API_BASE_URL}/{endpoint}"
        headers = {
            "Content-Type": "application/json-patch+json",
            "accept": "*/*",
            "Authorization": f"Bearer {token}",
        }
        async with self._session.post(url, json=json_data, headers=headers) as resp:
            if resp.status == 401:
                self._jwt = None
                raise SevApiError("Unauthorized - token may have expired")
            if resp.status != 200:
                text = await resp.text()
                raise SevApiError(f"API error {resp.status}: {text}")
            if json_data is None and "Content-Length" not in headers:
                pass
            return await resp.json()

    async def get_available_meters(self) -> list[dict]:
        """Get all available meters for the authenticated customer."""
        data = await self._post("get_available_meters")
        if not isinstance(data, list):
            raise SevApiError("Unexpected response from get_available_meters")
        return data

    async def get_hourly_kwh_usage(
        self,
        meter_ids: list[int],
        from_date: str,
        to_date: str,
    ) -> list[dict]:
        """Get hourly kWh consumption for the given meters and period."""
        payload = {
            "meters": meter_ids,
            "from_date": from_date,
            "to_date": to_date,
        }
        data = await self._post("hourly_kwh_usage", json_data=payload)
        if not isinstance(data, list):
            raise SevApiError("Unexpected response from hourly_kwh_usage")
        return data

    async def get_estimated_co2(
        self,
        meter_ids: list[int],
        from_date: str,
        to_date: str,
    ) -> list[dict]:
        """Get estimated CO2 (kg) for the given meters and period."""
        payload = {
            "meters": meter_ids,
            "from_date": from_date,
            "to_date": to_date,
        }
        data = await self._post("estimated_CO2", json_data=payload)
        if not isinstance(data, list):
            raise SevApiError("Unexpected response from estimated_CO2")
        return data

    async def get_estimated_cost(
        self,
        meter_ids: list[int],
        from_date: str,
        to_date: str,
    ) -> list[dict]:
        """Get estimated cost (DKK) for the given meters and period."""
        payload = {
            "meters": meter_ids,
            "from_date": from_date,
            "to_date": to_date,
        }
        data = await self._post("estimated_cost", json_data=payload)
        if not isinstance(data, list):
            raise SevApiError("Unexpected response from estimated_cost")
        return data
