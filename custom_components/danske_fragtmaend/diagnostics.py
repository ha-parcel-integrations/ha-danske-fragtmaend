"""Diagnostics support for the Danske Fragtmænd parcel tracker integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import DanskeFragtmaendConfigEntry

# Diagnostics are pasted into public issues, so redact anything that
# identifies a person, an address or a specific consignment — and the access
# key, which opens the recipient's details. Spelled exactly as stored.
TO_REDACT = {
    # entry options and canonical fields we publish ourselves
    "tracking_code",
    "key",
    "barcode",
    "sender",
    "receiver",
    "url",
    "pickup_point",
    # carrier payload fields
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
    "Username",
    "VehicleNo",
    "ExternalTrackingLink",
    "MarkAndNumber",
    "SenderRef",
    "Latitude",
    "Longitude",
    "Location",
    "ConsignmentComments",
    "PictureList",
    "Partner",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DanskeFragtmaendConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the Danske Fragtmænd config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
        "counts": {
            "incoming_active": len(coordinator.data or []),
            "delivered": len(coordinator.delivered or []),
            "skipped_from_fetch": len(coordinator.delivered_codes),
        },
        "polling": {
            "tier_minutes": coordinator.current_tier_minutes,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "suspended": coordinator.update_interval is None,
        },
        "incoming": async_redact_data(coordinator.data or [], TO_REDACT),
        "delivered": async_redact_data(coordinator.delivered or [], TO_REDACT),
    }
