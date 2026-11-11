"""Danske Fragtmænd public tracking API client.

The contract the coordinator relies on:

* ``async_get_parcel`` returns the consignment record on success, with the
  echoed access key removed,
* returns ``None`` when the number alone is unknown to the carrier,
* raises :class:`DanskeFragtmaendRejectedError` when a lookup with a key is
  refused — the carrier answers an unknown number and a wrong key the same
  way, so the two are never told apart,
* raises :class:`DanskeFragtmaendApiError` for anything else, with
  ``status_code`` set on a non-2xx response and ``retry_after`` set when the
  carrier's own ``Retry-After`` header on a 429 could be parsed as seconds.

Network failures are raised as :class:`DanskeFragtmaendApiError` too, carrying
only the exception type: aiohttp's own messages can include the request URL,
and the URL carries the access key.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from .const import (
    MAX_BODY_BYTES,
    REQUEST_TIMEOUT_SECONDS,
    TRACKING_API_LANGUAGE,
    TRACKING_API_URL_KEYED,
    TRACKING_API_URL_KEYLESS,
)
from .parcels import check_shape, scrub_raw, warn_once

_LOGGER = logging.getLogger(__name__)

_HEADERS = {"Accept": "application/json"}
_TIMEOUT = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)


class DanskeFragtmaendApiError(Exception):
    """Raised when a Danske Fragtmænd API call returns an unexpected response."""

    def __init__(
        self,
        detail: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        """Store the status code and the ``Retry-After`` header, if any."""
        super().__init__(f"Danske Fragtmænd API request failed: {detail}")
        self.detail = detail
        self.status_code = status_code
        self.retry_after = retry_after


class DanskeFragtmaendRejectedError(DanskeFragtmaendApiError):
    """The carrier refused a number + key pair (unknown number or wrong key)."""

    def __init__(self) -> None:
        """Record the refusal as HTTP 403."""
        super().__init__("number or key not recognised", status_code=403)


class DanskeFragtmaendApiClient:
    """Client for the public Danske Fragtmænd tracking endpoint."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialise the client with an aiohttp session."""
        self._session = session

    async def async_get_parcel(
        self, tracking_code: str, key: str | None = None
    ) -> dict[str, Any] | None:
        """Fetch one consignment, with its access key when the user has one.

        A rejected key is never retried without it: that would quietly swap
        the user's chosen view for a different one.
        """
        params = {"consignmentNumber": tracking_code, "language": TRACKING_API_LANGUAGE}
        if key:
            url = TRACKING_API_URL_KEYED
            params["key"] = key
        else:
            url = TRACKING_API_URL_KEYLESS
        try:
            async with self._session.get(
                url,
                params=params,
                headers=_HEADERS,
                allow_redirects=False,
                timeout=_TIMEOUT,
            ) as response:
                status = response.status
                retry_after_header = response.headers.get("Retry-After")
                body = await response.content.read(MAX_BODY_BYTES + 1)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DanskeFragtmaendApiError(type(err).__name__) from None

        if status == 429:
            try:
                retry_after = float(retry_after_header) if retry_after_header else None
            except ValueError:
                retry_after = (
                    None  # an HTTP-date, not seconds; the coordinator backs off itself
                )
            raise DanskeFragtmaendApiError(
                "HTTP 429", status_code=429, retry_after=retry_after
            )
        if key and status == 403:
            raise DanskeFragtmaendRejectedError
        if len(body) > MAX_BODY_BYTES:
            raise DanskeFragtmaendApiError(
                "response body too large", status_code=status
            )

        payload = _decode(body)
        if not key and status == 404:
            if isinstance(payload, dict) and "Message" in payload:
                return None
            _warn_non_json(status, payload)
            raise DanskeFragtmaendApiError("HTTP 404", status_code=404)
        if status != 200:
            raise DanskeFragtmaendApiError(f"HTTP {status}", status_code=status)
        if payload is None:
            _warn_non_json(status, payload)
            raise DanskeFragtmaendApiError("unparseable body", status_code=status)
        if not isinstance(payload, dict) or not isinstance(
            payload.get("ConsignmentNote"), dict
        ):
            warn_once(
                "shape",
                "unexpected response shape",
                f"top-level type={type(payload).__name__}",
            )
            raise DanskeFragtmaendApiError("unexpected body (no consignment note)")

        echoed = str(payload["ConsignmentNote"].get("ConsignmentNumber") or "")
        if echoed.strip().upper() != tracking_code:
            warn_once(
                "number_mismatch",
                "reply for a different consignment number",
                "the reply's ConsignmentNumber differs from the tracked one; "
                "keeping the last good data",
            )
            raise DanskeFragtmaendApiError("consignment number mismatch")

        check_shape(payload)
        return scrub_raw(payload)


def _decode(body: bytes) -> Any:
    """Return the JSON value of ``body``, or ``None`` when it is not JSON."""
    if not body:
        return None
    try:
        return json.loads(body.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        return None


def _warn_non_json(status: int, payload: Any) -> None:
    """Log once that the carrier answered with something other than its JSON."""
    warn_once(
        "non_json",
        "non-JSON reply",
        f"HTTP {status}, body type={type(payload).__name__}",
    )
