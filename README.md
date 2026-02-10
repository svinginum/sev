# SEV Home Assistant Integration

[SEV](https://www.sev.fo) is the Faroese electricity provider. This integration connects to the SEV Customer REST API so you can see your energy usage, estimated CO₂, and cost in Home Assistant.

## Features

- **Config flow**: Add the integration via **Settings → Devices & services → Add integration** and search for "SEV". Enter your SEV User ID and API Key.
- **Sensors per meter** (9 per meter): Estimated cost til end of month, Estimated energy til end of month, Cost last month, Cost yesterday, Cost today, Energy yesterday, Energy today, Energy last month, CO₂ yesterday. (Estimates use this month’s data so far, extrapolated to end of month.)

Data is updated every 30 minutes. Dates use Faroese local time. “Yesterday” usually has data even when “today” is still empty (API delay).

## Getting your SEV API credentials

You need a **User ID** and **API Key** from SEV. These are the same credentials used for the SEV REST API (see [SEV API documentation](https://api.sev.fo)). If you don’t have them yet, contact SEV or check your customer portal for API access.

## Installation

### Via HACS (recommended)

1. Install [HACS](https://hacs.xyz) if you haven’t already.
2. In HACS, go to **Integrations** and click the **+** (Add) button.
3. Search for **SEV** or add this repository as a custom repository:
   - **Repository:** `https://github.com/svinginum/sev`  
4. Install the integration and restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and add **SEV** with your User ID and API Key.

### Manual

1. Copy the `custom_components/sev` folder into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration via **Settings → Devices & services → Add integration → SEV**.

## Seeing your data

- **Developer tools → States**: Search for `sev` or your meter name to see all SEV entities and their values.
- **Dashboard**: Add a card (e.g. “Entities” or “Statistic”) and pick the SEV sensors.
- If values stay at 0 or unknown: “Yesterday” sensors often get data first; “today” can be empty until the API has hourly data. Enable **Settings → System → Logging** and set `custom_components.sev` to **Debug** to see what the API returns.

## Versioning (for developers)

- **Single source of truth:** `custom_components/sev/manifest.json` → `"version": "x.y.z"`. Home Assistant and HACS read this.
- **Scheme:** Use [SemVer](https://semver.org): `MAJOR.MINOR.PATCH` (e.g. `1.0.0`, `1.1.0`, `1.0.1`).
  - **MAJOR** – breaking changes (e.g. config or entity IDs change).
  - **MINOR** – new features, no breaking changes.
  - **PATCH** – bug fixes only.
- **Releasing a new version:**
  1. Bump `version` in `custom_components/sev/manifest.json`.
  2. Commit and push.
  3. Create a **Git tag** (and optionally a **GitHub Release**):
     ```bash
     git tag v1.0.1
     git push origin v1.0.1
     ```
  - HACS will show the latest tags/releases when users install or update. The tag can be `v1.0.1` or `1.0.1`; the value in `manifest.json` should match (without the `v` is fine: `1.0.1`).

## API limits

The SEV API allows a maximum of **10 requests per 5 minutes**. This integration uses 10 requests per update (meters + today, yesterday, and last month usage/CO₂/cost) and updates every 30 minutes, so it stays within the limit.

## Disclaimer

This is a community integration and is not officially endorsed by SEV. Use of the SEV API is subject to SEV’s terms and fair usage policy.
