"""Tests for the Danske Fragtmænd services (track_parcel / untrack_parcel)."""

from unittest.mock import AsyncMock, patch

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.danske_fragtmaend.api import (
    DanskeFragtmaendApiError,
    DanskeFragtmaendRejectedError,
)
from custom_components.danske_fragtmaend.const import (
    CONF_KEY,
    CONF_PARCELS,
    CONF_TRACKING_CODE,
    DOMAIN,
)

from .payloads import KEY, active_sample

_SAMPLE = active_sample()
_GET = (
    "custom_components.danske_fragtmaend.api.DanskeFragtmaendApiClient.async_get_parcel"
)
LINK = f"https://trace.fragt.dk/#/trackTrace/FD999999/{KEY}"


async def _setup(hass, parcels: list[dict] | None = None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        options={CONF_PARCELS: parcels or []},
    )
    entry.add_to_hass(hass)
    with patch(_GET, new=AsyncMock(return_value=_SAMPLE)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def _call(hass, service: str, data: dict, lookup=None) -> AsyncMock:
    lookup = lookup or AsyncMock(return_value=_SAMPLE)
    with patch(_GET, new=lookup):
        await hass.services.async_call(DOMAIN, service, data, blocking=True)
        await hass.async_block_till_done()
    return lookup


async def test_track_parcel_adds_a_bare_number(hass):
    entry = await _setup(hass)
    lookup = await _call(hass, "track_parcel", {CONF_TRACKING_CODE: " fd999999 "})
    assert entry.options[CONF_PARCELS] == [{CONF_TRACKING_CODE: "FD999999"}]
    lookup.assert_any_await("FD999999", None)


async def test_track_parcel_takes_the_key_from_a_link(hass):
    entry = await _setup(hass)
    lookup = await _call(hass, "track_parcel", {CONF_TRACKING_CODE: LINK})
    assert entry.options[CONF_PARCELS] == [
        {CONF_TRACKING_CODE: "FD999999", CONF_KEY: KEY}
    ]
    lookup.assert_any_await("FD999999", KEY)


async def test_track_parcel_takes_the_key_field_with_its_case(hass):
    entry = await _setup(hass)
    await _call(
        hass, "track_parcel", {CONF_TRACKING_CODE: "FD999999", CONF_KEY: " aBcD "}
    )
    assert entry.options[CONF_PARCELS] == [
        {CONF_TRACKING_CODE: "FD999999", CONF_KEY: "aBcD"}
    ]


async def test_track_parcel_refuses_conflicting_keys(hass):
    await _setup(hass)
    with pytest.raises(ServiceValidationError):
        await _call(hass, "track_parcel", {CONF_TRACKING_CODE: LINK, CONF_KEY: "other"})


@pytest.mark.parametrize(
    "value",
    ["", "FD 999999", "https://trace.fragt.dk/#/trackTrace/colli/0000/XyZ9"],
)
async def test_track_parcel_rejects_bad_input(hass, value):
    await _setup(hass)
    with pytest.raises(ServiceValidationError):
        await _call(hass, "track_parcel", {CONF_TRACKING_CODE: value})


async def test_track_parcel_not_recognised(hass):
    entry = await _setup(hass)
    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            "track_parcel",
            {CONF_TRACKING_CODE: LINK},
            AsyncMock(side_effect=DanskeFragtmaendRejectedError),
        )
    assert entry.options[CONF_PARCELS] == []


async def test_track_parcel_transport_error(hass):
    entry = await _setup(hass)
    with pytest.raises(HomeAssistantError):
        await _call(
            hass,
            "track_parcel",
            {CONF_TRACKING_CODE: "FD999999"},
            AsyncMock(side_effect=DanskeFragtmaendApiError("HTTP 500")),
        )
    assert entry.options[CONF_PARCELS] == []


async def test_track_parcel_duplicate_is_noop(hass):
    entry = await _setup(hass, parcels=[{CONF_TRACKING_CODE: "FD999999"}])
    lookup = await _call(hass, "track_parcel", {CONF_TRACKING_CODE: "FD999999"})
    assert len(entry.options[CONF_PARCELS]) == 1
    lookup.assert_not_awaited()


async def test_keyless_call_never_drops_a_saved_key(hass):
    saved = {CONF_TRACKING_CODE: "FD999999", CONF_KEY: KEY}
    entry = await _setup(hass, parcels=[saved])
    lookup = await _call(hass, "track_parcel", {CONF_TRACKING_CODE: "FD999999"})
    assert entry.options[CONF_PARCELS] == [saved]
    lookup.assert_not_awaited()


async def test_track_parcel_with_a_new_key_replaces_the_old_one(hass):
    entry = await _setup(hass, parcels=[{CONF_TRACKING_CODE: "FD999999"}])
    await _call(hass, "track_parcel", {CONF_TRACKING_CODE: LINK})
    assert entry.options[CONF_PARCELS] == [
        {CONF_TRACKING_CODE: "FD999999", CONF_KEY: KEY}
    ]


async def test_untrack_parcel_removes_from_options(hass):
    entry = await _setup(
        hass, parcels=[{CONF_TRACKING_CODE: "FD999999", CONF_KEY: KEY}]
    )
    await _call(hass, "untrack_parcel", {CONF_TRACKING_CODE: LINK})
    assert entry.options[CONF_PARCELS] == []


async def test_untrack_unknown_code_is_noop(hass):
    entry = await _setup(hass, parcels=[{CONF_TRACKING_CODE: "FD999999"}])
    await _call(hass, "untrack_parcel", {CONF_TRACKING_CODE: "FD000001"})
    assert len(entry.options[CONF_PARCELS]) == 1


async def test_services_need_a_hub(hass):
    await _setup(hass)
    with (
        patch.object(hass.config_entries, "async_entries", return_value=[]),
        pytest.raises(ServiceValidationError),
    ):
        await _call(hass, "untrack_parcel", {CONF_TRACKING_CODE: "FD999999"})
