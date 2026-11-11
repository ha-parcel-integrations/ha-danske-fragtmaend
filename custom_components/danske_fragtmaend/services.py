"""Services for the Danske Fragtmænd parcel tracker integration.

`danske_fragtmaend.track_parcel` / `danske_fragtmaend.untrack_parcel` let you add or remove a
tracked parcel without opening the integration options — so a Lovelace button
can start tracking a parcel straight from a dashboard.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .config_flow import (
    InvalidTrackingInput,
    async_validate_parcel,
    normalize_key,
    parcel_entry,
    parse_tracking_input,
)
from .const import CONF_KEY, CONF_PARCELS, CONF_TRACKING_CODE, DOMAIN

SERVICE_TRACK_PARCEL = "track_parcel"
SERVICE_UNTRACK_PARCEL = "untrack_parcel"

_TRACK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TRACKING_CODE): cv.string,
        vol.Optional(CONF_KEY): cv.string,
    }
)
_UNTRACK_SCHEMA = vol.Schema({vol.Required(CONF_TRACKING_CODE): cv.string})

_INPUT_ERRORS = {
    "invalid_tracking_code": "That is not a valid Danske Fragtmænd consignment number",
    "unsupported_link": (
        "Only the customer tracking link (…#/trackTrace/{number}/{key}) is supported"
    ),
}


def _resolve_entry(hass: HomeAssistant):
    """Return the single Danske Fragtmænd hub, or raise when it is not set up."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("Danske Fragtmænd is not set up")
    return entries[0]


def _parse(value: str) -> tuple[str, str | None]:
    try:
        return parse_tracking_input(value)
    except InvalidTrackingInput as err:
        raise ServiceValidationError(_INPUT_ERRORS[err.reason]) from None


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Danske Fragtmænd services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_TRACK_PARCEL):
        return

    async def _track(call: ServiceCall) -> None:
        tracking_code, link_key = _parse(call.data[CONF_TRACKING_CODE])
        field_key = normalize_key(call.data.get(CONF_KEY))
        if link_key and field_key and link_key != field_key:
            raise ServiceValidationError(
                "The link and the key field carry different keys"
            )
        key = link_key or field_key
        entry = _resolve_entry(hass)

        parcels = [dict(p) for p in entry.options.get(CONF_PARCELS, [])]
        existing = next(
            (p for p in parcels if p[CONF_TRACKING_CODE] == tracking_code), None
        )
        if existing is not None and (key is None or existing.get(CONF_KEY) == key):
            # Already tracked. A call without a key never drops a saved one;
            # removing a key is an explicit edit in the options flow.
            return

        error = await async_validate_parcel(hass, tracking_code, key)
        if error == "not_recognised":
            raise ServiceValidationError(
                "Danske Fragtmænd does not recognise that number or key"
            )
        if error:
            raise HomeAssistantError(
                "Could not reach Danske Fragtmænd, try again later"
            )

        parcels = [p for p in parcels if p[CONF_TRACKING_CODE] != tracking_code]
        parcels.append(parcel_entry(tracking_code, key))
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_PARCELS: parcels}
        )

    async def _untrack(call: ServiceCall) -> None:
        tracking_code, _ = _parse(call.data[CONF_TRACKING_CODE])
        entry = _resolve_entry(hass)
        current = entry.options.get(CONF_PARCELS, [])
        kept = [p for p in current if p[CONF_TRACKING_CODE] != tracking_code]
        if len(kept) != len(current):
            hass.config_entries.async_update_entry(
                entry, options={**entry.options, CONF_PARCELS: kept}
            )

    hass.services.async_register(
        DOMAIN, SERVICE_TRACK_PARCEL, _track, schema=_TRACK_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UNTRACK_PARCEL, _untrack, schema=_UNTRACK_SCHEMA
    )


def async_unload_services(hass: HomeAssistant) -> None:
    """Remove the Danske Fragtmænd services (single-entry integration, so on unload)."""
    for service in (SERVICE_TRACK_PARCEL, SERVICE_UNTRACK_PARCEL):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
