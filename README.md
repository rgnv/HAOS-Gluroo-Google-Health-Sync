# Gluroo Google Health Sync

A Home Assistant custom integration that reads glucose and related diabetes data from
Gluroo Global Connect and attempts to write each new glucose reading to the Google
Health API when Google enables blood-glucose creation for the account/API release.

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
- A ready-to-import `dashboards/glucose.yaml` view plus a Body-dashboard card
  snippet in `dashboards/body-gluroo-card.yaml`.
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

The integration sends the `blood-glucose` payload using mg/dL, marks readings as
continuous glucose monitoring measurements with interstitial-fluid specimens, and
uses the original Gluroo sample timestamp. It only requests the write scope. A
successful Google Health API `2xx` response is logged by Home Assistant; a real
provider write is not claimed until that response is observed.

### Current Google API limitation

The live Google Health API currently advertises `blood-glucose` as `list`, `get`,
`reconcile`, and rollup operations, but not `create`. A direct POST therefore
returns HTTP 400 (`Create is not supported for data type blood-glucose`). The
integration detects that response, keeps all Gluroo/HA sensors working, and stops
retrying instead of claiming a write succeeded. Google Health `weight` and
`body-fat` creation are separate supported data types. Actual glucose writes require
Google to enable creation for `blood-glucose`, an Android Health Connect writer, or
the legacy Google Fit API while it remains available.

## Entities

The integration creates one Gluroo device with these entities:

- **Blood glucose** — latest value in mg/dL, with direction and delta attributes.
- **Glucose delta** and **Glucose trend**.
- **Glucose reading age** in seconds.
- **Last treatment**, **Last insulin**, and **Last carbohydrates**.
- **Insulin on board** and **Carbohydrates on board** when reported by the latest
  device-status payload.
- **Google Health upload** — `ready`, `disabled`, `error`, or
  `provider_unsupported`; the latter is the current Google Health API behavior for
  blood-glucose creation and means no reading was uploaded.

Treatment and device-status sensors remain unavailable when Gluroo does not provide
those fields; this is expected and avoids inventing values.

## Dashboard

The live HAOS Overview dashboard contains a **Glucose** view and a Gluroo section
inside the existing **Body** view. The portable YAML sources are:

- [`dashboards/glucose.yaml`](dashboards/glucose.yaml)
- [`dashboards/body-gluroo-card.yaml`](dashboards/body-gluroo-card.yaml)

The Glucose view includes current glucose, trend, delta, reading age, a 12-hour
history graph, a 7-day statistics graph, treatment context, and Google Health upload
status.

## Health Connect on Android

The direct Google Health cloud API currently rejects creation of blood-glucose data.
Gluroo's Android application has its own Health Connect background synchronization,
which is the supported path for the phone:

1. In Gluroo on Android, open its Health Connect integration/settings.
2. Grant Gluroo write access to blood glucose in Android Health Connect.
3. Disable battery optimization/background restriction for Gluroo.
4. If desired, enable the Home Assistant Android Companion app's Health Connect
   **read** sensor so HA can display the phone-side record too.

The direct Gluroo Global Connect → HA path remains the authoritative live sensor path
in this integration. Details and official links are in
[`docs/google-health-upload.md`](docs/google-health-upload.md).

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
