"""Tests for the Danske Fragtmænd config and options flow."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.danske_fragtmaend.api import (
    DanskeFragtmaendApiError,
    DanskeFragtmaendRejectedError,
)
from custom_components.danske_fragtmaend.config_flow import (
    InvalidTrackingInput,
    normalize_key,
    normalize_tracking_code,
    parse_tracking_input,
    valid_tracking_code,
)
from custom_components.danske_fragtmaend.const import (
    CONF_DELIVERED_FILTER_AMOUNT,
    CONF_DELIVERED_FILTER_TYPE,
    CONF_INCLUDE_HISTORY,
    CONF_KEY,
    CONF_PARCELS,
    CONF_TRACKING_CODE,
    DOMAIN,
)

from .payloads import registered_keyed

LINK = "https://trace.fragt.dk/#/trackTrace/FD000000/XyZ9"
_GET = "custom_components.danske_fragtmaend.config_flow.DanskeFragtmaendApiClient.async_get_parcel"


def test_normalize_tracking_code_trims_and_uppercases():
    assert normalize_tracking_code("  fd000000 ") == "FD000000"
    assert normalize_tracking_code("") == ""
    assert normalize_tracking_code(None) == ""


def test_normalize_key_trims_but_keeps_case():
    assert normalize_key("  XyZ9 ") == "XyZ9"
    assert normalize_key(" ") is None
    assert normalize_key(None) is None


def test_valid_tracking_code_is_loose():
    """No format regex: every new number is looked up live anyway."""
    assert valid_tracking_code("FD000000")
    assert valid_tracking_code("ABC")
    assert valid_tracking_code("A" * 40)
    assert valid_tracking_code("FD-00000")
    for bad in ("", "FD 000000", "FD/1", "FD#1", "FD?1", "FD\t1"):
        assert not valid_tracking_code(bad), bad


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (LINK, ("FD000000", "XyZ9")),
        ("trace.fragt.dk/#/trackTrace/fd000000/aBcD", ("FD000000", "aBcD")),
        ("https://trace.fragt.dk/#/trackTrace/FD000000", ("FD000000", None)),
        ("https://trace.fragt.dk/#/trackTrace/FD000000/", ("FD000000", None)),
        ("https://trace.fragt.dk/#/trackTrace/FD000000/XyZ9?x=1", ("FD000000", "XyZ9")),
        (" fd000000 ", ("FD000000", None)),
        ("FD000000/xYz9", ("FD000000", "xYz9")),
        ("FD000000/ ", ("FD000000", None)),
    ],
)
def test_parse_tracking_input_accepts_the_customer_forms(value, expected):
    assert parse_tracking_input(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://trace.fragt.dk/#/trackTrace/colli/00000000000000000000/XyZ9",
        "https://trace.fragt.dk/#/trackTrace/id/12345",
        "https://trace.fragt.dk/#/trackTraceInternal/FD000000/token",
        "https://trace.fragt.dk/#/trackTraceUnsubscribe/FD000000/a@b",
        "https://trace.fragt.dk/",
        "https://www.fragt.dk/",
        "https://trace.fragt.dk/#/trackTrace/FD000000/XyZ9/extra",
    ],
)
def test_parse_tracking_input_refuses_other_link_forms(value):
    with pytest.raises(InvalidTrackingInput) as err:
        parse_tracking_input(value)
    assert err.value.reason == "unsupported_link"


@pytest.mark.parametrize("value", ["", "  ", "FD 000000", "FD?000"])
def test_parse_tracking_input_refuses_bad_numbers(value):
    with pytest.raises(InvalidTrackingInput) as err:
        parse_tracking_input(value)
    assert err.value.reason == "invalid_tracking_code"


async def test_user_flow_creates_hub_without_input(hass):
    """No account, no postcode — the entry is created straight away."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Danske Fragtmænd"
    assert result["options"][CONF_PARCELS] == []


async def test_second_hub_rejected(hass):
    MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "abort"
    # single_config_entry in the manifest aborts before the flow runs.
    assert result["reason"] == "single_instance_allowed"


def _hub(parcels: list[dict]) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        options={CONF_PARCELS: parcels},
    )


def _settings_input(
    *,
    history=False,
    filter_type="days",
    amount=7,
) -> dict:
    """Build the settings-form submission."""
    return {
        CONF_DELIVERED_FILTER_TYPE: filter_type,
        CONF_DELIVERED_FILTER_AMOUNT: amount,
        CONF_INCLUDE_HISTORY: history,
    }


async def _open_options_step(hass, entry, step_id: str):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "menu"
    assert result["menu_options"] == ["parcels", "settings"]
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step_id}
    )


def _hub(parcels: list[dict]) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        options={CONF_PARCELS: parcels},
    )


def _settings_input(
    *,
    history=False,
    filter_type="days",
    amount=7,
) -> dict:
    """Build the settings-form submission."""
    return {
        CONF_DELIVERED_FILTER_TYPE: filter_type,
        CONF_DELIVERED_FILTER_AMOUNT: amount,
        CONF_INCLUDE_HISTORY: history,
    }


async def _open_options_step(hass, entry, step_id: str):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "menu"
    assert result["menu_options"] == ["parcels", "settings"]
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": step_id}
    )


async def _submit_parcels(hass, entry, lines, lookup):
    with patch(_GET, lookup):
        result = await _open_options_step(hass, entry, "parcels")
        return await hass.config_entries.options.async_configure(
            result["flow_id"], {"tracking_codes": lines}
        )


async def test_options_add_link_stores_number_and_key(hass):
    entry = _hub([])
    entry.add_to_hass(hass)
    lookup = AsyncMock(return_value=registered_keyed())

    result = await _submit_parcels(hass, entry, [LINK], lookup)

    assert result["type"] == "create_entry"
    assert result["data"][CONF_PARCELS] == [
        {CONF_TRACKING_CODE: "FD000000", CONF_KEY: "XyZ9"}
    ]
    lookup.assert_awaited_once_with("FD000000", "XyZ9")


async def test_options_add_bare_number_has_no_key(hass):
    entry = _hub([])
    entry.add_to_hass(hass)
    lookup = AsyncMock(return_value=registered_keyed())
    result = await _submit_parcels(hass, entry, ["fd000000"], lookup)
    assert result["data"][CONF_PARCELS] == [{CONF_TRACKING_CODE: "FD000000"}]
    lookup.assert_awaited_once_with("FD000000", None)


async def test_options_keyed_403_at_add_time_is_not_recognised(hass):
    entry = _hub([])
    entry.add_to_hass(hass)
    lookup = AsyncMock(side_effect=DanskeFragtmaendRejectedError)
    result = await _submit_parcels(hass, entry, [LINK], lookup)
    assert result["type"] == "form"
    assert result["errors"] == {"base": "not_recognised"}
    # never retried without the key
    lookup.assert_awaited_once_with("FD000000", "XyZ9")


async def test_options_keyless_404_at_add_time_is_not_recognised(hass):
    entry = _hub([])
    entry.add_to_hass(hass)
    result = await _submit_parcels(
        hass, entry, ["FD999999"], AsyncMock(return_value=None)
    )
    assert result["errors"] == {"base": "not_recognised"}


async def test_options_transport_error_at_add_time(hass):
    entry = _hub([])
    entry.add_to_hass(hass)
    result = await _submit_parcels(
        hass,
        entry,
        ["FD000000"],
        AsyncMock(side_effect=DanskeFragtmaendApiError("HTTP 500")),
    )
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    ("line", "error"),
    [
        ("https://trace.fragt.dk/#/trackTrace/colli/0000/XyZ9", "unsupported_link"),
        ("FD 000000", "invalid_tracking_code"),
    ],
)
async def test_options_refuses_bad_lines_without_a_lookup(hass, line, error):
    entry = _hub([])
    entry.add_to_hass(hass)
    lookup = AsyncMock()
    result = await _submit_parcels(hass, entry, [line], lookup)
    assert result["errors"] == {"base": error}
    lookup.assert_not_awaited()


async def test_options_shows_saved_parcels_and_skips_known_lookups(hass):
    entry = _hub(
        [
            {CONF_TRACKING_CODE: "FD000000", CONF_KEY: "XyZ9"},
            {CONF_TRACKING_CODE: "FD111111"},
        ]
    )
    entry.add_to_hass(hass)
    lookup = AsyncMock()
    with patch(_GET, lookup):
        result = await _open_options_step(hass, entry, "parcels")
        suggested = result["data_schema"].schema
        marker = next(iter(suggested))
        assert marker.description["suggested_value"] == ["FD000000/XyZ9", "FD111111"]
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"tracking_codes": ["FD000000/XyZ9", "FD111111"]}
        )
    assert result["type"] == "create_entry"
    lookup.assert_not_awaited()


async def test_options_changing_a_key_looks_it_up_again(hass):
    entry = _hub([{CONF_TRACKING_CODE: "FD000000", CONF_KEY: "XyZ9"}])
    entry.add_to_hass(hass)
    lookup = AsyncMock(return_value=registered_keyed())
    result = await _submit_parcels(hass, entry, ["FD000000/xyz9"], lookup)
    assert result["data"][CONF_PARCELS] == [
        {CONF_TRACKING_CODE: "FD000000", CONF_KEY: "xyz9"}
    ]
    lookup.assert_awaited_once_with("FD000000", "xyz9")


async def test_options_de_duplicates_numbers(hass):
    entry = _hub([{CONF_TRACKING_CODE: "FD111111"}])
    entry.add_to_hass(hass)
    result = await _submit_parcels(
        hass, entry, ["FD111111", "fd111111", ""], AsyncMock()
    )
    assert result["data"][CONF_PARCELS] == [{CONF_TRACKING_CODE: "FD111111"}]


async def test_options_remove_parcel(hass):
    entry = _hub([{CONF_TRACKING_CODE: "FD111111"}, {CONF_TRACKING_CODE: "FD222222"}])
    entry.add_to_hass(hass)
    result = await _submit_parcels(hass, entry, ["FD222222"], AsyncMock())
    assert result["type"] == "create_entry"
    assert result["data"][CONF_PARCELS] == [{CONF_TRACKING_CODE: "FD222222"}]


async def test_options_can_clear_the_tracked_code_list(hass):
    entry = _hub([{CONF_TRACKING_CODE: "FD111111"}])
    entry.add_to_hass(hass)
    result = await _submit_parcels(hass, entry, [], AsyncMock())
    assert result["type"] == "create_entry"
    assert result["data"][CONF_PARCELS] == []


async def test_options_changes_history_and_delivered(hass):
    entry = _hub([])
    entry.add_to_hass(hass)
    result = await _open_options_step(hass, entry, "settings")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _settings_input(
            history=True,
            filter_type="parcels",
            amount=5,
        ),
    )
    assert result["type"] == "create_entry"
    assert result["data"][CONF_INCLUDE_HISTORY] is True
    assert result["data"][CONF_DELIVERED_FILTER_TYPE] == "parcels"
    assert result["data"][CONF_DELIVERED_FILTER_AMOUNT] == 5
