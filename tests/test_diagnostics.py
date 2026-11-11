"""Tests for Danske Fragtmænd diagnostics."""

from datetime import timedelta
import json
from unittest.mock import MagicMock

from custom_components.danske_fragtmaend.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)
from custom_components.danske_fragtmaend.parcels import normalize_parcel

from .payloads import ACTIVE_CODE, KEY, pickup_sample, registered_keyed

REDACTED = "**REDACTED**"

PLAN_FIELDS = {
    "Latitude",
    "Longitude",
    "Location",
    "ConsignmentComments",
    "PictureList",
    "ConsignmentNumber",
    "Key",
    "SenderReference",
    "Barcode",
    "Sender",
    "Receiver",
    "Initiator",
    "Pickup",
    "Parcelshop",
    "NotificationHistories",
    "BillingInfo",
    "AgreementNumber",
    "Reference",
    "RedeliveryUrl",
    "RelatedBillingNumber",
    "Parent",
}

PERSONAL_VALUES = (
    ACTIVE_CODE,
    KEY,
    "Example Receiver",
    "Example Road 2",
    "Example City",
    "9999",
    "11111111",
    "receiver@example.invalid",
    "shop@example.invalid",
    "Example Contact",
    "Example Shop A/S",
    "Example Parcelshop",
    "00000000000000000000",
    "Door code 4711",
    "55.123456",
    "12.654321",
)


def _entry(parcels: list[dict], data: list[dict]) -> MagicMock:
    entry = MagicMock()
    entry.options = {"parcels": parcels}
    coordinator = entry.runtime_data.coordinator
    coordinator.current_tier_minutes = 45
    coordinator.update_interval = timedelta(minutes=45)
    coordinator.data = data
    coordinator.delivered = []
    coordinator.delivered_codes = set()
    return entry


def test_every_field_the_plan_names_is_redacted():
    assert PLAN_FIELDS <= TO_REDACT


async def test_diagnostics_redact_the_number_the_key_and_every_personal_field(hass):
    raw = pickup_sample()
    # A keyed reply as stored would never keep its key; check it anyway.
    raw["Key"] = {"Key": KEY}
    raw["ConsignmentComments"] = "Door code 4711"
    raw["ConsignmentNoteTraces"][-1].update(
        {"Latitude": 55.123456, "Longitude": 12.654321, "Location": "Example Road 2"}
    )
    parcel = normalize_parcel(raw, tracking_code=ACTIVE_CODE, include_history=True)
    entry = _entry([{"tracking_code": ACTIVE_CODE, "key": KEY}], [parcel])

    result = await async_get_config_entry_diagnostics(hass, entry)
    dumped = json.dumps(result, default=str)

    for value in PERSONAL_VALUES:
        assert value not in dumped, value
    assert result["entry_options"]["parcels"][0] == {
        "tracking_code": REDACTED,
        "key": REDACTED,
    }
    raw_out = result["incoming"][0]["raw"]
    for field in ("Sender", "Receiver", "ConsignmentNumber", "SenderReference"):
        assert raw_out["ConsignmentNote"][field] == REDACTED
    assert raw_out["Parcelshop"] == REDACTED
    assert raw_out["NotificationHistories"] == REDACTED
    assert raw_out["ConsignmentNoteTraces"][0]["ConsignmentNumber"] == REDACTED
    assert raw_out["ColliTraces"][0]["Barcode"] == REDACTED
    # what diagnostics are for survives
    assert result["incoming"][0]["status"] == "in_transit"
    assert raw_out["ConsignmentNoteTraces"][-1]["EventCode"] == "DAT"
    assert raw_out["State"] == "Klar"
    assert result["counts"] == {
        "incoming_active": 1,
        "delivered": 0,
        "skipped_from_fetch": 0,
    }


async def test_diagnostics_redact_the_fixture_as_received(hass):
    entry = _entry([], [{"raw": registered_keyed()}])
    dumped = json.dumps(await async_get_config_entry_diagnostics(hass, entry))
    for value in PERSONAL_VALUES:
        assert value not in dumped, value


async def test_diagnostics_reports_suspended_polling(hass):
    """update_interval None (the full stop) must be visible, not just absent."""
    entry = _entry([], [])
    entry.runtime_data.coordinator.current_tier_minutes = None
    entry.runtime_data.coordinator.update_interval = None

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["polling"] == {
        "tier_minutes": None,
        "update_interval_seconds": None,
        "suspended": True,
    }
