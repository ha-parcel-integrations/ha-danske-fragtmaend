"""Tests for the Danske Fragtmænd API client."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.danske_fragtmaend.api import (
    DanskeFragtmaendApiClient,
    DanskeFragtmaendApiError,
    DanskeFragtmaendRejectedError,
)
from custom_components.danske_fragtmaend.const import (
    MAX_BODY_BYTES,
    TRACKING_API_URL_KEYED,
    TRACKING_API_URL_KEYLESS,
)

from .payloads import ACTIVE_CODE, KEY, keyless, registered_keyed


def _session_returning(
    status: int, body: object = b"", headers: dict | None = None
) -> MagicMock:
    if isinstance(body, bytes):
        raw = body
    elif isinstance(body, str):
        raw = body.encode()
    else:
        raw = json.dumps(body).encode()
    response = MagicMock()
    response.status = status
    response.headers = headers or {}
    response.content.read = AsyncMock(side_effect=lambda limit: raw[:limit])
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.get = MagicMock(return_value=ctx)
    return session


async def test_keyed_lookup_uses_the_keyed_leaf_and_drops_the_key():
    session = _session_returning(200, registered_keyed())
    client = DanskeFragtmaendApiClient(session)

    parcel = await client.async_get_parcel(ACTIVE_CODE, KEY)

    assert parcel["State"] == "Klar"
    assert "Key" not in parcel
    assert parcel["ConsignmentNote"]["RedeliveryUrl"] == ""
    assert KEY not in json.dumps(parcel)
    args, kwargs = session.get.call_args
    assert args[0] == TRACKING_API_URL_KEYED
    assert kwargs["params"] == {
        "consignmentNumber": ACTIVE_CODE,
        "language": "da",
        "key": KEY,
    }
    assert kwargs["allow_redirects"] is False
    assert kwargs["headers"] == {"Accept": "application/json"}


async def test_key_is_sent_with_its_case_untouched():
    session = _session_returning(200, registered_keyed())
    await DanskeFragtmaendApiClient(session).async_get_parcel(ACTIVE_CODE, "aBcD")
    assert session.get.call_args.kwargs["params"]["key"] == "aBcD"


async def test_keyless_lookup_uses_the_number_leaf():
    session = _session_returning(200, keyless())
    parcel = await DanskeFragtmaendApiClient(session).async_get_parcel(ACTIVE_CODE)
    assert parcel["ConsignmentNote"]["Receiver"] is None
    args, kwargs = session.get.call_args
    assert args[0] == TRACKING_API_URL_KEYLESS
    assert "key" not in kwargs["params"]


async def test_keyless_404_with_message_is_not_found():
    body = {"Message": "Couldn't find fragtbrev with number: XX999999"}
    client = DanskeFragtmaendApiClient(_session_returning(404, body))
    assert await client.async_get_parcel("XX999999") is None


async def test_keyless_404_without_json_is_a_transport_error(caplog):
    client = DanskeFragtmaendApiClient(_session_returning(404, "<html>gone</html>"))
    with caplog.at_level(logging.WARNING), pytest.raises(DanskeFragtmaendApiError):
        await client.async_get_parcel(ACTIVE_CODE)
    assert "non-JSON reply" in caplog.text
    assert "unrecognised_status.yml" in caplog.text


async def test_keyed_403_is_rejected_and_never_retried_without_the_key():
    session = _session_returning(403)
    client = DanskeFragtmaendApiClient(session)
    with pytest.raises(DanskeFragtmaendRejectedError) as err:
        await client.async_get_parcel(ACTIVE_CODE, KEY)
    assert session.get.call_count == 1
    assert KEY not in str(err.value)


async def test_keyed_404_is_an_error_not_not_found():
    client = DanskeFragtmaendApiClient(_session_returning(404, {"Message": "x"}))
    with pytest.raises(DanskeFragtmaendApiError) as err:
        await client.async_get_parcel(ACTIVE_CODE, KEY)
    assert not isinstance(err.value, DanskeFragtmaendRejectedError)


@pytest.mark.parametrize("status", [301, 302, 401, 403, 500, 503])
async def test_other_statuses_are_transport_errors(status):
    client = DanskeFragtmaendApiClient(_session_returning(status, "x"))
    with pytest.raises(DanskeFragtmaendApiError) as err:
        await client.async_get_parcel(ACTIVE_CODE)
    assert err.value.status_code == status
    assert not isinstance(err.value, DanskeFragtmaendRejectedError)


async def test_429_carries_retry_after():
    client = DanskeFragtmaendApiClient(
        _session_returning(429, headers={"Retry-After": "120"})
    )
    with pytest.raises(DanskeFragtmaendApiError) as err:
        await client.async_get_parcel(ACTIVE_CODE)
    assert err.value.status_code == 429
    assert err.value.retry_after == 120


async def test_429_with_http_date_retry_after_leaves_backoff_to_the_caller():
    client = DanskeFragtmaendApiClient(
        _session_returning(
            429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
        )
    )
    with pytest.raises(DanskeFragtmaendApiError) as err:
        await client.async_get_parcel(ACTIVE_CODE)
    assert err.value.retry_after is None


async def test_non_json_200_warns_once(caplog):
    client = DanskeFragtmaendApiClient(_session_returning(200, "<html></html>"))
    with caplog.at_level(logging.WARNING):
        for _ in range(2):
            with pytest.raises(DanskeFragtmaendApiError):
                await client.async_get_parcel(ACTIVE_CODE)
    assert caplog.text.count("non-JSON reply") == 1


async def test_empty_200_is_non_json():
    client = DanskeFragtmaendApiClient(_session_returning(200, b""))
    with pytest.raises(DanskeFragtmaendApiError):
        await client.async_get_parcel(ACTIVE_CODE)


async def test_body_over_the_cap_is_refused():
    client = DanskeFragtmaendApiClient(
        _session_returning(200, b"x" * (MAX_BODY_BYTES + 5))
    )
    with pytest.raises(DanskeFragtmaendApiError) as err:
        await client.async_get_parcel(ACTIVE_CODE)
    assert "too large" in str(err.value)


@pytest.mark.parametrize("body", [["a"], {"State": "Klar"}, {"ConsignmentNote": None}])
async def test_reply_without_a_consignment_note_is_an_error(body, caplog):
    client = DanskeFragtmaendApiClient(_session_returning(200, body))
    with caplog.at_level(logging.WARNING), pytest.raises(DanskeFragtmaendApiError):
        await client.async_get_parcel(ACTIVE_CODE)
    assert "unexpected response shape" in caplog.text


async def test_number_mismatch_is_inconclusive(caplog):
    client = DanskeFragtmaendApiClient(
        _session_returning(200, registered_keyed("FD999999"))
    )
    with caplog.at_level(logging.WARNING), pytest.raises(DanskeFragtmaendApiError):
        await client.async_get_parcel(ACTIVE_CODE, KEY)
    assert "different consignment number" in caplog.text
    assert "FD999999" not in caplog.text
    assert KEY not in caplog.text


async def test_echoed_number_is_compared_case_insensitively():
    sample = registered_keyed(ACTIVE_CODE.lower())
    client = DanskeFragtmaendApiClient(_session_returning(200, sample))
    assert await client.async_get_parcel(ACTIVE_CODE) is not None


async def test_new_envelope_keys_warn_once_by_name(caplog):
    sample = registered_keyed()
    sample["NewThing"] = "x"
    sample["ConsignmentNote"]["AlsoNew"] = "secret value"
    client = DanskeFragtmaendApiClient(_session_returning(200, sample))
    with caplog.at_level(logging.WARNING):
        await client.async_get_parcel(ACTIVE_CODE, KEY)
        await client.async_get_parcel(ACTIVE_CODE, KEY)
    assert caplog.text.count("new top-level key=NewThing") == 1
    assert caplog.text.count("new ConsignmentNote key=AlsoNew") == 1
    assert "secret value" not in caplog.text


@pytest.mark.parametrize(
    "error", [aiohttp.ClientConnectionError("https://x/?key=XyZ9"), TimeoutError()]
)
async def test_network_errors_carry_no_url(error):
    session = MagicMock()
    session.get = MagicMock(side_effect=error)
    client = DanskeFragtmaendApiClient(session)
    with pytest.raises(DanskeFragtmaendApiError) as err:
        await client.async_get_parcel(ACTIVE_CODE, KEY)
    assert KEY not in str(err.value)
    assert err.value.__cause__ is None
