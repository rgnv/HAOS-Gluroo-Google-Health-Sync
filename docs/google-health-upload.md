# Google Health upload research

## Verified provider capability

The Google Health API currently exposes the `blood-glucose` data type with these
operations:

- `list`
- `get`
- `reconcile`
- `rollup`
- `dailyRollup`

It does not currently expose `create` for blood glucose. A live POST to:

```text
https://health.googleapis.com/v4/users/me/dataTypes/blood-glucose/dataPoints
```

returns HTTP 400 with:

```text
Create is not supported for data type blood-glucose
```

The write-only health-metrics OAuth scope is therefore not proof that a blood-glucose
write is available. This repository detects that response, exposes
`sensor.gluroo_google_health_upload` as `provider_unsupported`, and stops retrying.
It never records the reading as uploaded after that response.

## Supported paths

### Recommended now: Gluroo → Health Connect

Gluroo's Android application has its own Google Health Connect integration and recent
release notes document background synchronization. Enable it inside the Gluroo Android
app and grant blood-glucose write permission in Android Health Connect. This is the
supported device-local path for the Xperia; Home Assistant does not need to write
Health Connect directly.

Health Connect's official Android API supports `BloodGlucoseRecord` and the
`WRITE_BLOOD_GLUCOSE` permission. The Home Assistant Android Companion app can read
Health Connect sensors, but it does not write them.

### Temporary legacy path: Google Fit

The legacy Google Fit REST API can create `com.google.blood_glucose` data points, but
Google has closed new developer enrollment and announced deprecation/end-of-support in
2026. It is not used by this project because it would add a short-lived OAuth/API
backend rather than the supported Health Connect path.

### Cloud Google Health API

The existing Google Health API OAuth integration remains useful for supported types
such as weight and body fat. It is retained here for capability detection, but it
cannot upload Gluroo blood glucose until Google enables `create` for that data type.

## Sources

- [Google Health API data types](https://developers.google.com/health/data-types)
- [Google Health API blood-glucose reference](https://developers.google.com/health/data-types/vitals)
- [Google Health API create method](https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/create)
- [Google Fit blood-glucose write guide](https://developers.google.com/fit/scenarios/write-blood-glucose-data)
- [Android Health Connect blood-glucose/vitals guide](https://developer.android.com/health-and-fitness/health-connect/experiences/vitals)
- [Gluroo Health Connect release note](https://gluroo.com/blog/releases/1-3-92-new-cgm-blood-sugar-charts-on-iphone-on-the-lock-screen-and-dynamic-island-improved-google-health-connect-android-and-more/)
