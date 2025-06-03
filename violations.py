import time
import threading
import traceback
from flask import Blueprint, render_template
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import telegram

violations_bp = Blueprint('violations', __name__, template_folder='templates')

# Telegram setup
TELEGRAM_API_KEY = '7215285493:AAFTn6A1peNE3QccbLUndPZj4Erw0t-aqus'
CHAT_ID = '5935343360'
bot = telegram.Bot(token=TELEGRAM_API_KEY)

# Credentials and URLs
LUCI_USERNAME = 'test7261236784702590@gmail.com'
LUCI_PASSWORD = 'Test3547736@'
LOGIN_URL = 'https://app.lucideld.com/login'
VIOLATIONS_URL = 'https://app.lucideld.com/companies-violations'

# Shared data & lock
violations_data = []
violations_lock = threading.Lock()

def send_telegram_alert(violation):
    message = (
        f"⚠️ Violation Alert ⚠️\n"
        f"Driver: {violation['driver_name']}\n"
        f"Company: {violation['company_name']}\n"
        f"Type: {violation['violation_type']}\n"
        f"Time: {violation['violation_time']}\n"
        f"Status: Unresolved > 5 minutes"
    )
    try:
        bot.send_message(chat_id=CHAT_ID, text=message)
        print(f"[ALERT] Sent Telegram alert for violation ID {violation['id']}")
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")
        traceback.print_exc()

def fetch_violations_with_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    try:
        driver = webdriver.Chrome(options=chrome_options)
    except Exception as e:
        print(f"[ERROR] Failed to start ChromeDriver: {e}")
        traceback.print_exc()
        return []

    try:
        driver.get(LOGIN_URL)
        wait = WebDriverWait(driver, 15)

        wait.until(EC.presence_of_element_located((By.NAME, 'email')))
        email_input = driver.find_element(By.NAME, 'email')
        password_input = driver.find_element(By.NAME, 'password')

        email_input.clear()
        email_input.send_keys(LUCI_USERNAME)
        password_input.clear()
        password_input.send_keys(LUCI_PASSWORD + Keys.RETURN)

        wait.until(EC.url_contains('/dashboard'))

        driver.get(VIOLATIONS_URL)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'table#violations-table tbody tr')))

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        rows = soup.select('table#violations-table tbody tr')

        violations = []
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 5:
                continue
            try:
                violation_id = int(cells[0].text.strip())
            except ValueError:
                continue
            violation = {
                'id': violation_id,
                'driver_name': cells[1].text.strip(),
                'company_name': cells[2].text.strip(),
                'violation_type': cells[3].text.strip(),
                'violation_time': cells[4].text.strip(),
                'resolved': False,
                'alert_sent': False,
                'first_detected': time.time()
            }
            violations.append(violation)

        print(f"[INFO] Fetched {len(violations)} violations")
        return violations
    except Exception as e:
        print(f"[ERROR] Error during Selenium operation: {e}")
        traceback.print_exc()
        return []
    finally:
        driver.quit()

def violation_monitor_thread():
    print("[INFO] Violation monitor thread started")
    while True:
        try:
            new_violations = fetch_violations_with_selenium()
            now = time.time()
            with violations_lock:
                new_dict = {v['id']: v for v in new_violations}

                existing_ids = set(v['id'] for v in violations_data)
                new_ids = set(new_dict.keys())

                # Mark resolved if missing
                for v in violations_data:
                    if v['id'] not in new_ids and not v['resolved']:
                        print(f"[INFO] Violation ID {v['id']} resolved or cleared")
                        v['resolved'] = True

                # Add/update violations
                for vid, new_v in new_dict.items():
                    existing = next((v for v in violations_data if v['id'] == vid), None)
                    if existing is None:
                        new_v['resolved'] = False
                        new_v['alert_sent'] = False
                        new_v['first_detected'] = now
                        violations_data.append(new_v)
                        print(f"[INFO] New violation ID {vid}")
                    else:
                        existing['driver_name'] = new_v['driver_name']
                        existing['company_name'] = new_v['company_name']
                        existing['violation_type'] = new_v['violation_type']
                        existing['violation_time'] = new_v['violation_time']
                        if existing['resolved']:
                            existing['resolved'] = False
                            existing['first_detected'] = now
                            existing['alert_sent'] = False

                # Send alerts for unresolved violations older than 5 mins
                for v in violations_data:
                    elapsed = now - v['first_detected']
                    print(f"[DEBUG] Violation ID {v['id']} elapsed {elapsed:.1f}s, alert_sent={v['alert_sent']}, resolved={v['resolved']}")
                    if not v['resolved'] and not v['alert_sent'] and elapsed > 300:
                        send_telegram_alert(v)
                        v['alert_sent'] = True

        except Exception as e:
            print(f"[ERROR] Error in violation monitor thread: {e}")
            traceback.print_exc()

        time.sleep(60)

def start_violation_monitor():
    print("[DEBUG] Starting violation monitor thread")
    t = threading.Thread(target=violation_monitor_thread, daemon=True)
    t.start()

def start_monitor_when_registered(state):
    start_violation_monitor()
