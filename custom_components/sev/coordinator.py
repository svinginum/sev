"""DataUpdateCoordinator for SEV API."""

from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL_MINUTES
from .api import SevApiClient, SevApiError

_LOGGER = logging.getLogger(__name__)

# API expects dates in local Faroese time
FAROE_TZ = ZoneInfo("Atlantic/Faroe")


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


def _date_range_local(day_offset: int = 0) -> tuple[str, str]:
    """Return from_date and to_date for a day in local Faroese time (API uses local time).
    day_offset=0 is today, day_offset=-1 is yesterday.
    """
    now = datetime.now(FAROE_TZ)
    from_dt = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day_offset))
    to_dt = from_dt + timedelta(days=1)
    return (
        from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        to_dt.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def _date_range_last_month() -> tuple[str, str]:
    """Return from_date and to_date for last calendar month in local Faroese time."""
    now = datetime.now(FAROE_TZ)
    first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 1:
        first_last_month = first_this_month.replace(year=now.year - 1, month=12)
    else:
        first_last_month = first_this_month.replace(month=now.month - 1)
    return (
        first_last_month.strftime("%Y-%m-%dT%H:%M:%S"),
        first_this_month.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def _date_range_this_month() -> tuple[str, str]:
    """Return from_date and to_date for this month so far (1st 00:00 to end of today) in Faroese time."""
    now = datetime.now(FAROE_TZ)
    first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_today = first_this_month + timedelta(days=now.day)  # start of tomorrow
    return (
        first_this_month.strftime("%Y-%m-%dT%H:%M:%S"),
        end_of_today.strftime("%Y-%m-%dT%H:%M:%S"),
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
            empty = {
                "meters": self._meters_flat,
                "usage": [],
                "cost": [],
                "usage_yesterday": [],
                "co2_yesterday": [],
                "cost_yesterday": [],
                "usage_last_month": [],
                "cost_last_month": [],
                "usage_this_month": [],
                "cost_this_month": [],
                "days_elapsed_this_month": 0,
                "days_in_month": 31,
            }
            if not self._meters_flat:
                return empty

            meter_ids = [m["meter_id"] for m in self._meters_flat if m.get("meter_id") is not None]
            if not meter_ids:
                return empty

            from_today, to_today = _date_range_local(0)
            from_yesterday, to_yesterday = _date_range_local(-1)
            _LOGGER.debug(
                "SEV requesting today %s–%s and yesterday %s–%s (Faroese) for meter_ids %s",
                from_today,
                to_today,
                from_yesterday,
                to_yesterday,
                meter_ids,
            )

            # Today: usage, cost only (2 calls) – no CO2 today
            usage_today = await self._client.get_hourly_kwh_usage(meter_ids, from_today, to_today)
            cost_today = await self._client.get_estimated_cost(meter_ids, from_today, to_today)

            # Yesterday: usage, cost, CO2 (3 calls)
            usage_yesterday = await self._client.get_hourly_kwh_usage(
                meter_ids, from_yesterday, to_yesterday
            )
            co2_yesterday = await self._client.get_estimated_co2(
                meter_ids, from_yesterday, to_yesterday
            )
            cost_yesterday = await self._client.get_estimated_cost(
                meter_ids, from_yesterday, to_yesterday
            )

            # Last month: usage, cost only (2 calls) – no CO2 last month
            from_last_month, to_last_month = _date_range_last_month()
            usage_last_month = await self._client.get_hourly_kwh_usage(
                meter_ids, from_last_month, to_last_month
            )
            cost_last_month = await self._client.get_estimated_cost(
                meter_ids, from_last_month, to_last_month
            )

            # This month so far: usage, cost (2 calls) – for "estimated til end of month"
            from_this_month, to_this_month = _date_range_this_month()
            _LOGGER.debug(
                "SEV requesting this month %s–%s (Faroese) for meter_ids %s",
                from_this_month,
                to_this_month,
                meter_ids,
            )
            usage_this_month = await self._client.get_hourly_kwh_usage(
                meter_ids, from_this_month, to_this_month
            )
            cost_this_month = await self._client.get_estimated_cost(
                meter_ids, from_this_month, to_this_month
            )

            now_faroe = datetime.now(FAROE_TZ)
            days_elapsed = now_faroe.day
            days_in_month = calendar.monthrange(now_faroe.year, now_faroe.month)[1]

            for name, lst in (
                ("usage_today", usage_today),
                ("usage_yesterday", usage_yesterday),
                ("usage_last_month", usage_last_month),
                ("usage_this_month", usage_this_month),
                ("cost_today", cost_today),
            ):
                total = sum(len(item.get("readings") or []) for item in lst)
                _LOGGER.debug("SEV API %s: %s readings", name, total)

            return {
                "meters": self._meters_flat,
                "usage": usage_today,
                "cost": cost_today,
                "usage_yesterday": usage_yesterday,
                "co2_yesterday": co2_yesterday,
                "cost_yesterday": cost_yesterday,
                "usage_last_month": usage_last_month,
                "cost_last_month": cost_last_month,
                "usage_this_month": usage_this_month,
                "cost_this_month": cost_this_month,
                "days_elapsed_this_month": days_elapsed,
                "days_in_month": days_in_month,
            }
        except SevApiError as err:
            raise UpdateFailed(f"SEV API error: {err}") from err
