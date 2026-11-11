"""Config flow for the Danske Fragtmænd parcel tracker integration."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import (
    DanskeFragtmaendApiClient,
    DanskeFragtmaendApiError,
    DanskeFragtmaendRejectedError,
)
from .const import (
    CONF_DELIVERED_FILTER_AMOUNT,
    CONF_DELIVERED_FILTER_TYPE,
    CONF_INCLUDE_HISTORY,
    CONF_KEY,
    CONF_PARCELS,
    CONF_TRACKING_CODE,
    DEFAULT_DELIVERED_FILTER_AMOUNT,
    DEFAULT_DELIVERED_FILTER_TYPE,
    DEFAULT_INCLUDE_HISTORY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_NOT_IN_NUMBER = re.compile(r"[/#?\s]")
_LINK_ROUTE = "trackTrace"
_KEY_SEPARATOR = "/"


class InvalidTrackingInput(ValueError):
    """A pasted value is not a usable number, number + key, or customer link.

    ``reason`` is the translation key of the error shown to the user.
    """

    def __init__(self, reason: str) -> None:
        """Store the error's translation key."""
        super().__init__(reason)
        self.reason = reason


def normalize_tracking_code(value: str) -> str:
    """Return the consignment number trimmed and upper-cased."""
    return (value or "").strip().upper()


def normalize_key(value: str | None) -> str | None:
    """Return the access key trimmed — never re-cased, the carrier compares it exactly."""
    key = (value or "").strip()
    return key or None


def valid_tracking_code(value: str) -> bool:
    """Whether ``value`` can be a consignment number.

    Deliberately loose: every new number is looked up before it is saved, so
    a shape check would only ever reject a valid number. It only refuses what
    cannot be one number (link or separator characters, whitespace).
    """
    return bool(value) and not _NOT_IN_NUMBER.search(value)


def parse_tracking_input(value: str) -> tuple[str, str | None]:
    """Split a customer link, ``NUMBER/KEY`` or a bare number into its parts.

    Only the customer link form (``#/trackTrace/{number}/{key}``) is accepted;
    the colli, internal-id and staff link forms are refused, since they key on
    something other than the consignment number.
    """
    text = (value or "").strip()
    if "#" in text or "://" in text or text.lower().startswith("trace.fragt.dk"):
        _, _, fragment = text.partition("#")
        parts = [part for part in fragment.split("?", 1)[0].split("/") if part]
        if (
            len(parts) < 2
            or len(parts) > 3
            or parts[0] != _LINK_ROUTE
            or parts[1] in ("colli", "id")
        ):
            raise InvalidTrackingInput("unsupported_link")
        number, key = parts[1], parts[2] if len(parts) == 3 else None
    else:
        number, _, key = text.partition(_KEY_SEPARATOR)
    code = normalize_tracking_code(number)
    if not valid_tracking_code(code):
        raise InvalidTrackingInput("invalid_tracking_code")
    return code, normalize_key(key)


def parcel_entry(code: str, key: str | None) -> dict[str, str]:
    """Return the stored form of one tracked consignment."""
    entry = {CONF_TRACKING_CODE: code}
    if key:
        entry[CONF_KEY] = key
    return entry


def display_entry(parcel: dict[str, str]) -> str:
    """Return the ``NUMBER`` or ``NUMBER/KEY`` line the parcels form shows."""
    key = parcel.get(CONF_KEY)
    code = parcel[CONF_TRACKING_CODE]
    return f"{code}{_KEY_SEPARATOR}{key}" if key else code


async def async_validate_parcel(
    hass: HomeAssistant, code: str, key: str | None
) -> str | None:
    """Look the consignment up once; return an error translation key or ``None``.

    A wrong key and an unknown number look the same to the carrier, so both
    are reported as "not recognised" without saying which.
    """
    client = DanskeFragtmaendApiClient(async_get_clientsession(hass))
    try:
        found = await client.async_get_parcel(code, key)
    except DanskeFragtmaendRejectedError:
        return "not_recognised"
    except DanskeFragtmaendApiError:
        return "cannot_connect"
    if found is None:
        return "not_recognised"
    return None


def _current_parcels(entry: ConfigEntry) -> list[dict[str, str]]:
    """Return a mutable copy of the tracked parcels list."""
    return [dict(item) for item in entry.options.get(CONF_PARCELS, [])]


class DanskeFragtmaendConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI-driven configuration flow for the Danske Fragtmænd integration."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> DanskeFragtmaendOptionsFlowHandler:
        """Return the options flow handler."""
        return DanskeFragtmaendOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the Danske Fragtmænd hub — single instance, no input needed.

        Each consignment carries its own optional key, stored with its number,
        so there is nothing to ask at setup: parcels are added afterwards via
        the options flow, the ``danske_fragtmaend.track_parcel`` service or a
        dashboard button. ``single_config_entry`` in the manifest enforces one
        hub.
        """
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="Danske Fragtmænd",
            data={},
            options={
                CONF_PARCELS: [],
                CONF_DELIVERED_FILTER_TYPE: DEFAULT_DELIVERED_FILTER_TYPE,
                CONF_DELIVERED_FILTER_AMOUNT: DEFAULT_DELIVERED_FILTER_AMOUNT,
                CONF_INCLUDE_HISTORY: DEFAULT_INCLUDE_HISTORY,
            },
        )


class DanskeFragtmaendOptionsFlowHandler(OptionsFlow):
    """Manage tracked parcels separately from integration settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer parcel management separately from integration settings."""
        return self.async_show_menu(
            step_id="init", menu_options=["parcels", "settings"]
        )

    async def async_step_parcels(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and handle the complete tracked-code list.

        Each line is a customer link, ``NUMBER/KEY`` or a bare number. A line
        that is new, or changes a saved key, is looked up once before saving.
        """
        errors: dict[str, str] = {}
        current = _current_parcels(self.config_entry)
        lines = [display_entry(parcel) for parcel in current]
        if user_input is not None:
            lines = [line for line in user_input.get("tracking_codes") or [] if line]
            known = {
                (parcel[CONF_TRACKING_CODE], parcel.get(CONF_KEY)) for parcel in current
            }
            parcels: dict[str, dict[str, str]] = {}
            for line in lines:
                try:
                    code, key = parse_tracking_input(line)
                except InvalidTrackingInput as err:
                    errors["base"] = err.reason
                    break
                if code in parcels:
                    continue
                if (code, key) not in known:
                    error = await async_validate_parcel(self.hass, code, key)
                    if error:
                        errors["base"] = error
                        break
                parcels[code] = parcel_entry(code, key)
            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        **self.config_entry.options,
                        CONF_PARCELS: list(parcels.values()),
                    },
                )
        schema = vol.Schema(
            {
                vol.Optional("tracking_codes"): selector.TextSelector(
                    selector.TextSelectorConfig(multiple=True)
                )
            }
        )
        return self.async_show_form(
            step_id="parcels",
            data_schema=self.add_suggested_values_to_schema(
                schema, {"tracking_codes": lines}
            ),
            errors=errors,
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show and handle the non-parcel integration settings."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_PARCELS: _current_parcels(self.config_entry),
                    CONF_DELIVERED_FILTER_TYPE: user_input[CONF_DELIVERED_FILTER_TYPE],
                    CONF_DELIVERED_FILTER_AMOUNT: int(
                        user_input[CONF_DELIVERED_FILTER_AMOUNT]
                    ),
                    CONF_INCLUDE_HISTORY: bool(user_input[CONF_INCLUDE_HISTORY]),
                },
            )
        current = self.config_entry.options
        schema: dict[Any, Any] = {
            vol.Required(
                CONF_DELIVERED_FILTER_TYPE,
                default=current.get(
                    CONF_DELIVERED_FILTER_TYPE, DEFAULT_DELIVERED_FILTER_TYPE
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["days", "parcels"],
                    translation_key=CONF_DELIVERED_FILTER_TYPE,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_DELIVERED_FILTER_AMOUNT,
                default=current.get(
                    CONF_DELIVERED_FILTER_AMOUNT, DEFAULT_DELIVERED_FILTER_AMOUNT
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=365, step=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_INCLUDE_HISTORY,
                default=current.get(CONF_INCLUDE_HISTORY, DEFAULT_INCLUDE_HISTORY),
            ): selector.BooleanSelector(),
        }
        return self.async_show_form(step_id="settings", data_schema=vol.Schema(schema))
