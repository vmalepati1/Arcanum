import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from colorama import Fore, Back
from pyvirtualdisplay import Display

PAGE_NAME = "gmail_compose"
TEST_PATH = "/root/"
TARGET_URL = "https://mail.google.com/mail/u/0/#inbox"
RECORDING_PATH = os.path.join(TEST_PATH, "recordings", "gmail_compose.wprgo")
ANNOTATION_PATH = os.path.join(TEST_PATH, "annotations", "gmail_compose_interactive.js")
RESULTS_DIR = os.path.join(TEST_PATH, "Results", PAGE_NAME)
WPR_PATH = "/root/go/pkg/mod/github.com/catapult-project/catapult/web_page_replay_go@v0.0.0-20230901234838-f16ca3c78e46/"
USER_DATA = "/root/userdata/"
REALWORLD_EXT_DIR = "/root/extensions/realworld/"
CHROMEDRIVER_PATH = "/root/chromedriver/chromedriver"
ARCANUM_BIN = "/root/Arcanum/opt/chromium.org/chromium-unstable/chromium-browser-unstable"
EXPECTED_STRINGS = [
    "jane.smith@gmail.com",
    "Test Subject",
    "This is a test message"
]
DEFAULT_EXTENSION = "oadkgbgppkhoaaoepjbcnjejmkknaobg"
FALLBACK_EXTENSION = "pjmfidajplecneclhdghcgdefnmhhlca"


def ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def init_environment():
    os.system("pkill Xvfb")
    os.system("pkill chrome")
    os.system("pkill chromedriver")
    os.system("pkill wpr")
    os.system(f"rm -rf {USER_DATA}")

    display = Display(visible=0, size=(1920, 1080))
    display.start()
    return display


def resolve_extension():
    preferred = os.path.join(REALWORLD_EXT_DIR, DEFAULT_EXTENSION + ".crx")
    fallback = os.path.join(REALWORLD_EXT_DIR, FALLBACK_EXTENSION + ".crx")

    if os.path.exists(preferred):
        return preferred

    if os.path.exists(fallback):
        return fallback

    raise FileNotFoundError(
        f"Neither default ({DEFAULT_EXTENSION}) nor fallback ({FALLBACK_EXTENSION}) extensions were found in {REALWORLD_EXT_DIR}"
    )


def start_wpr():
    if not os.path.exists(WPR_PATH):
        raise FileNotFoundError(f"WPR path not found: {WPR_PATH}")

    os.chdir(WPR_PATH)
    cmd = (
        "nohup /usr/local/go/bin/go run src/wpr.go replay "
        "--http_port=8080 --https_port=8081 "
        f"--inject_scripts=deterministic.js,{ANNOTATION_PATH} "
        f"{RECORDING_PATH} > /tmp/wprgo.log 2>&1 &"
    )
    os.system(cmd)
    time.sleep(3)


def launch_arcanum(extension_path):
    if not os.path.exists(ARCANUM_BIN):
        raise FileNotFoundError(f"Arcanum binary not found at {ARCANUM_BIN}")

    options = webdriver.ChromeOptions()
    options.binary_location = ARCANUM_BIN
    options.add_argument(f"--user-data-dir={USER_DATA}")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors=yes")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--enable-logging")
    options.add_argument("--v=0")
    options.add_extension(extension_path)

    rules = (
        "MAP mail.google.com:80 127.0.0.1:8080,"
        "MAP mail.google.com:443 127.0.0.1:8081,"
        "MAP *.google.com:80 127.0.0.1:8080,"
        "MAP *.google.com:443 127.0.0.1:8081,"
        "MAP *.gstatic.com:80 127.0.0.1:8080,"
        "MAP *.gstatic.com:443 127.0.0.1:8081,"
        "MAP *.googleusercontent.com:80 127.0.0.1:8080,"
        "MAP *.googleusercontent.com:443 127.0.0.1:8081,"
        "EXCLUDE localhost"
    )
    options.add_argument(f"--host-resolver-rules={rules}")

    return webdriver.Chrome(executable_path=CHROMEDRIVER_PATH, options=options)


def clear_log_files():
    for path in [os.path.join(USER_DATA, "taint_fetch.log"), "/ram/analysis/v8logs/taint_fetch.log"]:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def read_log_data():
    logs = ""
    for path in [os.path.join(USER_DATA, "taint_fetch.log"), "/ram/analysis/v8logs/taint_fetch.log"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as logfile:
                    logs += logfile.read()
            except Exception as exc:
                print(Fore.YELLOW + f"Warning: Unable to read {path}: {exc}" + Fore.RESET)
    return logs


def perform_interaction(driver):
    driver.get(TARGET_URL)

    compose_btn = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "div.T-I.T-I-KE[role='button']"))
    )
    compose_btn.click()

    to_field = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[aria-label='To recipients']"))
    )
    to_field.send_keys("jane.smith@gmail.com")

    subject_field = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.NAME, "subjectbox"))
    )
    subject_field.send_keys("Test Subject")

    body_field = WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "div[aria-label='Message Body']"))
    )
    body_field.click()
    body_field.send_keys("This is a test message")

    send_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//div[@role='button' and contains(@aria-label, 'Send')]")
        )
    )
    send_button.click()

    time.sleep(20)


def check_logs_for_expected_strings():
    logs = read_log_data()
    if all(value in logs for value in EXPECTED_STRINGS):
        print(Back.GREEN + "SUCCESS" + Back.RESET)
        return True

    print(Fore.RED + "FAILURE: Expected data not found in taint logs." + Fore.RESET)
    return False


def run():
    ensure_results_dir()
    display = init_environment()
    driver = None

    try:
        extension_path = resolve_extension()
        clear_log_files()
        start_wpr()
        driver = launch_arcanum(extension_path)
        perform_interaction(driver)
    except Exception as exc:
        print(Fore.RED + f"Test execution error: {exc}" + Fore.RESET)
    finally:
        if driver:
            driver.quit()
        display.stop()
        os.system("pkill wpr")

    check_logs_for_expected_strings()


if __name__ == "__main__":
    run()

