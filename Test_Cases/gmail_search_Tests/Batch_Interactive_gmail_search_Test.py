# -*- coding: utf-8 -*-
import os
import time
import glob
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from colorama import Fore, Back, Style
from pyvirtualdisplay import Display
from func_timeout import func_timeout, FunctionTimedOut

# --- Configuration ---
PAGE_NAME = "gmail_search"
TEST_PATH = "/root/"
TARGET_URL = "https://mail.google.com/mail/u/0/#inbox"
RECORDING_PATH = os.path.join(TEST_PATH, "recordings", "gmail_search.wprgo")
ANNOTATION_PATH = os.path.join(TEST_PATH, "annotations", "gmail_inbox.js")
RESULTS_DIR = os.path.join(TEST_PATH, "Results", PAGE_NAME)
# Mirroring the likely Amazon results file naming
RESULTS_CSV = os.path.join(RESULTS_DIR, "interactive_results.csv")
WPR_PATH = "/root/go/pkg/mod/github.com/catapult-project/catapult/web_page_replay_go@v0.0.0-20230901234838-f16ca3c78e46/"
USER_DATA = "/root/userdata/"
REALWORLD_EXT_DIR = "/root/extensions/realworld/"
CHROMEDRIVER_PATH = "/root/chromedriver/chromedriver"
ARCANUM_BIN = "/root/Arcanum/opt/chromium.org/chromium-unstable/chromium-browser-unstable"

# Expected string to be searched for and potentially leaked
EXPECTED_STRINGS = [
    "This is a test message",
    "John Doe",
    "arcanum.netsec@gmail.com",
    "Test Subject",
    "jane.smith@gmail.com"
]

# --- Core Functions (Mirrored from Amazon) ---

def init_environment():
    """Clean up previous processes and data and start virtual display."""
    os.system('pkill Xvfb')
    os.system('pkill chrome')
    os.system('pkill chromedriver')
    os.system('pkill wpr')
    os.system(f"rm -rf {USER_DATA}")
    
    # Start the virtual display
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    return display

def start_wpr():
    """Starts Web Page Replay in replay mode with the specified annotation script."""
    if not os.path.exists(WPR_PATH):
        print(Fore.RED + f"WPR path not found: {WPR_PATH}" + Fore.RESET)
        return False
    
    # Check if the correct annotation file exists
    if not os.path.exists(ANNOTATION_PATH):
        inject_scripts_arg = ""
    else:
        inject_scripts_arg = f"--inject_scripts=deterministic.js,{os.path.abspath(ANNOTATION_PATH)}"

    os.chdir(WPR_PATH)
    cmd = (
        "nohup /usr/local/go/bin/go run src/wpr.go replay "
        "--http_port=8080 --https_port=8081 "
        f"{inject_scripts_arg} "
        f"{os.path.abspath(RECORDING_PATH)} > /tmp/wprgo.log 2>&1 &"
    )
    os.system(cmd)
    time.sleep(3)
    return True

def launch_arcanum(extension_path):
    """Launches the custom Chromium browser with the given extension and WPR configuration."""
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

    # Host resolver rules for WPR replay
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
    """Removes previous taint log files."""
    for path in [os.path.join(USER_DATA, "taint_fetch.log"), "/ram/analysis/v8logs/taint_fetch.log"]:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    print("Cleared previous taint logs.")

def load_log_data():
    """Loads and returns all log data from the possible paths."""
    logs = ""
    potential_paths = [
        os.path.join(USER_DATA, "taint_fetch.log"), 
        "/ram/analysis/v8logs/taint_fetch.log"
    ]
    
    found_path = None
    for path in potential_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as logfile:
                    logs += logfile.read()
                    found_path = path
                    break
            except Exception:
                # Suppress detailed error mirroring Amazon style
                pass
    
    if not found_path:
        print(Fore.RED + "WARNING: Taint log file not found." + Fore.RESET)
    return logs


def perform_interaction(driver):
    """
    Performs the search interaction sequence:
    1. Navigates to the inbox.
    2. Finds the search bar.
    3. Manually taints the search bar (essential for this test).
    4. Enters the search query and submits.
    """
    print("Navigating to target URL and performing search interaction...")
    driver.get(TARGET_URL)

    # 1. Wait for search bar to be available
    search_bar = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[aria-label='Search mail'][name='q']"))
    )

    # 2. Manually apply taint via Selenium execute_script (mirroring interactive test)
    driver.execute_script("""
        var searchBar = document.querySelector("input[name='q']");
        if (searchBar) {
            searchBar.setAttribute("data-taint", "1");
            searchBar.style.border = "3px solid red"; // Visual confirmation
        }
    """)
    # Check the attribute (minimal logging)
    taint_value = search_bar.get_attribute("data-taint")
    
    if taint_value != "1":
        print(Fore.RED + "ERROR: Manual taint failed." + Fore.RESET)

    # 3. Enter search query and submit
    search_bar.click()
    time.sleep(0.5)
    search_bar.send_keys(EXPECTED_STRINGS[0])
    search_bar.send_keys(Keys.RETURN)
    
    # Wait for exfiltration time
    print("Waiting 20 seconds for exfiltration...")
    time.sleep(20)


def check_leakage():
    """Checks if the log data contains the expected leakage string."""
    logs = load_log_data()
    
    if not logs:
        return False
        
    leak_detected = any(value in logs for value in EXPECTED_STRINGS)
    
    if leak_detected:
        print(Back.GREEN + "Leak check: LEAK DETECTED." + Back.RESET)
    else:
        print(Fore.RED + "Leak check: No leakage found." + Fore.RESET)
        
    return leak_detected


def test_extension(ext_path):
    """Runs a single test iteration for a specific extension."""
    driver = None
    leak_detected = False
    
    try:
        # Cleanup user data and logs for a fresh run
        os.system(f"rm -rf {USER_DATA}")
        clear_log_files()
        
        # Launch browser with the current extension
        driver = launch_arcanum(ext_path)
        
        # Perform the actual user interaction
        perform_interaction(driver)
        
        # Check logs after interaction
        leak_detected = check_leakage()
        
    except Exception as e:
        print(Fore.RED + f"Test error: {e}" + Fore.RESET)
        
    finally:
        if driver:
            driver.quit()
        # Ensure browser processes are killed
        os.system('pkill chrome')
        os.system('pkill chromedriver')

    return leak_detected


def run_batch():
    """Main function to iterate over all extensions, apply timeout, and save results."""
    # Ensure results directory exists
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    extensions = sorted(glob.glob(os.path.join(REALWORLD_EXT_DIR, "*.crx")))

    if not extensions:
        print(Fore.RED + f"No extensions found in {REALWORLD_EXT_DIR}" + Fore.RESET)
        return

    results = []
    display = init_environment()

    try:
        if not start_wpr():
            display.stop()
            return

        for ext_path in extensions:
            ext_id = os.path.basename(ext_path).replace(".crx", "")
            print("\n" + "="*80)
            print(Fore.CYAN + Style.BRIGHT + f"Testing Extension: {ext_id}" + Style.RESET_ALL)
            print("="*80)
            
            leak_detected = False
            
            try:
                # Wrap the single test execution in a 120s hard timeout
                leak_detected = func_timeout(120, test_extension, args=(ext_path,))
            except FunctionTimedOut:
                print(Fore.RED + f"TIMEOUT: Extension {ext_id} took longer than 120s. Killing processes." + Fore.RESET)
                # Force kill stuck processes
                os.system('pkill chrome')
                os.system('pkill chromedriver')
            except Exception as e:
                print(Fore.RED + f"Unexpected Error running {ext_id}: {e}" + Fore.RESET)
            
            # Print result mirroring Amazon style
            if leak_detected:
                print(Back.GREEN + f"RESULT: LEAK DETECTED for {ext_id}" + Back.RESET)
            else:
                print(Fore.RED + f"RESULT: No leak for {ext_id}" + Fore.RESET)
                
            results.append([ext_id, leak_detected])
            
            # Short break between tests
            time.sleep(2) 
            
    except Exception as exc:
        print(Fore.RED + f"Critical Batch execution error: {exc}" + Fore.RESET)
    finally:
        # Final cleanup regardless of success/failure
        display.stop()
        os.system("pkill wpr") 

    # Save Report
    with open(RESULTS_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Extension ID", "Leak Detected"])
        writer.writerows(results)

    print("\n" + "="*80)
    print(Fore.GREEN + Style.BRIGHT + f"BATCH RUN COMPLETE. Results saved to {RESULTS_CSV}" + Style.RESET_ALL)
    print("="*80)


if __name__ == "__main__":
    run_batch()