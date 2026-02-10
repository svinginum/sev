"""DataUpdateCoordinator for SEV API."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_MINUTES
from .api import SevApiClient, SevApiError

_LOGGER = logging.getLogger(__name__)


def _flatten_meters(data: list[dict]) -> list[dict]:
    """Flatten customer -> installations -> meters into a list of meter dicts with context."""
    meters: list[dict] = []
    for customer in data:
        customer_name = customer.get("customer_name", "")
        for inst in customer.get("installations", []) or []:
            inst_id = inst.get("inst_id")
            address = inst.get("address", "")
            inst_nickname = inst.get("inst_nickname", "")
            for meter in inst.get("meters", []) or []:
                meters.append({
                    "meter_id": meter.get("meter_id"),
                    "meter_name": meter.get("meter_name", ""),
                    "serial_number": meter.get("serial_number", ""),
                    "meter_type": meter.get("meter_type", ""),
                    "address": address,
                    "installation_nickname": inst_nickname,
                    "customer_name": customer_name,
                })
    return meters


def _date_range_today_local() -> tuple[str, str]:
    """Return from_date and to_date for today in local Faroese time (API uses local time)."""
    # Use UTC for simplicity; SEV doc says "local Faroese time" - for exact match you'd use zone.
    now = datetime.utcnow()
    from_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    to_dt = from_dt + timedelta(days=1)
    return (
        from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        to_dt.strftime("%Y-%m-%dT%H:%M:%S"),
    )


class SevCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches SEV data and respects rate limits (10 calls per 5 min)."""

    def __init__(
        self,
        hass,
        username: str,
        password: str,
        session,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self._client = SevApiClient(username=username, password=password, session=session)
        self._meters_flat: list[dict] = []

    @property
    def meters(self) -> list[dict]:
        """Return flattened list of meters (meter_id, meter_name, address, etc.)."""
        return self._meters_flat

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from SEV API. Batches calls to stay under 10/5min."""
        try:
            # 1) Get available meters (1 call)
            raw_meters = await self._client.get_available_meters()
            self._meters_flat = _flatten_meters(raw_meters)
            if not self._meters_flat:
                return {
                    "meters": self._meters_flat,
                    "usage": [],
                    "co2": [],
                    "cost": [],
                }

            meter_ids = [m["meter_id"] for m in self._meters_flat if m.get("meter_id") is not None]
            if not meter_ids:
                return {
                    "meters": self._meters_flat,
                    "usage": [],
                    "co2": [],
                    "cost": [],
                }

            from_date, to_date = _date_range_today_local()

            # 2–4) Usage, CO2, cost (3 calls) for today
            usage = await self._client.get_hourly_kwh_usage(meter_ids, from_date, to_date)
            co2 = await self._client.get_estimated_co2(meter_ids, from_date, to_date)
            cost = await self._client.get_estimated_cost(meter_ids, from_date, to_date)

            return {
                "meters": self._meters_flat,
                "usage": usage,
                "co2": co2,
                "cost": cost,
            }
        except SevApiError as err:
            raise UpdateFailed(f"SEV API error: {err}") from err
