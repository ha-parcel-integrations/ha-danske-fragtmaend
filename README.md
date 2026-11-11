# Danske Fragtmænd Parcel Tracker

[![Release](https://img.shields.io/github/v/release/ha-parcel-integrations/ha-danske-fragtmaend.svg)](https://github.com/ha-parcel-integrations/ha-danske-fragtmaend/releases)
[![Downloads](https://img.shields.io/github/downloads/ha-parcel-integrations/ha-danske-fragtmaend/total.svg)](https://github.com/ha-parcel-integrations/ha-danske-fragtmaend/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 📦 Part of [**ha-parcel-integrations**](https://ha-parcel-integrations.github.io/), a family of package-tracking integrations for Home Assistant that all publish the same parcel format, statuses and events, so they plug into cross-carrier automations and the optional [Parcel Aggregator](https://github.com/ha-parcel-integrations/ha-parcel-aggregator). Browse the other carriers on the website.
>
> 💬 Questions or feedback? Join the discussion on the [Home Assistant community](https://community.home-assistant.io/t/packages-postnl-dhl-nl-dpd-and-gls-parcel-integration/112433/).

A custom Home Assistant integration that tracks your [Danske Fragtmænd](https://www.fragt.dk) consignments in Denmark. No account is needed: paste the tracking link from the text message or e-mail Danske Fragtmænd sends you, or enter the consignment number.

> ⚠️ **Pre-1.0 release.** One real consignment has been followed from registration to delivery. Errors, delays, cancellations and parcelshop deliveries have not been seen yet. Anything the integration does not recognise — a status, an event code, a consignment state, a new field, a date it cannot read, or a saved key the carrier refuses — logs one `WARNING` with a ready-made issue link instead of failing silently. Please [report it](https://github.com/ha-parcel-integrations/ha-danske-fragtmaend/issues/new?template=unrecognised_status.yml) when you see one.

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Options](#options)
- [Removal](#removal)
- [Sensors](#sensors)
- [Parcel status reference](#parcel-status-reference)
- [Events](#events)
- [Services](#services)
- [Examples](#examples)
- [Debugging](#debugging)
- [Troubleshooting](#troubleshooting)
- [Related integrations](#related-integrations)
- [Disclaimer](#disclaimer)
- [Contributing](#contributing)
- [License](#license)

## Features

- Track any number of Danske Fragtmænd consignments by tracking link or consignment number — no account needed
- Per-parcel sensor with the canonical status (`registered` / `in_transit` / `out_for_delivery` / `delivered` / …), the carrier's own status text (in Danish, as the carrier writes it), the expected delivery date or booked time slot, the weight and a tracking deep-link
- Summary sensors: incoming parcels, next delivery, recently delivered parcels
- Read-only **Deliveries** calendar with the expected delivery windows
- `danske_fragtmaend.track_parcel` / `danske_fragtmaend.untrack_parcel` services, so a dashboard button can add a parcel
- Events + device triggers for no-code automations (parcel registered, status changed, delivered, delivery time changed)
- Opt-in per-parcel status history
- Manual refresh button and a diagnostic last-update sensor

## Requirements

- Home Assistant 2025.12 or newer
- A Danske Fragtmænd consignment and its tracking link (`https://trace.fragt.dk/#/trackTrace/…`) from the carrier's text message or e-mail, or its consignment number — no account needed

## Installation

### HACS (recommended)

Click the button below to open this repository in HACS, then install **Danske Fragtmænd**:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ha-parcel-integrations&repository=ha-danske-fragtmaend&category=integration)

Or add it by hand: in HACS, choose the three-dot menu → **Custom repositories**, add `https://github.com/ha-parcel-integrations/ha-danske-fragtmaend` as an **Integration** and install **Danske Fragtmænd**.

Restart Home Assistant if HACS asks you to.

### Manual

Copy `custom_components/danske_fragtmaend` into your `config/custom_components/` folder and restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=danske_fragtmaend)

Add the integration via **Settings → Devices & Services → Add Integration → Danske Fragtmænd**. There is nothing to fill in: the hub is created immediately (Danske Fragtmænd tracking needs no account).

Then add consignments via the integration's **Configure** dialog, the [`danske_fragtmaend.track_parcel`](#services) service, or a [dashboard button](examples/dashboards/add_parcel_card.yaml). Each one is looked up once before it is saved, so a mistyped number or key is caught straight away.

Each line in **Parcels** is one of:

- the whole tracking link, `https://trace.fragt.dk/#/trackTrace/<number>/<key>`;
- the consignment number followed by `/` and the key from that link, `<number>/<key>`;
- the consignment number alone.

The key from the link gives the full record. With the number alone you get a shorter one without the sender, so the `sender` field stays empty. The key is case-sensitive: enter it exactly as it appears in the link. The integration stores it only in its own settings. It never puts it in a sensor, in an event it fires, in the parcel's `url` or in diagnostics, and it never logs it. When you pass a key or a link to the `danske_fragtmaend.track_parcel` service, though, Home Assistant itself records the data of that service call, and automation traces keep it too. Add keyed links through **Configure** if you don't want that, or exclude the `call_service` event from the recorder. A wrong key and an unknown number get the same answer from Danske Fragtmænd, so the error does not say which one it was. Links to a single colli, to an internal id or to the carrier's staff view are not supported.

## Options

Open **Configure** on the integration entry:

| Section | Option | Default | Description |
|---|---|---|---|
| Parcels | Add / remove | — | Manage the tracked consignments (link, `number/key` or number, one per line). Changes apply immediately, no restart. |
| Delivered parcels | Filter by / amount | last 7 days | How long delivered parcels stay visible on the delivered sensor. |
| Parcel history | Include status history | off | Adds a `history` attribute per parcel with each status update. |

Polling isn't one of these settings: the integration polls on a dynamic,
status-driven schedule with nothing to configure.

## Dynamic polling

Polling isn't a setting here — the integration adjusts its own cadence to
what your tracked parcels are actually doing:

- **Quiet hours** — no polling between 00:00–06:00 local time, aside from one
  catch-up check at each end of that window (around midnight and around 6
  AM), so an overnight update is never missed.
- **Hot (every 15 minutes)** — while any tracked parcel is out for delivery
  today, starting an hour before its delivery window opens (or immediately if
  no window is known yet).
- **Normal (every 45 minutes)** — for anything else still on its way.
- **Fully paused** — once every tracked parcel has been delivered, or nothing
  is tracked at all, polling stops until you add a parcel back (adding one
  always triggers an immediate check, regardless of the pause).
- A small, fixed per-hub offset is added on top, so not every Danske Fragtmænd
  hub out there polls at exactly the same second.

Danske Fragtmænd usually gives only an expected delivery date, without a time. So once a consignment is on its way from the local depot to you, it is checked every 15 minutes until a newer update arrives.

## Removal

Standard HA removal applies: **Settings → Devices & Services → Danske Fragtmænd → ⋮ → Delete**. Nothing is stored on Danske Fragtmænd's side.

## Sensors

| Entity | Description |
|---|---|
| `sensor.danske_fragtmaend_incoming_parcels` | Number of active tracked parcels, full list under the `parcels` attribute |
| `sensor.danske_fragtmaend_parcel_<code>` | One per tracked parcel; state is the canonical status, attributes carry the full normalised parcel |
| `sensor.danske_fragtmaend_next_delivery` | Earliest expected delivery moment across all active parcels |
| `sensor.danske_fragtmaend_delivered_parcels` | Recently delivered parcels (see the retention option) |
| `calendar.danske_fragtmaend_deliveries` | Read-only calendar of expected deliveries, no extra API calls |
| `sensor.danske_fragtmaend_last_successful_update` | Diagnostic: when Danske Fragtmænd was last polled successfully |

A delivered parcel moves from its per-parcel sensor to the delivered sensor automatically.

## Parcel status reference

The `status` field is the carrier-agnostic enum shared by the whole integration family:

| Status | Meaning |
|---|---|
| `registered` | Danske Fragtmænd has the consignment details from the sender |
| `in_transit` | Under way, or reported delayed (also "ready for dispatch" while it is still at the depot) |
| `out_for_delivery` | On its way from the local depot to you |
| `delivered` | Delivered |
| `problem` | Danske Fragtmænd reports an error, or the consignment was cancelled |
| `unknown` | Not found yet, or a status we have not mapped yet |

An information-only update from the carrier keeps the status the consignment already had. `at_pickup_point` and `returning` are not reported: no Danske Fragtmænd code for them is known yet.

The carrier's own text is always available as `raw_status`. Danske Fragtmænd writes it in Danish whatever language you use, and it is shown as written.

## Events

The integration fires these on the event bus (also available as device triggers on the Danske Fragtmænd device):

| Event | When |
|---|---|
| `danske_fragtmaend_parcel_registered` | A new parcel appears in the active list |
| `danske_fragtmaend_parcel_status_changed` | A parcel's canonical status changes (`old_status` / `new_status` in the payload), except the final hop to delivered |
| `danske_fragtmaend_parcel_delivered` | A parcel is delivered |
| `danske_fragtmaend_parcel_delivery_time_changed` | The expected delivery window changes |

Every payload is the full normalised parcel plus the hub's `device_id`. Events are suppressed on the first refresh after start-up.

## Services

| Service | Fields | Description |
|---|---|---|
| `danske_fragtmaend.track_parcel` | `tracking_code` (link or number), optional `key` | Start tracking a consignment, after one lookup. A call without a key for a consignment that is already tracked changes nothing, so it never drops a saved key. Home Assistant records the data of every service call, key included |
| `danske_fragtmaend.untrack_parcel` | `tracking_code` (link or number) | Stop tracking a consignment |

## Examples

Ready-to-paste automations and dashboard snippets live in [`examples/`](examples/), including tracking a new parcel straight from a dashboard.

### Community Lovelace cards

Third-party cards that work with this integration's sensors:

- [jonisnet/ha-parcel-card](https://github.com/jonisnet/ha-parcel-card)
- [klaptafel/ha-package-tracker-card](https://github.com/klaptafel/ha-package-tracker-card)

## Debugging

```yaml
logger:
  logs:
    custom_components.danske_fragtmaend: debug
```

## Troubleshooting

- **A consignment shows `unknown`** — Danske Fragtmænd no longer finds it, or its saved key was refused. The integration keeps the last information it had and logs one warning; re-add the consignment with the link from the carrier's newest message.
- **A status logs "Unrecognised Danske Fragtmænd status"** — please [open an issue](https://github.com/ha-parcel-integrations/ha-danske-fragtmaend/issues/new?template=unrecognised_status.yml) with the logged line so the mapping can be extended.

## Related integrations

This integration is part of [**ha-parcel-integrations**](https://ha-parcel-integrations.github.io/) — a family of
parcel-carrier integrations that all publish the same canonical parcel format,
statuses and events.

- [**Parcel Aggregator**](https://github.com/ha-parcel-integrations/ha-parcel-aggregator) rolls every installed carrier
  up into one set of sensors.
- Browse [the organisation](https://ha-parcel-integrations.github.io/) for the current list of supported carriers.

## Disclaimer

This is an independent, community-built project. It is not affiliated with, endorsed by, sponsored by, or supported by Danske Fragtmænd, Home Assistant, or any other third party referenced in this project. Please don't contact Danske Fragtmænd for support with this integration.

All third-party trademarks, trade names, product names, logos, and other brand assets are the property of their respective owners. References to them are solely to identify the relevant carrier or service and do not imply affiliation, sponsorship, or endorsement. Nothing in this project grants or implies any licence or right to use third-party brand assets.

This integration may rely on public, unofficial, or undocumented carrier interfaces, accessed with your own account or API key where required. These may change or be withdrawn without notice and may be subject to Danske Fragtmænd's terms. Data is sent only to Danske Fragtmænd's own services or those of its group; this project operates no servers of its own. You are responsible for ensuring that your use complies with applicable law and those terms. Use is at your own risk; see the [licence](LICENSE) for warranty limitations.

This integration uses the same public tracking service as the Danske Fragtmænd tracking website, with the number and key from your own tracking link.

## Contributing

Pull requests and issues are welcome. Please open an issue before
submitting a large change.

## License

[MIT](LICENSE)
