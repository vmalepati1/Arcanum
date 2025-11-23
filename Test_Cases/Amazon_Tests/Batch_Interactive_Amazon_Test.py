# -*- coding: utf-8 -*-
import os
import time
import glob
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from colorama import Fore, Back, Style
from pyvirtualdisplay import Display
from func_timeout import func_timeout, FunctionTimedOut

# --- Configuration ---
TEST_PATH = "/root/beeslab-arcanum/"
RECORDING_PATH = TEST_PATH + 'recordings/amazon_interactive.wprgo'
ANNOTATION_PATH = TEST_PATH + 'annotations/amazon_interactive.js'
WPR_PATH = '/root/go/pkg/mod/github.com/catapult-project/catapult/web_page_replay_go@v0.0.0-20230901234838-f16ca3c78e46/'
USER_DATA = '/root/userdata/'
REALWORLD_EXT_DIR = '/root/extensions/realworld/'
RESULTS_CSV = TEST_PATH + 'interactive_results.csv'

# Environment specific paths
CHROMEDRIVER_PATH = "/root/chromedriver/chromedriver"
ARCANUM_BIN = "/root/Arcanum/opt/chromium.org/chromium-unstable/chromium-browser-unstable"

def init_environment():
    """Clean up previous processes and data"""
    os.system('pkill Xvfb')
    os.system('pkill chrome')
    os.system('pkill chromedriver')
    os.system('pkill wpr')
    os.system(f'rm -rf {USER_DATA}')
    
    # Start virtual display
    display = Display(visible=0, size=(1920, 1080))
    display.start()
    return display

def start_wpr():
    """Start Web Page Replay in background"""
    if not os.path.exists(WPR_PATH):
        print(Fore.RED + f"Error: WPR path not found: {WPR_PATH}" + Fore.RESET)
        return False

    os.chdir(WPR_PATH)
    # Note: Using deterministic.js + our new annotation file
    cmd = (f'nohup /usr/local/go/bin/go run src/wpr.go replay '
           f'--http_port=8080 --https_port=8081 '
           f'--inject_scripts=deterministic.js,{ANNOTATION_PATH} '
           f'{RECORDING_PATH} > /tmp/wprgo.log 2>&1 &')
    
    print(f"Starting WPR: {cmd}")
    os.system(cmd)
    time.sleep(3) # Allow startup time
    return True

def launch_arcanum(extension_path):
    """Launch the custom Chromium browser with Selenium 3 syntax"""
    if not os.path.exists(ARCANUM_BIN):
        print(Fore.RED + f"Error: Arcanum binary not found at {ARCANUM_BIN}" + Fore.RESET)
        exit(1)

    options = webdriver.ChromeOptions()
    options.binary_location = ARCANUM_BIN
    
    options.add_argument(f'--user-data-dir={USER_DATA}')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors=yes')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("--enable-logging")
    options.add_argument("--v=0")
    
    # Load the extension
    options.add_extension(extension_path)
    
    # Network Rules for WPR
    rules = ("MAP *.amazon.com:80 127.0.0.1:8080,"
             "MAP *.amazon.com:443 127.0.0.1:8081,"
             "MAP *.ssl-images-amazon.com:80 127.0.0.1:8080,"
             "MAP *.ssl-images-amazon.com:443 127.0.0.1:8081,"
             "EXCLUDE localhost")
    options.add_argument(f'--host-resolver-rules={rules}')
    
    # Selenium 3 specific constructor
    driver = webdriver.Chrome(executable_path=CHROMEDRIVER_PATH, options=options)
    return driver

def check_leakage():
    """Check for leakage in logs, handling multiple potential paths"""
    potential_paths = [
        os.path.join(USER_DATA, 'taint_fetch.log'),
        '/ram/analysis/v8logs/taint_fetch.log'
    ]
    
    logs = ""
    for path in potential_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    logs += f.read()
            except Exception as e:
                print(f"Warning: Could not read {path}: {e}")

    # Check for the specific strings requested
    if "John Doe" in logs or "1234567890" in logs:
        return True
    return False

def test_extension(ext_path):
    """Test logic for a single extension, wrapped for timeout"""
    driver = None
    try:
        # Clean user data per extension run
        os.system(f'rm -rf {USER_DATA}')
        
        driver = launch_arcanum(ext_path)
        
        # Amazon Interaction Flow
        print("Navigating...")
        driver.get("https://www.amazon.com/a/addresses")
        
        print("Adding Address...")
        add_btn = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#ya-myab-address-add-link"))
        )
        add_btn.click()
        
        WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "#address-ui-widgets-enterAddressFullName"))
        )
        
        # Input Data per specs
        driver.find_element(By.CSS_SELECTOR, "#address-ui-widgets-enterAddressFullName").send_keys("Test User")
        driver.find_element(By.CSS_SELECTOR, "#address-ui-widgets-enterAddressPhoneNumber").send_keys("5550199")
        driver.find_element(By.CSS_SELECTOR, "#address-ui-widgets-enterAddressLine1").send_keys("123 Test St")
        driver.find_element(By.CSS_SELECTOR, "#address-ui-widgets-enterAddressCity").send_keys("Atlanta")
        driver.find_element(By.CSS_SELECTOR, "#address-ui-widgets-enterAddressPostalCode").send_keys("30332")
        
        print("Submitting...")
        driver.find_element(By.CSS_SELECTOR, "#address-ui-widgets-form-submit-button").click()
        
        print("Waiting 20s for exfiltration...")
        time.sleep(20)
        
    except Exception as e:
        print(Fore.RED + f"Selenium/Driver Error: {e}" + Fore.RESET)
    finally:
        if driver:
            driver.quit()
            
    return check_leakage()

# Known Target Mapping (from Realworld_Test.py and paper)
TARGET_MAP = {
    'amazon_address': ['oadkgbgppkhoaaoepjbcnjejmkknaobg', 'pjmfidajplecneclhdghcgdefnmhhlca'],
    'fb_post': ['jdianbbpnakhcmfkcckaboohfgnngfcc', 'bahcihkpdjlbndandplnfmejnalndgjo'],
    'ins_profile': ['aamfmnhcipnbjjnbfmaoooiohikifefk', 'nkecaphdplhfmmbkcfnknejeonfnifbn', 'mdfgkcdjgpgoeclhefnjgmollcckpedk'],
    'linkedin_profile': ['haphbbhhknaonfloinidkcmadhfjoghc', 'kecadfolelkekbfmmfoifpfalfedeljo'],
    'paypal_card': ['blcdkmjcpgjojjffbdkckaiondfpoglh'],
    'gmail_inbox': [],
    'outlook_inbox': []
}

def get_target_site(ext_id):
    for site, ids in TARGET_MAP.items():
        if ext_id in ids:
            return site
    return "unknown"

def run_batch_study():
    # Find all .crx files
    extensions = glob.glob(os.path.join(REALWORLD_EXT_DIR, "*.crx"))
    if not extensions:
        print(Fore.RED + f"No extensions found in {REALWORLD_EXT_DIR}" + Fore.RESET)
        return

    print(f"Found {len(extensions)} extensions to test.")
    
    results = []
    display = init_environment()
    
    if not start_wpr():
        display.stop()
        return

    for ext_path in extensions:
        ext_id = os.path.basename(ext_path).replace('.crx', '')
        target_site = get_target_site(ext_id)
        
        print(f"\nTesting Extension: {ext_id}")
        print(Fore.CYAN + f"Target Site: {target_site}" + Fore.RESET)
        
        if target_site != 'amazon_address' and target_site != 'unknown':
             print(Fore.YELLOW + f"WARNING: Site Mismatch! Extension targets '{target_site}', but test is 'amazon_address'." + Fore.RESET)

        leak_detected = False
        
        try:
            # Wrap the single test execution in a 120s (2 min) hard timeout
            leak_detected = func_timeout(120, test_extension, args=(ext_path,))
        except FunctionTimedOut:
            print(Fore.RED + f"TIMEOUT: Extension {ext_id} took longer than 120s. Killing processes." + Fore.RESET)
            # Force kill stuck processes to clear the way for the next test
            os.system('pkill chrome')
            os.system('pkill chromedriver')
        except Exception as e:
            print(Fore.RED + f"Unexpected Error running {ext_id}: {e}" + Fore.RESET)
        
        if leak_detected:
            print(Back.GREEN + f"RESULT: LEAK DETECTED for {ext_id}" + Back.RESET)
        else:
            print(Fore.RED + f"RESULT: No leak for {ext_id}" + Fore.RESET)
            
        results.append([ext_id, leak_detected])

    # Cleanup
    display.stop()
    os.system('pkill wpr')
    
    # Save Report
    with open(RESULTS_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Extension ID', 'Leak Detected'])
        writer.writerows(results)
        
    print(f"\nBatch Study Complete. Results saved to {RESULTS_CSV}")

if __name__ == "__main__":
    run_batch_study()
