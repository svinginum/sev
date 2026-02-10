# SEV Home Assistant Integration

[SEV](https://www.sev.fo) is the Faroese electricity provider. This integration connects to the SEV Customer REST API so you can see your energy usage, estimated CO₂, and cost in Home Assistant.

## Features

- **Config flow**: Add the integration via **Settings → Devices & services → Add integration** and search for "SEV". Enter your SEV User ID and API Key.
- **Sensors per meter**: For each electricity meter you have access to, the integration creates:
  - **Energy today** – kWh consumed today
  - **CO₂ today** – Estimated CO₂ (kg) from consumption today
  - **Cost today** – Estimated cost (DKK) for today

Data is updated every 30 minutes to respect the SEV API limit of 10 calls per 5 minutes.

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

## API limits

The SEV API allows a maximum of **10 requests per 5 minutes**. This integration uses 4 requests per update (meters, usage, CO₂, cost) and updates every 30 minutes, so it stays within the limit.

## Disclaimer

This is a community integration and is not officially endorsed by SEV. Use of the SEV API is subject to SEV’s terms and fair usage policy.
