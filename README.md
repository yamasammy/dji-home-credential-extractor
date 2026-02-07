# DJI Home Credential Extractor

Automated tool to extract DJI Home (Romo robot vacuum) credentials from an Android emulator's memory. These credentials enable MQTT integration with Home Assistant or any custom automation platform.

## What It Does

The DJI Home app stores authentication tokens in memory after login. This script:

1. **Sets up an Android emulator** — installs Android SDK, creates a rooted AVD (if not already present)
2. **Installs DJI Home** — side-loads the APK into the emulator
3. **Waits for you to log in** — you manually log in to your DJI account in the emulator
4. **Dumps process memory** — reads `/proc/<pid>/mem` of the DJI Home process via root access
5. **Extracts credentials** — parses the memory dump for tokens, user IDs, device serial numbers
6. **Validates via API** — tests the extracted token against DJI's API and retrieves MQTT broker credentials

### Extracted Data

| Field | Description |
|-------|-------------|
| `DJI_USER_TOKEN` | Authentication token (`US_...`) for DJI Home API |
| `DJI_USER_ID` | Numeric user ID |
| `DJI_DEVICE_SN` | Robot vacuum serial number |
| MQTT broker | `crobot-mqtt-us.djigate.com:8883` (TLS) |
| MQTT credentials | `user_uuid` + dynamic password (obtained via API, expires ~4h) |

## Prerequisites

- **macOS** (uses Homebrew for dependencies)
- **Android Studio** (or Android SDK with Emulator) — [download](https://developer.android.com/studio). The script will use your existing SDK or try to install command-line tools; if the emulator is missing, it will ask you to install Android Studio.
- **DJI Home APK** (`com.dji.home.apk`) — download from [APKMirror](https://www.apkmirror.com/apk/dji-technology-co-ltd/dji-home/) or [APKPure](https://apkpure.com/dji-home/com.dji.home)
- **Internet connection**
- **DJI account** with a paired Romo robot vacuum

## Usage

1. Download the DJI Home APK and place it in the same directory as the script:

```
dji-home-credential-extractor/
  dji_credentials_extractor.py
  com.dji.home.apk              <-- place APK here
```

2. Run the extractor:

```bash
python3 dji_credentials_extractor.py
```

3. Follow the on-screen instructions:
   - The script will install dependencies and start an Android emulator (first run takes ~10 min)
   - When the emulator is ready, DJI Home will open automatically
   - **Log in to your DJI account** in the emulator
   - Navigate to the main screen where your robot is visible
   - Press ENTER in the terminal to start extraction

4. Credentials are saved to:
   - `.env` — environment variables for use with MQTT clients
   - `dji_credentials.txt` — human-readable summary

## How MQTT Works After Extraction

The `.env` file contains your `DJI_USER_TOKEN`. To connect to the MQTT broker:

```bash
# 1. Get dynamic MQTT credentials (token expires every ~4h)
curl "https://home-api-vg.djigate.com/app/api/v1/users/auth/token?reason=mqtt" \
  -H "x-member-token: $DJI_USER_TOKEN"

# Response contains: mqtt_domain, mqtt_port, user_uuid, user_token (password)

# 2. Connect via MQTT (TLS, port 8883)
# Subscribe to: forward/cr800/thing/product/<DEVICE_SN>/#
```

### MQTT Topics

| Topic | Description |
|-------|-------------|
| `forward/cr800/thing/product/<SN>/property` | Device telemetry (battery, position, status) |
| `forward/cr800/thing/product/<SN>/events` | Events (cleaning progress, errors, drying) |
| `forward/cr800/thing/product/<SN>/services` | Commands (cloud to device) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DJI_USER_TOKEN` | API authentication token |
| `DJI_USER_ID` | Numeric user ID |
| `DJI_DEVICE_SN` | Robot serial number |
| `DJI_API_URL` | API base URL (default: `https://home-api-vg.djigate.com`) |
| `DJI_LOCALE` | Locale (default: `en_US`) |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Emulator won't start | Ensure you have enough disk space (~10GB) and RAM (~4GB free) |
| APK not found | Place the `.apk` file in the same directory as the script |
| Root access denied | Use a Google APIs system image (not Google Play) — the script does this by default |
| Token not found | Make sure you're fully logged in and on the main screen before pressing ENTER |
| API returns error | Token may have expired — re-run the extractor |

## Technical Details

- Uses `google_apis` system image (rootable, unlike `google_play` images)
- Memory dump reads 500MB starting at offset `0x12c00000` (heap region)
- Extracts strings matching known DJI token patterns (`US_...`, `flutter.user_id`, etc.)
- MQTT credentials are **not** stored in the APK — they are fetched dynamically from the API using the `user_token`

## Disclaimer

This tool is intended for extracting credentials from **your own DJI account** to enable local smart home integrations. Use responsibly and only with devices you own.

## License

MIT
