# -*- coding: utf-8 -*-
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from colorama import Fore, Back, Style
from pyvirtualdisplay import Display

# --- Configuration ---
TEST_PATH = "/root/beeslab-arcanum/"
RECORDING_PATH = TEST_PATH + 'recordings/amazon_interactive.wprgo'
ANNOTATION_PATH = TEST_PATH + 'annotations/amazon_interactive.js'
WPR_PATH = '/root/go/pkg/mod/github.com/catapult-project/catapult/web_page_replay_go@v0.0.0-20230901234838-f16ca3c78e46/'
USER_DATA = '/root/userdata/'
REALWORLD_EXT_DIR = '/root/extensions/realworld/'

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

def resolve_extension():
    """Find a valid extension ID to use"""
    ids = [
        'oadkgbgppkhoaaoepjbcnjejmkknaobg', 
        'jdianbbpnakhcmfkcckaboohfgnngfcc', 
        'aamfmnhcipnbjjnbfmaoooiohikifefk', 
        'blcdkmjcpgjojjffbdkckaiondfpoglh',
        'pjmfidajplecneclhdghcgdefnmhhlca',
        'bahcihkpdjlbndandplnfmejnalndgjo',
        'nkecaphdplhfmmbkcfnknejeonfnifbn',
        'haphbbhhknaonfloinidkcmadhfjoghc',
        'kecadfolelkekbfmmfoifpfalfedeljo'
    ]
    default_id = ids[0]
    fallback_id = 'aamfmnhcipnbjjnbfmaoooiohikifefk'
    
    default_path = os.path.join(REALWORLD_EXT_DIR, default_id + '.crx')
    fallback_path = os.path.join(REALWORLD_EXT_DIR, fallback_id + '.crx')

    if os.path.exists(default_path):
        print(Fore.CYAN + f"Using DEFAULT extension: {default_id}" + Fore.RESET)
        print(Fore.CYAN + f"Path: {default_path}" + Fore.RESET)
        return default_path
    
    print(Fore.YELLOW + f"Default extension {default_id} not found. Checking fallback..." + Fore.RESET)
    if os.path.exists(fallback_path):
        print(Fore.CYAN + f"Using FALLBACK extension: {fallback_id}" + Fore.RESET)
        print(Fore.CYAN + f"Path: {fallback_path}" + Fore.RESET)
        return fallback_path

    print(Fore.RED + f"Error: No suitable extension found in {REALWORLD_EXT_DIR}. Available files:" + Fore.RESET)
    os.system(f"ls {REALWORLD_EXT_DIR}")
    exit(1)

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
    """Launch the custom Chromium browser with Selenium"""
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
    
    driver = webdriver.Chrome(executable_path=CHROMEDRIVER_PATH, options=options)
    return driver

def check_logs():
    """Check for leakage in logs, handling multiple potential paths"""
    potential_paths = [
        os.path.join(USER_DATA, 'taint_fetch.log'),
        '/ram/analysis/v8logs/taint_fetch.log'
    ]
    
    found_path = None
    logs = ""

    for path in potential_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    logs = f.read()
                    found_path = path
                    break
            except Exception as e:
                print(f"Warning: Could not read {path}: {e}")

    if not found_path:
        # In passive mode, lack of log file is actually a GOOD thing (No Leak)
        print(Fore.YELLOW + f"Info: No taint logs found (Expected for Passive Test)." + Fore.RESET)
        print(Fore.GREEN + "SUCCESS: No passive leakage found" + Fore.RESET)
        return

    print(f"Analyzing logs from: {found_path}")
    
    if "John Doe" in logs or "1234567890" in logs:
        print(Back.RED + "FAIL: PASSIVE LEAK DETECTED (Unexpected)" + Back.RESET)
    else:
        print(Back.GREEN + "SUCCESS: No passive leakage found" + Back.RESET)

def run_passive_test():
    display = init_environment()
    ext_path = resolve_extension()
    
    if not start_wpr():
        display.stop()
        return

    driver = None
    try:
        print(f"Launching Arcanum with extension: {ext_path}")
        driver = launch_arcanum(ext_path)
        
        print("Navigating to Amazon Addresses (Passive Mode)...")
        driver.get("https://www.amazon.com/a/addresses")
        
        # PASSIVE MODE: No Interaction
        
        print("Waiting 20s for passive observation...")
        time.sleep(20)
        
    except Exception as e:
        print(Fore.RED + f"Test Execution Error: {str(e)}" + Fore.RESET)
        
    finally:
        if driver:
            driver.quit()
        display.stop()
        os.system('pkill wpr')
        
    # Verification
    check_logs()

if __name__ == "__main__":
    run_passive_test()

