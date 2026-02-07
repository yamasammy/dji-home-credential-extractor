#!/usr/bin/env python3
"""
DJI Home Credentials Extractor
===============================

Automated script to extract DJI Home credentials from an Android emulator.

Prerequisites:
- macOS
- The DJI Home APK (com.dji.home.apk) in the same folder as this script
- Internet connection

The script will:
1. Install Android SDK and emulator if needed
2. Create and launch a rooted Android emulator
3. Install the DJI Home APK
4. Ask you to log in to the app
5. Extract your credentials from memory
6. Save everything to a file

Usage:
    python3 dji_credentials_extractor.py
"""

import os
import shutil
import sys
import subprocess
import time
import re
import json
from pathlib import Path
from datetime import datetime

# Configuration
SCRIPT_DIR = Path(__file__).parent
APK_NAME = "com.dji.home.apk"
AVD_NAME = "dji_extractor"
SYSTEM_IMAGE = "system-images;android-34;google_apis;arm64-v8a"
OUTPUT_FILE = SCRIPT_DIR / "dji_credentials.txt"
ENV_FILE = SCRIPT_DIR / ".env"

# Colors for terminal
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}\n")


def print_step(step, text):
    print(f"{Colors.CYAN}[{step}]{Colors.END} {text}")


def print_success(text):
    print(f"{Colors.GREEN}[✓]{Colors.END} {text}")


def print_error(text):
    print(f"{Colors.FAIL}[✗]{Colors.END} {text}")


def print_warning(text):
    print(f"{Colors.WARNING}[!]{Colors.END} {text}")


def print_info(text):
    print(f"{Colors.BLUE}[i]{Colors.END} {text}")


def run_command(cmd, check=True, capture=True, timeout=None):
    """Execute a shell command."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=check,
            capture_output=capture,
            text=True,
            timeout=timeout
        )
        return result.stdout.strip() if capture else None
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return None
    except subprocess.TimeoutExpired:
        return None


def _sdk_has_emulator(android_home):
    """Return True if the SDK at android_home has the emulator binary."""
    if not android_home:
        return False
    return Path(f"{android_home}/emulator/emulator").exists()


def _sdk_has_system_image(android_home):
    """Return True if the required system image exists under android_home."""
    if not android_home:
        return False
    return Path(f"{android_home}/system-images/android-34/google_apis/arm64-v8a").is_dir()


def check_android_studio_or_sdk():
    """Check for Android Studio or a valid Android SDK with emulator."""
    print_step("1.1", "Checking for Android Studio / Android SDK...")

    # Android Studio installs SDK here on macOS
    studio_sdk = Path.home() / "Library/Android/sdk"
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not android_home:
        android_home = str(studio_sdk) if studio_sdk.exists() else None
    if not android_home:
        for path in [Path.home() / "Android/Sdk", Path("/opt/android-sdk")]:
            if path.exists():
                android_home = str(path)
                break

    if android_home and _sdk_has_emulator(android_home):
        print_success("Android SDK with Emulator found")
        return True
    if android_home:
        print_warning("Android SDK found but Emulator component missing (will install if possible)")
    else:
        print_warning("Android Studio / SDK not found (will try to install command-line tools via Homebrew)")
    return False


def check_homebrew():
    """Check if Homebrew is installed."""
    print_step("1.2", "Checking for Homebrew...")

    if run_command("which brew", check=False):
        print_success("Homebrew is installed")
        return True

    print_warning("Homebrew is not installed")
    print_info("Installing Homebrew...")

    install_cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    os.system(install_cmd)

    return run_command("which brew", check=False) is not None


def check_java():
    """Check if Java is installed."""
    print_step("1.3", "Checking for Java...")

    java_version = run_command("java -version 2>&1 | head -1", check=False)
    if java_version and "version" in java_version.lower():
        print_success(f"Java is installed: {java_version}")
        return True

    print_warning("Java is not installed")
    print_info("Installing Java via Homebrew...")
    run_command("brew install openjdk@17", check=False)
    run_command("sudo ln -sfn /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk /Library/Java/JavaVirtualMachines/openjdk-17.jdk", check=False)

    return True


def setup_android_sdk():
    """Setup Android SDK and emulator."""
    print_step("1.4", "Configuring Android SDK...")

    # Check if Android SDK exists
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")

    if not android_home:
        # Try common locations
        possible_paths = [
            Path.home() / "Library/Android/sdk",
            Path.home() / "Android/Sdk",
            Path("/opt/android-sdk"),
        ]
        for path in possible_paths:
            if path.exists():
                android_home = str(path)
                break

    if not android_home or not Path(android_home).exists():
        print_warning("Android SDK not found")
        print_info("Installing Android SDK...")

        # Install via Homebrew
        run_command("brew install --cask android-commandlinetools", check=False)
        android_home = str(Path.home() / "Library/Android/sdk")
        Path(android_home).mkdir(parents=True, exist_ok=True)

    # Set environment variables
    os.environ["ANDROID_HOME"] = android_home
    os.environ["ANDROID_SDK_ROOT"] = android_home

    # Update PATH
    platform_tools = f"{android_home}/platform-tools"
    emulator_path = f"{android_home}/emulator"
    cmdline_tools = f"{android_home}/cmdline-tools/latest/bin"

    os.environ["PATH"] = f"{platform_tools}:{emulator_path}:{cmdline_tools}:{os.environ['PATH']}"

    print_success(f"ANDROID_HOME = {android_home}")

    # Check for sdkmanager
    sdkmanager = None
    possible_sdkmanager = [
        f"{android_home}/cmdline-tools/latest/bin/sdkmanager",
        f"{android_home}/tools/bin/sdkmanager",
        "/opt/homebrew/share/android-commandlinetools/cmdline-tools/latest/bin/sdkmanager",
    ]

    for sm in possible_sdkmanager:
        if Path(sm).exists():
            sdkmanager = sm
            break

    if not sdkmanager:
        print_info("Installing command-line tools...")
        run_command("brew install --cask android-commandlinetools", check=False)
        sdkmanager = "/opt/homebrew/share/android-commandlinetools/cmdline-tools/latest/bin/sdkmanager"

    if not Path(sdkmanager).exists():
        print_error("Could not find sdkmanager")
        print_error("Please install Android Studio from https://developer.android.com/studio (includes SDK and Emulator)")
        sys.exit(1)

    # Install required components
    print_step("1.5", "Installing required SDK components...")

    components = [
        "platform-tools",
        "emulator",
        "platforms;android-34",
        SYSTEM_IMAGE,
    ]

    # Force install into ANDROID_HOME (Homebrew sdkmanager otherwise uses its own prefix)
    sdk_root_arg = f'--sdk_root="{android_home}"'
    for component in components:
        print_info(f"Installing {component}...")
        run_command(f'yes | "{sdkmanager}" {sdk_root_arg} "{component}"', check=False)

    if not _sdk_has_emulator(android_home):
        print_error("Emulator binary not found after installing components.")
        print_error("Please install Android Studio from https://developer.android.com/studio and ensure SDK + Emulator are installed.")
        sys.exit(1)

    if not _sdk_has_system_image(android_home):
        print_error("System image (android-34 google_apis arm64-v8a) not found after install.")
        print_error("Please install Android Studio from https://developer.android.com/studio and install the SDK + Emulator system image.")
        sys.exit(1)

    return android_home, sdkmanager


def create_avd(android_home, sdkmanager):
    """Create Android Virtual Device."""
    print_step("2.1", f"Creating emulator '{AVD_NAME}'...")

    avdmanager = sdkmanager.replace("sdkmanager", "avdmanager")
    sdk_root_arg = f'--sdk_root="{android_home}"'

    # Check if AVD already exists
    avd_list = run_command(f'"{avdmanager}" {sdk_root_arg} list avd', check=False) or ""

    if AVD_NAME in avd_list:
        print_success(f"Emulator '{AVD_NAME}' already exists")
        return True

    # Create AVD (use --sdk_root so AVD points at our SDK's system image)
    print_info("Creating a new emulator...")

    create_cmd = f'echo "no" | "{avdmanager}" {sdk_root_arg} create avd -n {AVD_NAME} -k "{SYSTEM_IMAGE}" --device "pixel_6"'
    result = run_command(create_cmd, check=False)

    if result is None:
        # Try alternative approach
        create_cmd = f'"{avdmanager}" {sdk_root_arg} create avd -n {AVD_NAME} -k "{SYSTEM_IMAGE}" --device "pixel_6" --force'
        run_command(create_cmd, check=False)

    print_success("Emulator created")
    return True


def start_emulator(android_home):
    """Start the Android emulator."""
    print_step("2.2", "Starting the emulator...")

    if not _sdk_has_system_image(android_home):
        print_error("System image not found in SDK. The AVD needs android-34 google_apis arm64-v8a.")
        print_info("Re-run this script to reinstall components into ANDROID_HOME, or install Android Studio.")
        return False

    emulator_path = f"{android_home}/emulator/emulator"
    if not Path(emulator_path).exists():
        # Resolve via PATH (set earlier in setup_android_sdk) so Popen gets a full path
        emulator_path = shutil.which("emulator") or emulator_path
    if not emulator_path or (emulator_path == f"{android_home}/emulator/emulator" and not Path(emulator_path).exists()):
        print_error("Emulator binary not found. Check ANDROID_HOME and that SDK components are installed.")
        return False

    # Check if emulator is already running
    devices = run_command("adb devices", check=False) or ""
    if "emulator" in devices and "device" in devices:
        print_success("Emulator is already running")
        return True

    # Start emulator in background (log stderr so we can debug if it fails)
    print_info("Launching the emulator (this may take a few minutes)...")
    emulator_log = SCRIPT_DIR / "emulator.log"

    with open(emulator_log, "w") as logf:
        proc = subprocess.Popen(
            [emulator_path, "-avd", AVD_NAME, "-no-snapshot", "-writable-system", "-no-audio"],
            stdout=logf,
            stderr=subprocess.STDOUT,
            cwd=SCRIPT_DIR,
            env={**os.environ, "ANDROID_HOME": android_home, "ANDROID_SDK_ROOT": android_home},
        )

    # Wait for emulator to appear (adb wait-for-device)
    print_info("Waiting for emulator to start...")
    run_command("adb wait-for-device", timeout=90, check=False)

    max_wait = 420  # 7 minutes (first boot of arm64 image can be slow)
    start_time = time.time()

    while time.time() - start_time < max_wait:
        if proc.poll() is not None:
            print()
            print_error("Emulator process exited unexpectedly. Check emulator.log for details.")
            return False
        devices = run_command("adb devices", check=False) or ""
        if "emulator" in devices and "device" in devices:
            if "offline" in devices:
                time.sleep(5)
                print(".", end="", flush=True)
                continue
            # Check if boot completed
            boot_completed = run_command("adb shell getprop sys.boot_completed", check=False)
            if boot_completed and boot_completed.strip() == "1":
                print_success("Emulator started and ready!")
                time.sleep(5)  # Give it a few more seconds
                return True

        time.sleep(5)
        print(".", end="", flush=True)

    print()
    print_error("Timeout: emulator did not start in time")
    print_info(f"Check {emulator_log} for emulator output.")
    return False


def setup_root():
    """Setup root access on emulator."""
    print_step("2.3", "Setting up root access...")

    run_command("adb root", check=False)
    time.sleep(3)

    # Verify root
    whoami = run_command("adb shell whoami", check=False)
    if whoami and "root" in whoami:
        print_success("Root access enabled")
        return True

    print_warning("Limited root access (normal for some emulators)")
    return True


def install_apk():
    """Install DJI Home APK."""
    print_step("3.1", "Installing DJI Home APK...")

    apk_path = SCRIPT_DIR / APK_NAME

    # Also check for alternative names
    if not apk_path.exists():
        for f in SCRIPT_DIR.glob("*.apk"):
            if "dji" in f.name.lower() and "home" in f.name.lower():
                apk_path = f
                break

    if not apk_path.exists():
        # List APK files in directory
        apk_files = list(SCRIPT_DIR.glob("*.apk"))
        if apk_files:
            print_info(f"APKs found: {[f.name for f in apk_files]}")
            apk_path = apk_files[0]
        else:
            print_error(f"APK not found!")
            print_info(f"Please place the DJI Home APK in: {SCRIPT_DIR}")
            print_info("You can download it from APKMirror or APKPure")
            sys.exit(1)

    print_info(f"Installing {apk_path.name}...")

    # Check if already installed
    packages = run_command("adb shell pm list packages | grep dji.home", check=False)
    if packages and "com.dji.home" in packages:
        print_success("DJI Home is already installed")
        return True

    # Install APK
    result = run_command(f'adb install -r "{apk_path}"', check=False)

    if result and "Success" in result:
        print_success("APK installed successfully")
        return True

    print_error(f"Installation error: {result}")
    return False


def launch_app():
    """Launch DJI Home app."""
    print_step("3.2", "Launching DJI Home app...")

    run_command("adb shell am start -n com.dji.home/.MainActivity", check=False)
    time.sleep(5)

    print_success("App launched")
    return True


def wait_for_login():
    """Wait for user to login."""
    print_header("LOGIN REQUIRED")

    print(f"""
{Colors.WARNING}The DJI Home app is now open in the emulator.

Please log in to your DJI account in the app.

Once logged in and on the main screen (with your robot visible),
press ENTER to continue...{Colors.END}
""")

    input(f"{Colors.CYAN}>>> Press ENTER when you are logged in... {Colors.END}")

    # Verify app is running and logged in
    time.sleep(2)
    return True


def extract_credentials():
    """Extract credentials from app memory."""
    print_header("EXTRACTING CREDENTIALS")

    # Re-enable root access (may have been lost)
    print_step("4.0", "Enabling root access...")
    run_command("adb root", check=False)
    time.sleep(3)

    # Verify root
    whoami = run_command("adb shell whoami", check=False)
    if whoami and "root" in whoami:
        print_success("Root access OK")
    else:
        print_warning("Limited root access - trying anyway...")

    print_step("4.1", "Searching for DJI Home process...")

    # Get PID
    pid = run_command("adb shell pidof com.dji.home", check=False)

    if not pid:
        print_error("App not found. Is it running?")
        return None

    pid = pid.strip().split()[0]  # Get first PID if multiple
    print_success(f"Process found: PID {pid}")

    print_step("4.2", "Extracting memory (this may take a moment)...")

    # Calculate skip value (0x12c00000 / 1048576 = 300)
    skip_value = 0x12c00000 // 1048576  # = 300

    # Dump memory - use simpler command
    dump_cmd = f"dd if=/proc/{pid}/mem bs=1048576 skip={skip_value} count=500 of=/data/local/tmp/heap.bin"

    print_info(f"Command: {dump_cmd}")

    result = run_command(f'adb shell "{dump_cmd}" 2>&1', check=False, timeout=180)

    # Check if file was created
    file_check = run_command("adb shell ls -la /data/local/tmp/heap.bin", check=False)

    if not file_check or "No such file" in str(file_check):
        print_error("Memory dump failed")
        print_info(f"Result: {result}")

        # Try alternative method with cat
        print_info("Trying alternative method...")
        alt_cmd = f"cat /proc/{pid}/maps | head -5"
        maps = run_command(f'adb shell "{alt_cmd}"', check=False)
        print_info(f"Memory maps: {maps}")

        return None

    print_success(f"Memory extracted: {file_check}")

    print_step("4.3", "Analyzing data...")

    # Extract strings and search for credentials
    extract_cmd = """
    cd /data/local/tmp &&
    echo "=== USER_TOKEN ===" &&
    strings heap.bin | grep -o 'US_[A-Za-z0-9_-]\\{50,\\}' | head -1 &&
    echo "=== USER_ID ===" &&
    strings heap.bin | grep -A 1 'flutter.user_id' | grep -o '[0-9]\\{15,\\}' | head -1 &&
    echo "=== USER_EMAIL ===" &&
    strings heap.bin | grep -A 1 'flutter.user_email' | grep -oE '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}' | head -1 &&
    echo "=== USER_NAME ===" &&
    strings heap.bin | grep -o 'djiuser_[A-Za-z0-9_]*' | head -1 &&
    echo "=== DEVICE_SN ===" &&
    (strings heap.bin | grep -oE '"sn":"[A-Z0-9]+"|"device_sn":"[A-Z0-9]+"' | head -1 | grep -oE '[A-Z0-9]{10,}' || strings heap.bin | grep -oE '[0-9][A-Z]{3,4}[A-Z0-9]{8,}' | sort | uniq -c | sort -rn | head -1 | sed 's/^[[:space:]]*[0-9]*[[:space:]]*//' ) &&
    echo "=== PAIR_UUID ===" &&
    strings heap.bin | grep -oE 'ROMO-[A-Z0-9]+' | head -1 &&
    echo "=== IOT_URL ===" &&
    strings heap.bin | grep -o 'things-access[a-z0-9.-]*\\.iot\\.djigate\\.com' | head -1 &&
    echo "=== DEVICE_UUID ===" &&
    strings heap.bin | grep -A 1 'flutter._deviceUUIDKey' | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1 &&
    rm -f heap.bin
    """

    output = run_command(f'adb shell "{extract_cmd}"', check=False, timeout=60)

    if not output:
        print_error("Extraction failed")
        return None

    # Parse output
    credentials = {}
    current_key = None

    for line in output.split('\n'):
        line = line.strip()
        if line.startswith("=== ") and line.endswith(" ==="):
            current_key = line[4:-4].lower()
        elif line and current_key:
            credentials[current_key] = line
            current_key = None

    # Validate
    if not credentials.get("user_token"):
        print_error("User token not found")
        print_info("Make sure you are logged in to the app")
        return None

    print_success("Credentials extracted successfully!")

    return credentials


def test_api(credentials):
    """Test the extracted credentials with DJI API."""
    print_step("4.4", "Testing credentials with DJI API...")

    try:
        import requests
    except ImportError:
        run_command("pip3 install requests", check=False)
        import requests

    user_token = credentials.get("user_token")
    if not user_token:
        print_warning("Cannot test without user_token")
        return credentials

    headers = {
        "x-member-token": user_token,
        "X-DJI-locale": "en_US",
    }

    # Get MQTT credentials
    try:
        response = requests.get(
            "https://home-api-vg.djigate.com/app/api/v1/users/auth/token",
            params={"reason": "mqtt"},
            headers=headers,
            timeout=30
        )

        data = response.json()

        if data.get("result", {}).get("code") == 0:
            mqtt_data = data["data"]
            credentials["mqtt_domain"] = mqtt_data.get("mqtt_domain")
            credentials["mqtt_port"] = mqtt_data.get("mqtt_port")
            credentials["mqtt_user_uuid"] = mqtt_data.get("user_uuid")
            credentials["api_working"] = True
            print_success("API is working! MQTT credentials retrieved")
        else:
            credentials["api_working"] = False
            print_warning(f"API error: {data.get('result', {}).get('message')}")

    except Exception as e:
        credentials["api_working"] = False
        print_warning(f"API error: {e}")

    # Try to get device list if SN not found
    if not credentials.get("device_sn"):
        print_step("4.5", "Retrieving devices via API...")
        try:
            # Try homes endpoint
            response = requests.get(
                "https://home-api-vg.djigate.com/app/api/v1/homes",
                headers=headers,
                timeout=30
            )
            data = response.json()

            if data.get("result", {}).get("code") == 0:
                homes = data.get("data", {}).get("homes", [])
                for home in homes:
                    devices = home.get("devices", [])
                    for device in devices:
                        sn = device.get("sn") or device.get("device_sn")
                        if sn:
                            credentials["device_sn"] = sn
                            credentials["device_name"] = device.get("name", "")
                            print_success(f"Device found via API: {sn} ({credentials['device_name']})")
                            break
                    if credentials.get("device_sn"):
                        break
        except Exception as e:
            print_warning(f"Could not retrieve devices: {e}")

    return credentials


def save_credentials(credentials):
    """Save credentials to file."""
    print_step("5", "Saving credentials...")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create .env file for mqtt client
    env_content = f"""# DJI Home Credentials - Extracted on {timestamp}
# This file is used by dji_mqtt_client.py

DJI_USER_TOKEN={credentials.get('user_token', '')}
DJI_USER_ID={credentials.get('user_id', '')}
DJI_DEVICE_SN={credentials.get('device_sn', '')}
DJI_API_URL=https://home-api-vg.djigate.com
DJI_LOCALE=en_US
"""

    ENV_FILE.write_text(env_content)
    print_success(f".env file created: {ENV_FILE}")

    # Create human-readable file
    content = f"""
================================================================================
                    DJI HOME CREDENTIALS
                    Extracted on: {timestamp}
================================================================================

USER ACCOUNT
------------
User Token:     {credentials.get('user_token', 'Not found')}
User ID:        {credentials.get('user_id', 'Not found')}
User Email:     {credentials.get('user_email', 'Not found')}
User Name:      {credentials.get('user_name', 'Not found')}
Device UUID:    {credentials.get('device_uuid', 'Not found')}

DEVICE
------
Device SN:      {credentials.get('device_sn', 'Not found')}
Pair UUID:      {credentials.get('pair_uuid', 'Not found')}
IoT URL:        {credentials.get('iot_url', 'Not found')}

MQTT
----
Broker:         {credentials.get('mqtt_domain', 'crobot-mqtt-us.djigate.com')}
Port:           {credentials.get('mqtt_port', 8883)}
Username:       {credentials.get('mqtt_user_uuid', 'Obtained via API')}
Password:       Obtained dynamically via API (expires every ~4h)

API ENDPOINT
------------
URL:            https://home-api-vg.djigate.com/app/api/v1/users/auth/token?reason=mqtt
Header:         x-member-token: <USER_TOKEN>

================================================================================

USAGE:
------
The .env file has been created automatically.
Simply run: python3 dji_mqtt_client.py --subscribe

================================================================================
"""

    OUTPUT_FILE.write_text(content)
    print_success(f"Credentials saved to: {OUTPUT_FILE}")

    return content


def cleanup():
    """Cleanup emulator."""
    print_step("6", "Cleanup...")

    response = input(f"{Colors.CYAN}Do you want to stop the emulator? (y/N): {Colors.END}")

    if response.lower() in ['y', 'yes']:
        run_command("adb emu kill", check=False)
        print_success("Emulator stopped")
    else:
        print_info("Emulator is still running")


def main():
    print_header("DJI HOME CREDENTIALS EXTRACTOR")

    print(f"""
{Colors.BLUE}This script will extract your DJI Home credentials to enable
integration with Home Assistant via MQTT.

Prerequisites:
- Android Studio (or Android SDK with Emulator) — https://developer.android.com/studio
- The DJI Home APK must be in the same folder as this script
- An internet connection
- Your DJI account

The process takes about 5-10 minutes.{Colors.END}
""")

    input(f"{Colors.CYAN}>>> Press ENTER to start... {Colors.END}")

    try:
        # Step 1: Setup environment
        print_header("STEP 1: ENVIRONMENT SETUP")

        check_android_studio_or_sdk()
        check_homebrew()
        check_java()
        android_home, sdkmanager = setup_android_sdk()

        # Step 2: Setup emulator
        print_header("STEP 2: EMULATOR SETUP")

        create_avd(android_home, sdkmanager)

        if not start_emulator(android_home):
            print_error("Could not start emulator")
            sys.exit(1)

        setup_root()

        # Step 3: Install and launch app
        print_header("STEP 3: APP INSTALLATION")

        if not install_apk():
            print_error("Could not install APK")
            sys.exit(1)

        launch_app()

        # Step 4: Wait for login and extract
        wait_for_login()

        credentials = extract_credentials()

        if credentials:
            credentials = test_api(credentials)
            content = save_credentials(credentials)

            print_header("RESULT")
            print(content)
        else:
            print_error("Credential extraction failed")
            sys.exit(1)

        # Step 5: Cleanup
        cleanup()

        print_header("DONE!")
        print_success(f"Your credentials are in: {OUTPUT_FILE}")

    except KeyboardInterrupt:
        print("\n")
        print_warning("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
