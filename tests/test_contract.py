"""The parcel contract's checks, run over every normalised sample."""

from datetime import datetime

import pytest

from custom_components.danske_fragtmaend.const import ParcelStatus
from custom_components.danske_fragtmaend.parcels import normalize_parcel, parse_iso

from .payloads import (
    active_sample,
    delivered_sample,
    out_for_delivery_sample,
    pickup_sample,
)

CANONICAL_KEYS = [
    "carrier",
    "barcode",
    "sender",
    "receiver",
    "status",
    "raw_status",
    "delivered",
    "delivered_at",
    "planned_from",
    "planned_to",
    "pickup",
    "pickup_point",
    "url",
    "weight",
    "dimensions",
    "history",
    "raw",
]


def _collected() -> dict:
    sample = delivered_sample()
    sample["Parcelshop"] = pickup_sample()["Parcelshop"]
    return sample


def _cancelled() -> dict:
    sample = active_sample()
    sample["State"] = "Annulleret"
    return sample


def _moment_only() -> dict:
    sample = active_sample()
    times = sample["ConsignmentNote"]["DeliveryTime"]
    times["DotIntervalStart"] = times["DotIntervalEnd"] = "2026-11-11T13:00:00"
    return sample


def _date_only() -> dict:
    sample = active_sample()
    sample["ConsignmentNote"]["DeliveryTime"]["ExpectedDeliveryDate"] = "2026-11-11"
    return sample


SAMPLES = {
    "delivered": delivered_sample,
    "active": active_sample,
    "out_for_delivery": out_for_delivery_sample,
    "pickup": pickup_sample,
    "collected": _collected,
    "problem": _cancelled,
    "moment_only": _moment_only,
    "date_only": _date_only,
    "bare": dict,
}


@pytest.fixture(params=SAMPLES)
def parcel(request) -> dict:
    return normalize_parcel(SAMPLES[request.param]())


def test_keys_and_order(parcel):
    assert list(parcel) == CANONICAL_KEYS


def test_delivered_follows_status(parcel):
    assert parcel["delivered"] is (parcel["status"] is ParcelStatus.DELIVERED)


def test_delivered_at_only_when_delivered(parcel):
    if not parcel["delivered"]:
        assert parcel["delivered_at"] is None


def test_planned_window_is_ordered_and_anchored(parcel):
    if parcel["planned_to"] is not None:
        assert parcel["planned_from"] is not None
        assert parse_iso(parcel["planned_to"]) > parse_iso(parcel["planned_from"])


def test_planned_is_empty_when_the_parcel_is_done_or_waiting(parcel):
    if parcel["status"] in (
        ParcelStatus.DELIVERED,
        ParcelStatus.AT_PICKUP_POINT,
        ParcelStatus.RETURNING,
    ):
        assert parcel["planned_from"] is None
        assert parcel["planned_to"] is None


def test_pickup_is_a_bool_and_the_point_needs_it(parcel):
    assert isinstance(parcel["pickup"], bool)
    if not parcel["pickup"]:
        assert parcel["pickup_point"] is None


def test_a_collected_pickup_parcel_stays_pickup():
    parcel = normalize_parcel(_collected())
    assert parcel["status"] is ParcelStatus.DELIVERED
    assert parcel["delivered"] is True
    assert parcel["delivered_at"] is not None
    assert parcel["pickup"] is True
    assert parcel["pickup_point"] == "Example Parcelshop"


def test_a_home_delivery_is_not_pickup():
    parcel = normalize_parcel(delivered_sample())
    assert parcel["pickup"] is False
    assert parcel["pickup_point"] is None


def test_a_moment_ends_at_the_end_of_that_day():
    parcel = normalize_parcel(_moment_only())
    start = datetime.fromisoformat(parcel["planned_from"])
    end = datetime.fromisoformat(parcel["planned_to"])
    assert (start.hour, start.minute) == (13, 0)
    assert (end.hour, end.minute, end.second, end.microsecond) == (23, 59, 59, 0)
    assert end.date() == start.date()
    assert end.utcoffset() == start.utcoffset()


def test_a_date_covers_the_whole_day():
    parcel = normalize_parcel(_date_only())
    start = datetime.fromisoformat(parcel["planned_from"])
    end = datetime.fromisoformat(parcel["planned_to"])
    assert (start.hour, start.minute, start.second) == (0, 0, 0)
    assert (end.hour, end.minute, end.second, end.microsecond) == (23, 59, 59, 0)
    assert start.date() == end.date()
