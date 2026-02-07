#!/usr/bin/env python3
"""
DJI Fly Credentials Extractor
===============================

Automated script to extract DJI Fly credentials from an Android emulator.
These credentials enable access to DJI's cloud APIs for flight records,
drone telemetry, and account integration.

Prerequisites:
- macOS
- Android Studio (or Android SDK with Emulator)
- The DJI Fly APK in the same folder as this script
- Internet connection

How to get the DJI Fly APK:
1. Go to https://www.apkmirror.com/apk/dji-technology-co-ltd/dji-fly/
   or https://apkpure.com/dji-fly/dji.go.v5
2. Download the APK — make sure it's the arm64-v8a variant (~700 MB)
3. Place it in the same directory as this script
4. Rename it to 'dji.go.v5.apk' (or any name containing 'fly' or 'go.v5')

The script will:
1. Install Android SDK and emulator if needed
2. Create and launch a rooted Android emulator
3. Install the DJI Fly APK
4. Ask you to log in to the app
5. Extract your credentials from memory
6. Save everything to a file

Usage:
    python3 dji_fly_credentials_extractor.py
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
APK_NAME = "dji.go.v5.apk"
PACKAGE_NAME = "dji.go.v5"
AVD_NAME = "dji_fly_extractor"
SYSTEM_IMAGE = "system-images;android-34;google_apis;arm64-v8a"
OUTPUT_FILE = SCRIPT_DIR / "dji_fly_credentials.txt"
ENV_FILE = SCRIPT_DIR / ".env.dji_fly"

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

    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")

    if not android_home:
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

        run_command("brew install --cask android-commandlinetools", check=False)
        android_home = str(Path.home() / "Library/Android/sdk")
        Path(android_home).mkdir(parents=True, exist_ok=True)

    os.environ["ANDROID_HOME"] = android_home
    os.environ["ANDROID_SDK_ROOT"] = android_home

    platform_tools = f"{android_home}/platform-tools"
    emulator_path = f"{android_home}/emulator"
    cmdline_tools = f"{android_home}/cmdline-tools/latest/bin"

    os.environ["PATH"] = f"{platform_tools}:{emulator_path}:{cmdline_tools}:{os.environ['PATH']}"

    print_success(f"ANDROID_HOME = {android_home}")

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

    print_step("1.5", "Installing required SDK components...")

    components = [
        "platform-tools",
        "emulator",
        "platforms;android-34",
        SYSTEM_IMAGE,
    ]

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


def _avd_exists(avd_name):
    """Check if an AVD exists on disk."""
    avd_dir = Path.home() / ".android" / "avd"
    return (avd_dir / f"{avd_name}.ini").exists()


def create_avd(android_home, sdkmanager):
    """Create Android Virtual Device."""
    print_step("2.1", f"Creating emulator '{AVD_NAME}'...")

    if _avd_exists(AVD_NAME):
        print_success(f"Emulator '{AVD_NAME}' already exists")
        return True

    avdmanager = sdkmanager.replace("sdkmanager", "avdmanager")

    print_info("Creating a new emulator...")

    # Try with ANDROID_SDK_ROOT env var (more reliable than --sdk_root flag)
    env_with_sdk = f'ANDROID_SDK_ROOT="{android_home}" ANDROID_HOME="{android_home}"'

    create_cmd = f'{env_with_sdk} echo "no" | "{avdmanager}" create avd -n {AVD_NAME} -k "{SYSTEM_IMAGE}" --device "pixel_6"'
    result = run_command(create_cmd, check=False)

    if not _avd_exists(AVD_NAME):
        # Retry with --force
        print_info("Retrying with --force...")
        create_cmd = f'{env_with_sdk} "{avdmanager}" create avd -n {AVD_NAME} -k "{SYSTEM_IMAGE}" --device "pixel_6" --force'
        run_command(create_cmd, check=False)

    if not _avd_exists(AVD_NAME):
        # Last resort: try with --sdk_root
        print_info("Retrying with --sdk_root flag...")
        sdk_root_arg = f'--sdk_root="{android_home}"'
        create_cmd = f'echo "no" | "{avdmanager}" {sdk_root_arg} create avd -n {AVD_NAME} -k "{SYSTEM_IMAGE}" --device "pixel_6" --force'
        run_command(create_cmd, check=False)

    if not _avd_exists(AVD_NAME):
        print_error(f"Failed to create AVD '{AVD_NAME}'.")
        print_info("You can try manually: avdmanager create avd -n dji_fly_extractor -k 'system-images;android-34;google_apis;arm64-v8a' --device pixel_6")
        return False

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
        emulator_path = shutil.which("emulator") or emulator_path
    if not emulator_path or (emulator_path == f"{android_home}/emulator/emulator" and not Path(emulator_path).exists()):
        print_error("Emulator binary not found. Check ANDROID_HOME and that SDK components are installed.")
        return False

    devices = run_command("adb devices", check=False) or ""
    if "emulator" in devices and "device" in devices:
        print_success("Emulator is already running")
        return True

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

    print_info("Waiting for emulator to start...")
    run_command("adb wait-for-device", timeout=90, check=False)

    max_wait = 420  # 7 minutes
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
            boot_completed = run_command("adb shell getprop sys.boot_completed", check=False)
            if boot_completed and boot_completed.strip() == "1":
                print_success("Emulator started and ready!")
                time.sleep(5)
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

    whoami = run_command("adb shell whoami", check=False)
    if whoami and "root" in whoami:
        print_success("Root access enabled")
        return True

    print_warning("Limited root access (normal for some emulators)")
    return True


def install_apk():
    """Install DJI Fly APK."""
    print_step("3.1", "Installing DJI Fly APK...")

    apk_path = SCRIPT_DIR / APK_NAME

    # Also check for alternative names
    if not apk_path.exists():
        for f in SCRIPT_DIR.glob("*.apk"):
            name_lower = f.name.lower()
            if "dji" in name_lower and ("fly" in name_lower or "go.v5" in name_lower):
                apk_path = f
                break

    if not apk_path.exists():
        # No DJI Fly APK found — do NOT fall back to unrelated APKs
        other_apks = list(SCRIPT_DIR.glob("*.apk"))
        if other_apks:
            print_warning(f"APKs in directory: {[f.name for f in other_apks]}")
            print_warning("None of these appear to be DJI Fly (expected 'dji.go.v5.apk' or a file with 'fly' in the name)")
        print_error("DJI Fly APK not found!")
        print_info(f"Please download the DJI Fly APK and place it in: {SCRIPT_DIR}")
        print_info("")
        print_info("  Download from:")
        print_info("    https://www.apkmirror.com/apk/dji-technology-co-ltd/dji-fly/")
        print_info("    https://apkpure.com/dji-fly/dji.go.v5")
        print_info("")
        print_info(f"  Then rename it to '{APK_NAME}' or any name containing 'fly' or 'go.v5'")
        sys.exit(1)

    print_info(f"Installing {apk_path.name} (DJI Fly is ~700MB, this may take a minute)...")

    # Check if already installed
    packages = run_command(f"adb shell pm list packages | grep {PACKAGE_NAME}", check=False)
    if packages and PACKAGE_NAME in packages:
        print_success("DJI Fly is already installed")
        return True

    # Install APK (use -g to grant all permissions)
    result = run_command(f'adb install -r -g "{apk_path}"', check=False, timeout=300)

    if result and "Success" in result:
        print_success("APK installed successfully")
        return True

    print_error(f"Installation error: {result}")
    return False


def launch_app():
    """Launch DJI Fly app."""
    print_step("3.2", "Launching DJI Fly app...")

    # Discover and use the launcher activity
    activity = run_command(
        f'adb shell cmd package resolve-activity --brief {PACKAGE_NAME} 2>/dev/null | tail -1',
        check=False
    )

    if activity and "/" in activity:
        print_info(f"Launcher activity: {activity}")
        run_command(f'adb shell am start -n "{activity}"', check=False)
    else:
        # Fallback: use monkey to launch
        print_info("Using monkey launcher...")
        run_command(f"adb shell monkey -p {PACKAGE_NAME} -c android.intent.category.LAUNCHER 1", check=False)

    time.sleep(8)  # DJI Fly takes longer to start than DJI Home
    print_success("App launched")
    return True


def wait_for_login():
    """Wait for user to login."""
    print_header("LOGIN REQUIRED")

    print(f"""
{Colors.WARNING}The DJI Fly app is now open in the emulator.

Please:
1. Log in to your DJI account in the app
2. Wait for the main screen to fully load
3. If you have drones paired to your account, they should appear
   (you don't need a physical drone connected)

Once logged in and on the main screen,
press ENTER to continue...{Colors.END}
""")

    input(f"{Colors.CYAN}>>> Press ENTER when you are logged in... {Colors.END}")

    time.sleep(2)
    return True


def extract_credentials():
    """Extract credentials from app memory."""
    print_header("EXTRACTING CREDENTIALS")

    # Re-enable root access
    print_step("4.0", "Enabling root access...")
    run_command("adb root", check=False)
    time.sleep(3)

    whoami = run_command("adb shell whoami", check=False)
    if whoami and "root" in whoami:
        print_success("Root access OK")
    else:
        print_warning("Limited root access - trying anyway...")

    print_step("4.1", f"Searching for {PACKAGE_NAME} process...")

    pid = run_command(f"adb shell pidof {PACKAGE_NAME}", check=False)

    if not pid:
        print_error("App not found. Is it running?")
        return None

    pid = pid.strip().split()[0]
    print_success(f"Process found: PID {pid}")

    print_step("4.2", "Extracting memory (DJI Fly is large, this may take a while)...")

    # DJI Fly is a native app with a larger heap footprint
    # Scan a wider memory range to find credentials
    skip_value = 0x12c00000 // 1048576  # = 300
    count = 800  # Larger scan than DJI Home (DJI Fly is a bigger app)

    dump_cmd = f"dd if=/proc/{pid}/mem bs=1048576 skip={skip_value} count={count} of=/data/local/tmp/heap.bin"

    print_info(f"Command: {dump_cmd}")

    result = run_command(f'adb shell "{dump_cmd}" 2>&1', check=False, timeout=300)

    file_check = run_command("adb shell ls -la /data/local/tmp/heap.bin", check=False)

    if not file_check or "No such file" in str(file_check):
        print_error("Memory dump failed")
        print_info(f"Result: {result}")

        print_info("Trying alternative method...")
        alt_cmd = f"cat /proc/{pid}/maps | head -5"
        maps = run_command(f'adb shell "{alt_cmd}"', check=False)
        print_info(f"Memory maps: {maps}")

        return None

    print_success(f"Memory extracted: {file_check}")

    print_step("4.3", "Analyzing data...")

    # DJI Fly is a native Android app (Java/Kotlin), not Flutter.
    # Token format is the same (DJI SSO uses US_ prefix).
    # Other patterns differ from DJI Home.
    # IMPORTANT: use ';' not '&&' so empty results don't break the chain
    # (e.g. user has no drone paired — drone fields will be empty and that's OK)
    extract_cmd = r"""
    cd /data/local/tmp ;
    echo "=== USER_TOKEN ===" ;
    strings heap.bin | grep -o 'US_[A-Za-z0-9_-]\{50,\}' | head -1 ;
    echo "=== USER_ID ===" ;
    strings heap.bin | grep -oE '"user_id"[[:space:]]*:[[:space:]]*"?[0-9]{10,}"?' | head -1 | grep -oE '[0-9]{10,}' ;
    strings heap.bin | grep -oE '"uid"[[:space:]]*:[[:space:]]*"?[0-9]{10,}"?' | head -1 | grep -oE '[0-9]{10,}' ;
    strings heap.bin | grep -oE '"member_uid"[[:space:]]*:[[:space:]]*"?[0-9]{10,}"?' | head -1 | grep -oE '[0-9]{10,}' ;
    echo "=== USER_EMAIL ===" ;
    strings heap.bin | grep -oE '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}' | head -1 ;
    echo "=== USER_NAME ===" ;
    strings heap.bin | grep -oE '"nickname"[[:space:]]*:[[:space:]]*"[^"]{2,30}"' | head -1 | sed 's/.*"nickname"[[:space:]]*:[[:space:]]*"//;s/"$//' ;
    strings heap.bin | grep -o 'djiuser_[A-Za-z0-9_]*' | head -1 ;
    echo "=== DRONE_SN ===" ;
    strings heap.bin | grep -oE '"sn"[[:space:]]*:[[:space:]]*"[A-Z0-9]{10,}"' | head -1 | grep -oE '[A-Z0-9]{10,}' ;
    strings heap.bin | grep -oE '"serial_number"[[:space:]]*:[[:space:]]*"[A-Z0-9]{10,}"' | head -1 | grep -oE '[A-Z0-9]{10,}' ;
    strings heap.bin | grep -oE '"device_sn"[[:space:]]*:[[:space:]]*"[A-Z0-9]{10,}"' | head -1 | grep -oE '[A-Z0-9]{10,}' ;
    echo "=== DRONE_MODEL ===" ;
    strings heap.bin | grep -oE '"model_name"[[:space:]]*:[[:space:]]*"[^"]{3,40}"' | head -1 | sed 's/.*"model_name"[[:space:]]*:[[:space:]]*"//;s/"$//' ;
    strings heap.bin | grep -oE '"product_type"[[:space:]]*:[[:space:]]*"[^"]{3,40}"' | head -1 | sed 's/.*"product_type"[[:space:]]*:[[:space:]]*"//;s/"$//' ;
    strings heap.bin | grep -oE 'DJI (Mini|Mavic|Air|Avata|FPV|Phantom|Inspire|Matrice)[A-Za-z0-9 ]*' | head -1 ;
    echo "=== ACCOUNT_TOKEN ===" ;
    strings heap.bin | grep -oE '"account_token"[[:space:]]*:[[:space:]]*"[A-Za-z0-9_-]{20,}"' | head -1 | sed 's/.*"account_token"[[:space:]]*:[[:space:]]*"//;s/"$//' ;
    echo "=== OPENAPI_TOKEN ===" ;
    strings heap.bin | grep -oE '"openapi_token"[[:space:]]*:[[:space:]]*"[A-Za-z0-9_-]{20,}"' | head -1 | sed 's/.*"openapi_token"[[:space:]]*:[[:space:]]*"//;s/"$//' ;
    echo "=== API_URLS ===" ;
    strings heap.bin | grep -oE 'https?://[a-z0-9.-]*\.dji(gate|service|cdn)?\.com[a-z0-9/._-]*' | sort -u | head -20 ;
    echo "=== DEVICE_UUID ===" ;
    strings heap.bin | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -3 ;
    rm -f heap.bin
    """

    # Run via adb shell with stdin to avoid quoting hell with nested double quotes
    try:
        proc = subprocess.run(
            ["adb", "shell"],
            input=extract_cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = proc.stdout.strip()
    except subprocess.TimeoutExpired:
        output = None

    if not output:
        print_error("Extraction failed")
        # Show stderr for debugging
        if proc and proc.stderr:
            print_info(f"stderr: {proc.stderr.strip()[:200]}")
        return None

    # Parse output — each section uses ';' so empty results don't break the chain.
    # Multiple fallback commands per section means we may get several values;
    # keep the first non-empty one for scalar fields, collect all for list fields.
    credentials = {}
    current_key = None
    list_keys = {"api_urls", "device_uuid"}

    for line in output.split('\n'):
        line = line.strip()
        if line.startswith("=== ") and line.endswith(" ==="):
            current_key = line[4:-4].lower()
        elif line and current_key:
            if current_key in list_keys:
                lst = credentials.get(current_key, [])
                if line not in lst:
                    lst.append(line)
                credentials[current_key] = lst
            elif current_key not in credentials:
                # First non-empty value wins (subsequent fallback lines are ignored)
                credentials[current_key] = line

    # Validate — only the token is truly required
    if not credentials.get("user_token"):
        print_error("User token not found")
        print_info("Make sure you are fully logged in to the DJI Fly app")
        return None

    # It's OK if drone fields are empty (user may not own a drone)
    if not credentials.get("drone_sn"):
        print_warning("No drone serial number found (normal if you don't have a drone paired)")

    print_success("Credentials extracted successfully!")

    # Print summary
    for key, value in credentials.items():
        if isinstance(value, list):
            print_info(f"  {key}: {len(value)} entries found")
        elif key == "user_token":
            print_info(f"  {key}: {value[:20]}...{value[-10:]}")
        else:
            print_info(f"  {key}: {value}")

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
        "User-Agent": "DJIFly",
    }

    # Test 1: Try the account info endpoint
    print_info("Testing account access...")
    try:
        response = requests.get(
            "https://active.dji.com/app/api/v1/member/info",
            headers=headers,
            timeout=30
        )
        data = response.json()
        if data.get("result", {}).get("code") == 0 or data.get("code") == 0:
            member = data.get("data", data)
            credentials["account_verified"] = True
            if member.get("nickname"):
                credentials["user_name"] = member["nickname"]
            if member.get("uid"):
                credentials["user_id"] = str(member["uid"])
            if member.get("email"):
                credentials["user_email"] = member["email"]
            print_success("Account access verified!")
        else:
            print_warning(f"Account API: {data.get('result', {}).get('message', data.get('message', 'Unknown'))}")
    except Exception as e:
        print_warning(f"Account API error: {e}")

    # Test 2: Try to get device/drone list
    print_step("4.5", "Retrieving drone information via API...")
    try:
        response = requests.get(
            "https://active.dji.com/app/api/v1/devices",
            headers=headers,
            timeout=30
        )
        data = response.json()
        if data.get("result", {}).get("code") == 0 or data.get("code") == 0:
            devices = data.get("data", {})
            if isinstance(devices, list):
                for device in devices:
                    sn = device.get("sn") or device.get("serial_number")
                    model = device.get("model_name") or device.get("product_type") or device.get("name")
                    if sn:
                        if not credentials.get("drone_sn"):
                            credentials["drone_sn"] = sn
                        if model:
                            credentials["drone_model"] = model
                        print_success(f"Drone found via API: {sn} ({model or 'Unknown model'})")
    except Exception as e:
        print_warning(f"Device API: {e}")

    # Test 3: Try flight records API
    print_step("4.6", "Checking flight records access...")
    try:
        response = requests.get(
            "https://mydjiflight.dji.com/api/v1/user/flights",
            headers={"Authorization": f"Bearer {user_token}", **headers},
            params={"page": 1, "page_size": 5},
            timeout=30
        )
        data = response.json()
        if response.status_code == 200 and (data.get("result", {}).get("code") == 0 or data.get("code") == 0):
            flights = data.get("data", {}).get("flights", data.get("data", []))
            count = len(flights) if isinstance(flights, list) else 0
            credentials["flight_records_accessible"] = True
            credentials["recent_flights_count"] = count
            print_success(f"Flight records accessible ({count} recent flights)")
        else:
            credentials["flight_records_accessible"] = False
            print_warning(f"Flight records: {data.get('message', 'Not available or different API format')}")
    except Exception as e:
        credentials["flight_records_accessible"] = False
        print_warning(f"Flight records API: {e}")

    return credentials


def save_credentials(credentials):
    """Save credentials to file."""
    print_step("5", "Saving credentials...")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Create .env file
    api_urls = credentials.get('api_urls', [])
    api_urls_str = ",".join(api_urls) if isinstance(api_urls, list) else str(api_urls)

    env_content = f"""# DJI Fly Credentials - Extracted on {timestamp}
# Generated by dji_fly_credentials_extractor.py

DJI_USER_TOKEN={credentials.get('user_token', '')}
DJI_USER_ID={credentials.get('user_id', '')}
DJI_USER_EMAIL={credentials.get('user_email', '')}
DJI_DRONE_SN={credentials.get('drone_sn', '')}
DJI_DRONE_MODEL={credentials.get('drone_model', '')}
"""

    ENV_FILE.write_text(env_content)
    print_success(f"Env file created: {ENV_FILE}")

    # Create human-readable file
    device_uuids = credentials.get('device_uuid', [])
    if isinstance(device_uuids, list):
        device_uuid_str = "\n                ".join(device_uuids) if device_uuids else "Not found"
    else:
        device_uuid_str = device_uuids or "Not found"

    api_urls_display = "\n                ".join(api_urls) if api_urls else "None discovered"

    content = f"""
================================================================================
                    DJI FLY CREDENTIALS
                    Extracted on: {timestamp}
================================================================================

USER ACCOUNT
------------
User Token:     {credentials.get('user_token', 'Not found')}
User ID:        {credentials.get('user_id', 'Not found')}
User Email:     {credentials.get('user_email', 'Not found')}
User Name:      {credentials.get('user_name', 'Not found')}
Account Token:  {credentials.get('account_token', 'Not found')}
OpenAPI Token:  {credentials.get('openapi_token', 'Not found')}

DRONE
-----
Drone SN:       {credentials.get('drone_sn', 'Not found')}
Drone Model:    {credentials.get('drone_model', 'Not found')}

DEVICE UUIDs
------------
                {device_uuid_str}

API ENDPOINTS (discovered in memory)
-------------------------------------
                {api_urls_display}

API ACCESS
----------
Account Info:       {"✓ Verified" if credentials.get('account_verified') else "✗ Not verified"}
Flight Records:     {"✓ Accessible" if credentials.get('flight_records_accessible') else "✗ Not accessible"}
Recent Flights:     {credentials.get('recent_flights_count', 'N/A')}

================================================================================

USAGE:
------
The .env.dji_fly file has been created automatically.

# Test your token with curl:
curl -H "x-member-token: $DJI_USER_TOKEN" \\
     https://active.dji.com/app/api/v1/member/info

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
    print_header("DJI FLY CREDENTIALS EXTRACTOR")

    print(f"""
{Colors.BLUE}This script will extract your DJI Fly credentials from an
Android emulator. These credentials can be used to access
DJI's cloud APIs for flight records, drone info, and account
integration.

Prerequisites:
- Android Studio (or Android SDK with Emulator)
  https://developer.android.com/studio
- The DJI Fly APK in this folder (see below)
- An internet connection
- Your DJI account

{Colors.WARNING}How to get the DJI Fly APK:{Colors.END}
  1. Go to: https://www.apkmirror.com/apk/dji-technology-co-ltd/dji-fly/
     or:    https://apkpure.com/dji-fly/dji.go.v5
  2. Download the APK (arm64-v8a variant, ~700 MB)
  3. Place it in: {SCRIPT_DIR}
  4. Rename to 'dji.go.v5.apk' (or any name with 'fly' or 'go.v5')

{Colors.WARNING}Note: DJI Fly is ~700MB. Installation in the emulator may
take a few minutes.{Colors.END}

{Colors.BLUE}The process takes about 10-15 minutes.{Colors.END}
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
