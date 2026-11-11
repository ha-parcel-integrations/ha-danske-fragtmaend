"""Canonical parcel shape, status mapping and list helpers.

Everything in this module is a **pure function** — no I/O, no Home Assistant
objects beyond the config entry's options — so the carrier mapping stays
unit-testable without spinning up HA.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry

from .const import (
    CARRIER_TZ_NAME,
    CONF_DELIVERED_FILTER_AMOUNT,
    CONF_DELIVERED_FILTER_TYPE,
    DEFAULT_DELIVERED_FILTER_AMOUNT,
    DEFAULT_DELIVERED_FILTER_TYPE,
    HISTORY_MAX_EVENTS,
    TRACKING_URL,
    ParcelStatus,
)

_LOGGER = logging.getLogger(__name__)

# The carrier stamps every time as Danish wall-clock time without an offset.
CARRIER_TZ = ZoneInfo(CARRIER_TZ_NAME)

# The ``?template=`` parameter matters: without it the link opens a blank form,
# and the report comes back missing the version and the log line we need.
NEW_ISSUE_URL = (
    "https://github.com/ha-parcel-integrations/ha-danske-fragtmaend/issues/new"
    "?template=unrecognised_status.yml"
)

# Keyed on the consignment trace ``Status``. 6 ("information") carries no
# movement of its own and is resolved in _walk_traces instead.
_STATUS_MAP: dict[int, ParcelStatus] = {
    1: ParcelStatus.REGISTERED,
    2: ParcelStatus.IN_TRANSIT,
    3: ParcelStatus.DELIVERED,
    4: ParcelStatus.PROBLEM,
    5: ParcelStatus.IN_TRANSIT,
    7: ParcelStatus.PROBLEM,
}
STATUS_INFORMATION = 6
STATUS_DELIVERED = 3
STATUS_UNDER_WAY = 2

# Event codes that refine the under-way band. ``OMX`` is the run from the
# local hub to the receiver on delivery day; the other under-way codes stay
# in transit.
_UNDER_WAY_OVERRIDES: dict[str, ParcelStatus] = {
    "OMX": ParcelStatus.OUT_FOR_DELIVERY,
}

STATE_CANCELLED = "Annulleret"
KNOWN_STATES = frozenset({"Klar", STATE_CANCELLED})
KNOWN_EVENT_CODES = frozenset({"DAT", "ANK", "KTU", "OMX", "LEV"})

KNOWN_TOP_LEVEL_KEYS = frozenset(
    {
        "Carrier",
        "ColliTraces",
        "ConsignmentComments",
        "ConsignmentNote",
        "ConsignmentNoteTraces",
        "EtaStatus",
        "ForcedColliScan",
        "Key",
        "NotificationHistories",
        "Parcelshop",
        "Parent",
        "PictureList",
        "RedeliveryUrl",
        "RelatedBillingNumber",
        "RelatedBillings",
        "State",
    }
)
KNOWN_NOTE_KEYS = frozenset(
    {
        "AgreementNumber",
        "BillingInfo",
        "ConsignmentDate",
        "ConsignmentNoteType",
        "ConsignmentNumber",
        "DeliveryTime",
        "ExchangePallets",
        "Goods",
        "Initiator",
        "LastUpdated",
        "Partner",
        "Pickup",
        "PickupTime",
        "ProductCode",
        "Receiver",
        "RedeliveryUrl",
        "Reference",
        "Route",
        "Sender",
        "SenderReference",
        "ServiceCodes",
        "ShippingType",
        "WhoPays",
        "WhoPaysOriginal",
    }
)

# One-shot warning keys already logged this HA session, so each unknown is
# reported once instead of on every poll.
_unmapped_statuses_logged: set[str] = set()


def warn_once(
    kind: str, what: str, detail: str, *, once_key: str | None = None
) -> None:
    """Log an unconfirmed shape or code once, with a copy-paste issue link.

    ``detail`` carries keys and codes only — never a value that could hold
    personal data or the access key.
    """
    marker = f"{kind}:{once_key if once_key is not None else detail}"
    if marker in _unmapped_statuses_logged:
        return
    _unmapped_statuses_logged.add(marker)
    _LOGGER.warning(
        "Unrecognised Danske Fragtmænd %s — help us map it. Open an issue and "
        "paste this line: %s\n  %s",
        what,
        NEW_ISSUE_URL,
        detail,
    )


_KNOWN_PICTURE_KEYS = frozenset(
    {
        "BookingNr",
        "ColliNr",
        "ConsignmentNumber",
        "Id",
        "Latitude",
        "Longitude",
        "TimestampClient",
        "TimestampServer",
        "Type",
        "UserName",
    }
)


def scrub_raw(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the payload without the fields that can open something.

    The echoed access key always goes. A filled-in redelivery link goes too:
    it has only been seen empty, and such a link may carry its own key. Its
    first sighting warns once, by name.
    """
    scrubbed = {
        name: value
        for name, value in payload.items()
        if name != "Key" and not (name == "RedeliveryUrl" and value)
    }
    note = payload.get("ConsignmentNote")
    note_link = False
    if isinstance(note, dict) and note.get("RedeliveryUrl"):
        note_link = True
        scrubbed["ConsignmentNote"] = {
            name: value for name, value in note.items() if name != "RedeliveryUrl"
        }
    if note_link or payload.get("RedeliveryUrl"):
        warn_once(
            "dropped", "response field", "non-empty RedeliveryUrl dropped from raw"
        )
    if "PictureList" in payload:
        scrubbed["PictureList"] = _scrub_pictures(payload["PictureList"])
    return scrubbed


def _scrub_pictures(pictures: Any) -> list[dict[str, Any]] | None:
    """Keep only the picture metadata fields seen on a real delivery.

    The picture download is gated by the access key, so an unseen field here
    could carry a link with that key in it: it is dropped, not published, and
    named once in a warning.
    """
    if pictures is None:
        return None
    if not isinstance(pictures, list):
        warn_once(
            "picture_shape",
            "response field",
            f"PictureList is a {type(pictures).__name__}, dropped from raw",
        )
        return None
    kept: list[dict[str, Any]] = []
    for row in pictures:
        if not isinstance(row, dict):
            warn_once(
                "picture_shape",
                "response field",
                f"PictureList row is a {type(row).__name__}, dropped from raw",
            )
            continue
        for name in sorted(set(row) - _KNOWN_PICTURE_KEYS):
            warn_once(
                "picture_key",
                "response field",
                f"new PictureList key={name}, dropped from raw",
            )
        kept.append(
            {name: value for name, value in row.items() if name in _KNOWN_PICTURE_KEYS}
        )
    return kept


def check_shape(payload: dict[str, Any]) -> None:
    """Warn once per envelope key the integration has never seen."""
    for name in sorted(set(payload) - KNOWN_TOP_LEVEL_KEYS):
        warn_once("top_key", "response field", f"new top-level key={name}")
    note = payload.get("ConsignmentNote")
    if isinstance(note, dict):
        for name in sorted(set(note) - KNOWN_NOTE_KEYS):
            warn_once("note_key", "response field", f"new ConsignmentNote key={name}")


def map_trace_status(code: Any) -> ParcelStatus | None:
    """Map a trace ``Status`` other than 6 to a canonical status, or ``None``.

    An unmapped value warns once and returns ``None`` so the caller can fall
    back to the newest mappable trace.
    """
    if isinstance(code, int) and not isinstance(code, bool):
        mapped = _STATUS_MAP.get(code)
        if mapped is not None:
            return mapped
    warn_once("status", "status", f"Status={code!r} → falls back to the history")
    return None


def _check_event_code(code: Any) -> None:
    if code not in KNOWN_EVENT_CODES:
        warn_once("event_code", "event code", f"EventCode={code!r}")


def _check_state(state: Any) -> None:
    if state not in KNOWN_STATES:
        warn_once("state", "consignment state", f"State={state!r}")


def parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO 8601 string to an aware datetime, or ``None`` on failure.

    Naive values are treated as UTC so a list always sorts without crashing on
    a mixed set.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def parse_carrier_time(value: Any, field: str) -> datetime | None:
    """Parse a carrier timestamp as Copenhagen local time.

    The carrier's "no value" placeholder (year 1) and blanks are ``None``;
    anything else that does not parse warns once, naming the field.
    """
    if value is None or value == "":
        return None
    text = str(value)
    if text.startswith("0001-01-01"):
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        warn_once("date", "date format", f"unparseable date in {field}")
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CARRIER_TZ)
    return parsed


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment is not None else None


def _walk_traces(
    traces: Any,
) -> list[tuple[dict[str, Any], datetime | None, ParcelStatus | None]]:
    """Return the consignment traces oldest first, each with its status.

    A Status-6 row inherits the status before it (``registered`` when it is
    the first), so an information event never moves the parcel.
    """
    rows: list[tuple[dict[str, Any], datetime | None]] = [
        (trace, parse_carrier_time(trace.get("Date"), "ConsignmentNoteTraces.Date"))
        for trace in traces or []
        if isinstance(trace, dict)
    ]
    floor = datetime.min.replace(tzinfo=UTC)
    rows.sort(key=lambda row: row[1] or floor)

    walked: list[tuple[dict[str, Any], datetime | None, ParcelStatus | None]] = []
    previous: ParcelStatus | None = None
    for trace, moment in rows:
        _check_event_code(trace.get("EventCode"))
        code = trace.get("Status")
        if code == STATUS_INFORMATION:
            status: ParcelStatus | None = previous or ParcelStatus.REGISTERED
        elif (
            code == STATUS_UNDER_WAY and trace.get("EventCode") in _UNDER_WAY_OVERRIDES
        ):
            status = _UNDER_WAY_OVERRIDES[trace["EventCode"]]
        else:
            status = map_trace_status(code)
        if status is not None:
            previous = status
        walked.append((trace, moment, status))
    return walked


def _event_text(trace: dict[str, Any]) -> str | None:
    return trace.get("EventCodeText") or trace.get("EventCode") or None


def build_history(
    walked: list[tuple[dict[str, Any], datetime | None, ParcelStatus | None]],
    *,
    max_events: int = HISTORY_MAX_EVENTS,
) -> list[dict]:
    """Build the canonical ``history`` list, oldest → newest, capped.

    Only consignment traces count: the per-colli scan list opens with a
    placeholder row before the first scan, and is never read.
    """
    entries = [
        {
            "timestamp": moment.isoformat(),
            "status": status if status is not None else ParcelStatus.UNKNOWN,
            "raw_status": _event_text(trace),
        }
        for trace, moment, status in walked
        if moment is not None
    ]
    return entries[-max_events:]


def tracking_url(tracking_code: str | None) -> str | None:
    """Construct the consumer tracking deep-link for a parcel (never with a key)."""
    if not tracking_code:
        return None
    return TRACKING_URL.format(tracking_code=tracking_code)


def _total_weight(goods: Any) -> float | None:
    weights = [
        float(item["Weight"])
        for item in goods or []
        if isinstance(item, dict)
        and isinstance(item.get("Weight"), (int, float))
        and not isinstance(item.get("Weight"), bool)
    ]
    return sum(weights) if weights else None


def _name(block: Any) -> str | None:
    if isinstance(block, dict):
        return block.get("Name") or None
    return None


def normalize_parcel(
    raw: dict,
    *,
    tracking_code: str | None = None,
    include_history: bool = False,
) -> dict:
    """Return a carrier-agnostic parcel dict with the payload under ``raw``.

    ``tracking_code`` is the number the user entered; it is the barcode even
    for a not-yet-found consignment, which has no record at all. The keys of
    the returned dict are the suite contract — never omit one.
    """
    note = raw.get("ConsignmentNote")
    note = note if isinstance(note, dict) else {}
    barcode = tracking_code or note.get("ConsignmentNumber") or None

    walked = _walk_traces(raw.get("ConsignmentNoteTraces"))
    mapped = [status for _, _, status in walked if status is not None]
    status = mapped[-1] if mapped else ParcelStatus.UNKNOWN
    if "State" in raw:
        _check_state(raw.get("State"))
    if raw.get("State") == STATE_CANCELLED:
        status = ParcelStatus.PROBLEM
    delivered = status is ParcelStatus.DELIVERED

    times = note.get("DeliveryTime")
    times = times if isinstance(times, dict) else {}

    delivered_at: datetime | None = None
    planned_from: datetime | None = None
    planned_to: datetime | None = None
    if delivered:
        delivered_at = parse_carrier_time(
            times.get("ActualDeliveryDate"), "DeliveryTime.ActualDeliveryDate"
        )
        if delivered_at is None:
            delivered_at = next(
                (
                    moment
                    for trace, moment, _ in reversed(walked)
                    if trace.get("Status") == STATUS_DELIVERED and moment is not None
                ),
                None,
            )
    else:
        start = parse_carrier_time(
            times.get("DotIntervalStart"), "DeliveryTime.DotIntervalStart"
        )
        end = parse_carrier_time(
            times.get("DotIntervalEnd"), "DeliveryTime.DotIntervalEnd"
        )
        if start is not None and end is not None:
            planned_from = start
            planned_to = end if end != start else None
        else:
            planned_from = parse_carrier_time(
                times.get("ExpectedDeliveryDate"), "DeliveryTime.ExpectedDeliveryDate"
            )

    pickup_point = None if delivered else _name(raw.get("Parcelshop"))

    return {
        "carrier": "Danske Fragtmænd",
        "barcode": barcode,
        "sender": _name(note.get("Sender")),
        "receiver": None,
        "status": status,
        "raw_status": _event_text(walked[-1][0]) if walked else None,
        "delivered": delivered,
        "delivered_at": _iso(delivered_at),
        "planned_from": _iso(planned_from),
        "planned_to": _iso(planned_to),
        "pickup": None,
        "pickup_point": pickup_point,
        "url": tracking_url(barcode),
        "weight": _total_weight(note.get("Goods")),
        "dimensions": None,
        "history": build_history(walked) if include_history else None,
        "raw": scrub_raw(raw),
    }


def sort_parcels_by_ts(
    parcels: list[dict], key_field: str, *, descending: bool = False
) -> list[dict]:
    """Return normalised parcels sorted by the ISO timestamp at ``key_field``.

    The suite's sort contract: incoming/outgoing ascending on ``planned_from``,
    delivered descending on ``delivered_at``. Parcels whose value is missing or
    unparseable always sort to the end, regardless of ``descending``.
    """
    with_ts: list[tuple[datetime, dict]] = []
    without_ts: list[dict] = []
    for parcel in parcels:
        parsed = parse_iso(parcel.get(key_field))
        if parsed is None:
            without_ts.append(parcel)
        else:
            with_ts.append((parsed, parcel))
    with_ts.sort(key=lambda item: item[0], reverse=descending)
    return [parcel for _, parcel in with_ts] + without_ts


def apply_delivered_filter(parcels: list[dict], entry: ConfigEntry) -> list[dict]:
    """Trim the delivered list per the entry's retention option.

    ``parcels`` must already be sorted newest-first. ``days`` keeps deliveries
    from the last N days (an unparseable ``delivered_at`` is kept rather than
    silently dropped); the ``parcels`` type keeps the N most recent. Parcels
    stay *tracked* either way — this only controls what the delivered sensor
    shows.
    """
    options = entry.options
    filter_type = options.get(CONF_DELIVERED_FILTER_TYPE, DEFAULT_DELIVERED_FILTER_TYPE)
    amount = int(
        options.get(CONF_DELIVERED_FILTER_AMOUNT, DEFAULT_DELIVERED_FILTER_AMOUNT)
    )
    if filter_type == "days":
        cutoff = datetime.now(UTC) - timedelta(days=amount)
        return [
            parcel
            for parcel in parcels
            if (parsed := parse_iso(parcel.get("delivered_at"))) is None
            or parsed >= cutoff
        ]
    return parcels[:amount]
