"""Tests for the pure parcel-mapping helpers.

These need no Home Assistant instance: ``parcels.py`` is free of I/O, so the
carrier mapping is tested as plain functions.
"""

from datetime import UTC, datetime, timedelta
import json
import logging

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.danske_fragtmaend.const import (
    CAPABILITIES,
    CONF_DELIVERED_FILTER_AMOUNT,
    CONF_DELIVERED_FILTER_TYPE,
    DOMAIN,
    KNOWN_CAPABILITIES,
    PENDING_CAPABILITIES,
    ParcelStatus,
)
from custom_components.danske_fragtmaend.parcels import (
    apply_delivered_filter,
    check_shape,
    map_trace_status,
    normalize_parcel,
    parse_carrier_time,
    parse_iso,
    sort_parcels_by_ts,
)

from .payloads import (
    ACTIVE_CODE,
    KEY,
    active_sample,
    delivered_keyed,
    delivered_sample,
    keyless,
    out_for_delivery_sample,
    pickup_sample,
    registered_keyed,
    trace,
)


def _with_traces(*rows: dict, state: str = "Klar") -> dict:
    raw = registered_keyed()
    raw["ConsignmentNoteTraces"] = list(rows)
    raw["State"] = state
    return raw


# ---------------------------------------------------------------------------
# status map
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1, ParcelStatus.REGISTERED),
        (2, ParcelStatus.IN_TRANSIT),
        (3, ParcelStatus.DELIVERED),
        (4, ParcelStatus.PROBLEM),
        (5, ParcelStatus.IN_TRANSIT),
        (7, ParcelStatus.PROBLEM),
    ],
)
def test_map_trace_status_known(code, expected):
    assert map_trace_status(code) == expected


@pytest.mark.parametrize("code", [0, 8, None, "2", True])
def test_map_trace_status_unmapped_is_none_and_warns(code, caplog):
    with caplog.at_level(logging.WARNING):
        assert map_trace_status(code) is None
    assert "unrecognised_status.yml" in caplog.text


def test_unmapped_status_warns_only_once(caplog):
    with caplog.at_level(logging.WARNING):
        map_trace_status(9)
        map_trace_status(9)
    assert caplog.text.count("Status=9") == 1


def test_registered_fixture_dat_inherits_into_registered():
    """The only trace seen live: Status 6 ``DAT`` as the first row."""
    parcel = normalize_parcel(registered_keyed(), include_history=True)
    assert parcel["status"] == ParcelStatus.REGISTERED
    assert parcel["history"][0]["status"] == ParcelStatus.REGISTERED
    assert parcel["raw_status"] == (
        "Vi har modtaget information om din forsendelse fra afsender."
    )


def test_status_6_inherits_the_previous_row_not_registered():
    """Band trap: an information row after movement must not reset the parcel."""
    raw = _with_traces(
        trace(6, "2026-11-09T10:00:00"),
        trace(2, "2026-11-10T06:00:00", "UND", "Undervejs"),
        trace(6, "2026-11-10T07:00:00", "DO1", "Leveringstid booket"),
    )
    parcel = normalize_parcel(raw, include_history=True)
    assert parcel["status"] == ParcelStatus.IN_TRANSIT
    assert [entry["status"] for entry in parcel["history"]] == [
        ParcelStatus.REGISTERED,
        ParcelStatus.IN_TRANSIT,
        ParcelStatus.IN_TRANSIT,
    ]
    assert parcel["raw_status"] == "Leveringstid booket"


def test_status_6_after_a_problem_stays_a_problem():
    raw = _with_traces(
        trace(4, "2026-11-10T06:00:00", "FEJ", "Fejl"),
        trace(6, "2026-11-10T07:00:00"),
    )
    assert normalize_parcel(raw)["status"] == ParcelStatus.PROBLEM


def test_delayed_is_in_transit_not_problem():
    raw = _with_traces(trace(5, "2026-11-10T06:00:00", "FOR", "Forsinket"))
    assert normalize_parcel(raw)["status"] == ParcelStatus.IN_TRANSIT


def test_traces_are_sorted_by_date_before_walking():
    raw = _with_traces(
        trace(2, "2026-11-10T06:00:00", "UND", "Undervejs"),
        trace(6, "2026-11-09T10:00:00"),
    )
    parcel = normalize_parcel(raw, include_history=True)
    assert parcel["status"] == ParcelStatus.IN_TRANSIT
    assert parcel["history"][0]["status"] == ParcelStatus.REGISTERED


def test_equal_dates_keep_their_order():
    raw = _with_traces(
        trace(2, "2026-11-10T06:00:00", "A", "first"),
        trace(4, "2026-11-10T06:00:00", "B", "second"),
    )
    assert normalize_parcel(raw)["raw_status"] == "second"


def test_unmapped_newest_status_falls_back_to_newest_mappable_row(caplog):
    raw = _with_traces(
        trace(2, "2026-11-10T06:00:00", "UND", "Undervejs"),
        trace(42, "2026-11-10T08:00:00", "NEW", "Noget nyt"),
    )
    with caplog.at_level(logging.WARNING):
        parcel = normalize_parcel(raw, include_history=True)
    assert parcel["status"] == ParcelStatus.IN_TRANSIT
    assert parcel["history"][-1]["status"] == ParcelStatus.UNKNOWN
    assert parcel["raw_status"] == "Noget nyt"
    assert "Status=42" in caplog.text


def test_only_unmapped_rows_is_unknown(caplog):
    raw = _with_traces(trace(42, "2026-11-10T08:00:00", "NEW", "Noget nyt"))
    assert normalize_parcel(raw)["status"] == ParcelStatus.UNKNOWN


def test_cancelled_state_is_problem():
    raw = _with_traces(trace(6, "2026-11-09T10:00:00"), state="Annulleret")
    assert normalize_parcel(raw)["status"] == ParcelStatus.PROBLEM


def test_cancelled_status_7_is_problem():
    raw = _with_traces(trace(7, "2026-11-10T06:00:00", "ANN", "Annulleret"))
    assert normalize_parcel(raw)["status"] == ParcelStatus.PROBLEM


def test_unseen_state_word_and_event_code_warn_once(caplog):
    raw = _with_traces(trace(2, "2026-11-10T06:00:00", "UND", "x"), state="Leveret")
    with caplog.at_level(logging.WARNING):
        normalize_parcel(raw)
        normalize_parcel(raw)
    assert caplog.text.count("State='Leveret'") == 1
    assert caplog.text.count("EventCode='UND'") == 1


def test_known_state_and_event_code_are_silent(caplog):
    with caplog.at_level(logging.WARNING):
        normalize_parcel(registered_keyed())
    assert caplog.text == ""


# ---------------------------------------------------------------------------
# timestamps
# ---------------------------------------------------------------------------


def test_carrier_times_are_copenhagen_local():
    assert parse_carrier_time("2026-11-09T14:42:30", "f").isoformat() == (
        "2026-11-09T14:42:30+01:00"
    )
    assert parse_carrier_time("2026-07-01T12:00:00", "f").isoformat() == (
        "2026-07-01T12:00:00+02:00"
    )
    assert parse_carrier_time("2026-07-01T12:00:00Z", "f").tzinfo == UTC


@pytest.mark.parametrize("value", [None, "", "0001-01-01T00:00:00"])
def test_carrier_time_blanks_and_year_one_are_none(value, caplog):
    with caplog.at_level(logging.WARNING):
        assert parse_carrier_time(value, "f") is None
    assert caplog.text == ""


def test_unparseable_carrier_time_warns_with_the_field_only(caplog):
    with caplog.at_level(logging.WARNING):
        assert parse_carrier_time("tomorrow-ish", "DeliveryTime.X") is None
    assert "unparseable date in DeliveryTime.X" in caplog.text
    assert "tomorrow-ish" not in caplog.text


def test_parse_iso_handles_z_naive_and_garbage():
    assert parse_iso("2026-04-29T13:12:42Z").tzinfo is not None
    assert parse_iso("2026-04-29T13:12:42").tzinfo == UTC
    assert parse_iso("not-a-date") is None
    assert parse_iso(None) is None


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


def test_history_never_reads_the_unscanned_colli_row():
    parcel = normalize_parcel(registered_keyed(), include_history=True)
    assert len(parcel["history"]) == 1
    assert all(entry["raw_status"] != "ingen skanninger" for entry in parcel["history"])
    assert all(not entry["timestamp"].startswith("0001") for entry in parcel["history"])


def test_history_caps_to_the_last_20_rows():
    rows = [
        trace(2, f"2026-10-{day:02d}T10:00:00", "UND", f"d{day}")
        for day in range(1, 26)
    ]
    history = normalize_parcel(_with_traces(*rows), include_history=True)["history"]
    assert len(history) == 20
    assert history[0]["raw_status"] == "d6"
    assert history[-1]["raw_status"] == "d25"


def test_history_skips_rows_without_a_date_and_falls_back_to_event_code():
    raw = _with_traces(
        trace(2, "0001-01-01T00:00:00", "UND", "undated"),
        trace(2, "2026-11-10T06:00:00", "UND", None),
        "not-a-row",
    )
    history = normalize_parcel(raw, include_history=True)["history"]
    assert history == [
        {
            "timestamp": "2026-11-10T06:00:00+01:00",
            "status": ParcelStatus.IN_TRANSIT,
            "raw_status": "UND",
        }
    ]


def test_history_is_opt_in():
    assert normalize_parcel(delivered_sample())["history"] is None


# ---------------------------------------------------------------------------
# normalize_parcel — the canonical contract
# ---------------------------------------------------------------------------


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


def test_normalize_publishes_exactly_the_canonical_keys():
    """The aggregator and cross-carrier dashboards depend on this key set."""
    assert list(normalize_parcel(delivered_sample())) == CANONICAL_KEYS


def test_capabilities_are_known_values():
    """A typo here would silently misreport this carrier on the docs site."""
    assert CAPABILITIES <= KNOWN_CAPABILITIES
    assert PENDING_CAPABILITIES <= KNOWN_CAPABILITIES


def test_a_capability_is_never_both_populated_and_pending():
    """The docs site would have to pick one; "awaiting data" must not hide a confirmed field."""
    assert not CAPABILITIES & PENDING_CAPABILITIES


def test_capabilities_match_what_normalize_parcel_actually_returns():
    """Every declared CAPABILITIES entry must come true somewhere in a sample.

    Copy this test into a real carrier's own test_parcels.py verbatim — it
    stays correct for whatever subset of CAPABILITIES that carrier declares.
    """
    delivered = normalize_parcel(delivered_sample())
    active = normalize_parcel(active_sample())
    pickup = normalize_parcel(pickup_sample())
    with_history = normalize_parcel(delivered_sample(), include_history=True)

    if "weight" in CAPABILITIES:
        assert delivered["weight"] is not None
    if "dimensions" in CAPABILITIES:
        assert delivered["dimensions"] is not None
    if "delivery_window" in CAPABILITIES:
        assert active["planned_from"] is not None or active["planned_to"] is not None
    if "pickup_point" in CAPABILITIES:
        assert pickup["pickup_point"] is not None
    if "url" in CAPABILITIES:
        assert delivered["url"] is not None
    if "history" in CAPABILITIES:
        assert with_history["history"] is not None


def test_normalize_registered_fixture():
    parcel = normalize_parcel(registered_keyed(), tracking_code=ACTIVE_CODE)
    assert parcel["carrier"] == "Danske Fragtmænd"
    assert parcel["barcode"] == ACTIVE_CODE
    assert parcel["sender"] == "Example Shop A/S"
    assert parcel["receiver"] is None
    assert parcel["delivered"] is False
    assert parcel["delivered_at"] is None
    assert parcel["planned_from"] == "2026-11-11T00:00:00+01:00"
    assert parcel["planned_to"] is None
    assert parcel["pickup"] is None
    assert parcel["pickup_point"] is None
    assert parcel["url"] == f"https://trace.fragt.dk/#/trackTrace/{ACTIVE_CODE}"
    assert parcel["weight"] == 46.0
    assert isinstance(parcel["weight"], float)
    assert parcel["dimensions"] is None


def test_key_never_reaches_raw_or_url():
    parcel = normalize_parcel(registered_keyed())
    assert "Key" not in parcel["raw"]
    assert KEY not in json.dumps(parcel, default=str)


@pytest.mark.parametrize("top_level", [False, True])
def test_filled_redelivery_url_never_reaches_raw(caplog, top_level):
    raw = registered_keyed()
    link = "https://example.invalid/r/secret"
    if top_level:
        raw["RedeliveryUrl"] = link
    else:
        raw["ConsignmentNote"]["RedeliveryUrl"] = link
    with caplog.at_level(logging.WARNING):
        parcel = normalize_parcel(raw)
        normalize_parcel(raw)
    assert "secret" not in json.dumps(parcel, default=str)
    assert caplog.text.count("non-empty RedeliveryUrl dropped") == 1
    assert "secret" not in caplog.text
    # the input itself is left alone
    assert link in json.dumps(raw)


def test_delivered_picture_list_stays_in_raw(caplog):
    """Seen on a real delivery: picture metadata, no link and no key."""
    with caplog.at_level(logging.WARNING):
        check_shape(delivered_keyed())
        parcel = normalize_parcel(delivered_sample())
    assert parcel["raw"]["PictureList"][0]["Type"] == 0
    assert caplog.text == ""


def test_unseen_picture_field_is_dropped_and_warned_once(caplog):
    raw = delivered_keyed()
    raw["PictureList"][0]["Url"] = "https://example.invalid/p?key=secret"
    raw["PictureList"][0]["Nested"] = {"Link": "https://example.invalid/n/secret"}
    with caplog.at_level(logging.WARNING):
        parcel = normalize_parcel(raw)
        normalize_parcel(raw)
    row = parcel["raw"]["PictureList"][0]
    assert "Url" not in row
    assert "Nested" not in row
    assert row["Type"] == 0
    assert "secret" not in json.dumps(parcel, default=str)
    assert caplog.text.count("new PictureList key=Url") == 1
    assert caplog.text.count("new PictureList key=Nested") == 1
    assert "secret" not in caplog.text
    # the input itself is left alone
    assert raw["PictureList"][0]["Url"]


@pytest.mark.parametrize(
    ("pictures", "expected", "logged"),
    [
        (["https://example.invalid/p?key=secret"], [], "PictureList row is a str"),
        ("https://example.invalid/p?key=secret", None, "PictureList is a str"),
        (None, None, None),
    ],
)
def test_picture_list_of_another_shape_is_dropped(caplog, pictures, expected, logged):
    raw = delivered_keyed()
    raw["PictureList"] = pictures
    with caplog.at_level(logging.WARNING):
        parcel = normalize_parcel(raw)
    assert parcel["raw"]["PictureList"] == expected
    assert "secret" not in json.dumps(parcel, default=str)
    assert "secret" not in caplog.text
    if logged:
        assert logged in caplog.text
    else:
        assert caplog.text == ""


def test_empty_redelivery_url_and_pictures_stay_in_raw(caplog):
    with caplog.at_level(logging.WARNING):
        parcel = normalize_parcel(registered_keyed())
    assert parcel["raw"]["ConsignmentNote"]["RedeliveryUrl"] == ""
    assert parcel["raw"]["PictureList"] == []
    assert caplog.text == ""


def test_barcode_is_the_entered_number():
    parcel = normalize_parcel(registered_keyed(), tracking_code="FD222222")
    assert parcel["barcode"] == "FD222222"


def test_keyless_reply_with_null_parties():
    parcel = normalize_parcel(keyless(), tracking_code=ACTIVE_CODE)
    assert parcel["status"] == ParcelStatus.REGISTERED
    assert parcel["sender"] is None
    assert parcel["receiver"] is None
    assert parcel["weight"] == 46.0


def test_real_delivered_reply():
    """The live delivered reply: State stays Klar and no actual delivery date."""
    raw = delivered_keyed()
    assert raw["State"] == "Klar"
    assert raw["ConsignmentNote"]["DeliveryTime"]["ActualDeliveryDate"] is None
    parcel = normalize_parcel(raw, include_history=True)
    assert parcel["status"] == ParcelStatus.DELIVERED
    assert parcel["delivered"] is True
    # falls back to the newest Status-3 trace
    assert parcel["delivered_at"] == "2026-11-11T11:13:09+01:00"
    assert parcel["planned_from"] is None
    assert parcel["planned_to"] is None
    assert parcel["raw_status"] == "Forsendelsen er leveret hos modtager."
    assert [entry["status"] for entry in parcel["history"]] == [
        ParcelStatus.REGISTERED,
        ParcelStatus.IN_TRANSIT,
        ParcelStatus.IN_TRANSIT,
        ParcelStatus.OUT_FOR_DELIVERY,
        ParcelStatus.DELIVERED,
    ]
    assert [entry["raw_status"] for entry in parcel["history"]][1:3] == [
        "Danske Fragtmænd Eksempelby behandler forsendelsen.",
        "Klar til udkørsel – vi forventer at levere forsendelsen i dag.",
    ]
    assert parcel["weight"] == 46.0
    assert "Key" not in parcel["raw"]


def test_real_delivered_reply_is_silent(caplog):
    with caplog.at_level(logging.WARNING):
        check_shape(delivered_keyed())
        normalize_parcel(delivered_keyed())
    assert caplog.text == ""


def test_ready_for_dispatch_is_still_in_transit():
    """Band trap: KTU says "delivery expected today" but is still at the hub."""
    parcel = normalize_parcel(active_sample())
    assert parcel["status"] == ParcelStatus.IN_TRANSIT
    assert parcel["raw_status"] == (
        "Klar til udkørsel – vi forventer at levere forsendelsen i dag."
    )
    assert parcel["planned_from"] == "2026-11-11T00:00:00+01:00"


def test_omx_is_out_for_delivery():
    parcel = normalize_parcel(out_for_delivery_sample())
    assert parcel["status"] == ParcelStatus.OUT_FOR_DELIVERY
    assert parcel["delivered"] is False
    assert parcel["planned_from"] == "2026-11-11T00:00:00+01:00"


def test_omx_override_only_applies_to_the_under_way_band(caplog):
    """An OMX row with another Status keeps that Status's mapping."""
    raw = _with_traces(trace(4, "2026-11-11T08:49:05", "OMX", "x"))
    assert normalize_parcel(raw)["status"] == ParcelStatus.PROBLEM


def test_information_after_omx_stays_out_for_delivery():
    raw = out_for_delivery_sample()
    raw["ConsignmentNoteTraces"].append(trace(6, "2026-11-11T09:30:00"))
    assert normalize_parcel(raw)["status"] == ParcelStatus.OUT_FOR_DELIVERY


def test_actual_delivery_date_wins_when_set():
    raw = delivered_sample()
    raw["ConsignmentNote"]["DeliveryTime"]["ActualDeliveryDate"] = "2026-11-11T11:12:00"
    assert normalize_parcel(raw)["delivered_at"] == "2026-11-11T11:12:00+01:00"


def test_delivered_without_any_delivery_time():
    raw = _with_traces(trace(3, "0001-01-01T00:00:00", "LEV", "Leveret"))
    parcel = normalize_parcel(raw)
    assert parcel["delivered"] is True
    assert parcel["delivered_at"] is None


def test_dot_interval_beats_expected_delivery_date():
    raw = active_sample()
    times = raw["ConsignmentNote"]["DeliveryTime"]
    times["DotIntervalStart"] = "2026-11-11T08:00:00"
    times["DotIntervalEnd"] = "2026-11-11T10:00:00"
    parcel = normalize_parcel(raw)
    assert parcel["planned_from"] == "2026-11-11T08:00:00+01:00"
    assert parcel["planned_to"] == "2026-11-11T10:00:00+01:00"


def test_half_a_dot_interval_falls_back_to_expected_date():
    raw = active_sample()
    raw["ConsignmentNote"]["DeliveryTime"]["DotIntervalStart"] = "2026-11-11T08:00:00"
    parcel = normalize_parcel(raw)
    assert parcel["planned_from"] == "2026-11-11T00:00:00+01:00"
    assert parcel["planned_to"] is None


def test_dot_interval_of_one_instant_is_a_point_estimate():
    raw = active_sample()
    times = raw["ConsignmentNote"]["DeliveryTime"]
    times["DotIntervalStart"] = times["DotIntervalEnd"] = "2026-11-11T08:00:00"
    parcel = normalize_parcel(raw)
    assert parcel["planned_from"] == "2026-11-11T08:00:00+01:00"
    assert parcel["planned_to"] is None


def test_never_planned_once_delivered():
    raw = delivered_sample()
    times = raw["ConsignmentNote"]["DeliveryTime"]
    times["DotIntervalStart"] = "2026-11-11T08:00:00"
    times["DotIntervalEnd"] = "2026-11-11T10:00:00"
    parcel = normalize_parcel(raw)
    assert parcel["planned_from"] is None
    assert parcel["planned_to"] is None


def test_weight_is_the_sum_of_non_null_goods():
    raw = active_sample()
    goods = raw["ConsignmentNote"]["Goods"]
    goods.append({**goods[0], "Weight": 12.5})
    goods.append({**goods[0], "Weight": None})
    goods.append("not-a-row")
    assert normalize_parcel(raw)["weight"] == 58.5


def test_weight_is_none_when_every_value_is_null():
    raw = active_sample()
    raw["ConsignmentNote"]["Goods"][0]["Weight"] = None
    assert normalize_parcel(raw)["weight"] is None
    raw["ConsignmentNote"]["Goods"] = None
    assert normalize_parcel(raw)["weight"] is None


def test_pickup_point_is_the_parcelshop_name():
    parcel = normalize_parcel(pickup_sample())
    assert parcel["pickup_point"] == "Example Parcelshop"
    assert parcel["pickup"] is None
    assert parcel["status"] == ParcelStatus.IN_TRANSIT


def test_pickup_point_cleared_once_delivered():
    raw = delivered_sample()
    raw["Parcelshop"] = pickup_sample()["Parcelshop"]
    assert normalize_parcel(raw)["pickup_point"] is None


def test_blank_sender_name_is_none():
    raw = active_sample()
    raw["ConsignmentNote"]["Sender"]["Name"] = ""
    assert normalize_parcel(raw)["sender"] is None


def test_normalize_pending_placeholder():
    """A tracked-but-not-found number still yields a full parcel dict."""
    parcel = normalize_parcel({}, tracking_code="FD333333")
    assert parcel["barcode"] == "FD333333"
    assert parcel["status"] == ParcelStatus.UNKNOWN
    assert parcel["delivered"] is False
    assert parcel["raw_status"] is None
    assert parcel["planned_from"] is None
    assert parcel["weight"] is None
    assert parcel["url"] == "https://trace.fragt.dk/#/trackTrace/FD333333"
    assert normalize_parcel({})["url"] is None


def test_normalize_keeps_the_rest_of_the_raw_payload():
    raw = active_sample()
    assert normalize_parcel(raw)["raw"] == raw


# ---------------------------------------------------------------------------
# sort_parcels_by_ts
# ---------------------------------------------------------------------------


def test_sort_parcels_ascending_puts_unparseable_last():
    parcels = [
        {"barcode": "a", "planned_from": "2026-05-02T10:00:00Z"},
        {"barcode": "b", "planned_from": None},
        {"barcode": "c", "planned_from": "2026-05-01T10:00:00Z"},
    ]
    ordered = [p["barcode"] for p in sort_parcels_by_ts(parcels, "planned_from")]
    assert ordered == ["c", "a", "b"]


def test_sort_parcels_descending_still_puts_unparseable_last():
    parcels = [
        {"barcode": "a", "delivered_at": "2026-05-02T10:00:00Z"},
        {"barcode": "b", "delivered_at": "nonsense"},
        {"barcode": "c", "delivered_at": "2026-05-01T10:00:00Z"},
    ]
    ordered = [
        p["barcode"]
        for p in sort_parcels_by_ts(parcels, "delivered_at", descending=True)
    ]
    assert ordered == ["a", "c", "b"]


# ---------------------------------------------------------------------------
# apply_delivered_filter
# ---------------------------------------------------------------------------


def _entry(filter_type: str, amount: int) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_DELIVERED_FILTER_TYPE: filter_type,
            CONF_DELIVERED_FILTER_AMOUNT: amount,
        },
        unique_id=DOMAIN,
    )


def _delivered_pair() -> list[dict]:
    now = datetime.now(UTC)
    return [
        {"barcode": "RECENT", "delivered_at": (now - timedelta(days=1)).isoformat()},
        {"barcode": "OLD", "delivered_at": (now - timedelta(days=30)).isoformat()},
    ]


def test_delivered_filter_by_days():
    kept = apply_delivered_filter(_delivered_pair(), _entry("days", 7))
    assert [p["barcode"] for p in kept] == ["RECENT"]


def test_delivered_filter_by_count():
    parcels = _delivered_pair()
    assert apply_delivered_filter(parcels, _entry("parcels", 1)) == parcels[:1]


def test_delivered_filter_keeps_unparseable_timestamp():
    """Better to show a parcel with a broken date than to silently drop it."""
    parcels = [{"barcode": "WEIRD", "delivered_at": "nonsense"}]
    assert apply_delivered_filter(parcels, _entry("days", 7)) == parcels
