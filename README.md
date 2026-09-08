# Gluroo Google Health Sync

A Home Assistant custom integration that reads glucose and related diabetes data from
Gluroo Global Connect and optionally writes each new glucose reading to the Google
Health API.

```text
Gluroo mobile app / CGM
        -> Gluroo Global Connect (Nightscout-compatible API)
        -> Home Assistant sensors
        -> Google Health API (blood-glucose data points)
```

The integration does **not** scrape Android notifications or require an Android
runtime on the Home Assistant host. If Gluroo is receiving readings on a phone, the
Gluroo Global Connect backend is the supported network boundary for Home Assistant.
This project targets the cloud Google Health API, not Android Health Connect.

## Features

- Config flow for a Gluroo Global Connect URL and API secret token.
- Home Assistant OAuth2 flow using the narrow Google Health health-metrics write scope.
- Glucose, delta, trend, reading age, latest treatment, insulin, carbohydrates, IOB,
  and COB sensors when those fields are present in the Gluroo data.
- Bounded local deduplication so a reading is uploaded at most once per entry ID.
- Poll interval and Google upload options in the Home Assistant options flow.
- HACS-compatible repository with no private URLs, tokens, profiles, or device data.

## HACS installation

1. In HACS, open **Integrations** → **Custom repositories**.
2. Add this repository URL and choose **Integration**.
3. Install **Gluroo Google Health Sync** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and select it.
5. Complete the Google OAuth flow, then paste the Gluroo Global Connect URL and API
   secret token when prompted.

The Gluroo URL should be the standard HTTPS Nightscout-compatible URL copied from
Gluroo's **Settings → Gluroo Global Connect Nightscout** page. Do not paste the
Nightguard-specific URL, and do not include `?token=...` in the URL field. Put the
API secret token in the token field.

## Google Health API prerequisites

1. Create or select a Google Cloud project.
2. Enable the [Google Health API](https://console.cloud.google.com/apis/library/health.googleapis.com).
3. Configure Google Auth Platform consent and add the Google account as a test user
   while the app is in testing mode.
4. Add this scope under Data Access:

   ```text
   https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly
   ```

5. Create a Web application OAuth client and add this exact redirect URI:

   ```text
   https://my.home-assistant.io/redirect/oauth
   ```

6. In Home Assistant, register the client ID and secret under **Settings → Devices
   & services → Application credentials** for this integration.

The integration writes the `blood-glucose` data type using mg/dL, marks readings as
continuous glucose monitoring measurements with interstitial-fluid specimens, and
uses the original Gluroo sample timestamp. It only requests the write scope. A
successful Google Health API `2xx` response is logged by Home Assistant; a real
provider write is not claimed until that response is observed.

## Entities

The integration creates one Gluroo device with these entities:

- **Blood glucose** — latest value in mg/dL, with direction and delta attributes.
- **Glucose delta** and **Glucose trend**.
- **Glucose reading age** in seconds.
- **Last treatment**, **Last insulin**, and **Last carbohydrates**.
- **Insulin on board** and **Carbohydrates on board** when reported by the latest
  device-status payload.

Treatment and device-status sensors remain unavailable when Gluroo does not provide
those fields; this is expected and avoids inventing values.

## Security and privacy

- Gluroo tokens and Google OAuth tokens are stored in Home Assistant config-entry
  storage and are never logged by this project.
- The repository contains no household identifiers, personal health profiles, device
  addresses, or credentials.
- Use the read-only Gluroo token if Gluroo provides one for your account. The
  integration only performs GET requests against Gluroo.
- Health data is sensitive. Keep Home Assistant and its backups protected, and use
  HTTPS for the Gluroo URL.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip pytest pytest-asyncio aiohttp
pytest -q
python -m compileall custom_components
```

The pure-Python tests validate Nightscout parsing, malformed data handling, Google
Health payload shape, and stable deduplication IDs. Full Home Assistant config-flow
and runtime verification must run against the target HAOS version.

## License

MIT. See [LICENSE](LICENSE).
