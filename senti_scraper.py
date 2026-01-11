import os
import time
import shutil
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class SentiScraper:
    def __init__(self, download_dir=None):
        self.download_dir = download_dir if download_dir else os.getcwd()
        self.driver = None
        self.wait = None

    def setup_driver(self):
        options = webdriver.ChromeOptions()
        prefs = {"download.default_directory": self.download_dir}
        options.add_experimental_option("prefs", prefs)
        
        # Cloud/Headless compatibility settings
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        
        # Try to find system specific chrome if needed
        # On Streamlit Cloud (Linux), we often need to point to chromium
        service = None
        if os.path.exists("/usr/bin/chromium"):
             options.binary_location = "/usr/bin/chromium"
             # If we are using system chromium, we should try to use system chromedriver too
             # This avoids version mismatch errors
             if os.path.exists("/usr/bin/chromedriver"):
                 service = Service("/usr/bin/chromedriver")
             elif os.path.exists("/usr/lib/chromium-browser/chromedriver"):
                 service = Service("/usr/lib/chromium-browser/chromedriver")

        elif os.path.exists("/usr/bin/google-chrome"):
             options.binary_location = "/usr/bin/google-chrome"
        
        # Fallback to WDM if no system driver found
        if not service:
            try:
                service = Service(ChromeDriverManager().install())
            except:
                # Last ditch effort: try finding generic chromedriver
                service = Service()
            
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 20) # Increased timeout

    def login(self, email, password):
        try:
            print("Navigating to login...")
            self.driver.get("https://sentione.com/app")
            
            try:
                cookie_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(@class, 'cookies__content')]//*[contains(text(), 'OK')]")))
                cookie_btn.click()
                print("Cookies accepted.")
                time.sleep(1)
            except:
                print("No cookie banner found.")

            print("Waiting for login fields...")
            # Wait for any input to be sure page loaded
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input")))
            
            try:
                email_field_spec = self.driver.find_element(By.CSS_SELECTOR, "input.input-with-label__input[type='email']")
                email_field_spec.clear()
                email_field_spec.send_keys(email)
            except:
                # Fallback
                email_field = self.driver.find_element(By.CSS_SELECTOR, "input.input-with-label__input")
                email_field.clear()
                email_field.send_keys(email)
            
            password_field = self.driver.find_element(By.CSS_SELECTOR, "input.input-with-label__input[type='password']")
            password_field.clear()
            password_field.send_keys(password)
            
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button.entry-form__submit")
            self.driver.execute_script("arguments[0].click();", submit_btn) # JS Click is stronger
            
            print("Login submitted. Waiting for dashboard...")
            self.wait.until(EC.url_contains("/app#/topics"))
            print("Logged in successfully.")
            return True
        except Exception as e:
            print(f"Login failed: {e}")
            if self.driver:
                print(f"Current URL: {self.driver.current_url}")
                print(f"Page Source Preview: {self.driver.page_source[:500]}")
            return False

    def scrape_topic(self, topic_id, start_date, end_date):
        try:
            target_url = f"https://sentione.com/app#/results?topicId={topic_id}"
            print(f"Navigating to topic: {target_url}")
            self.driver.get(target_url)
            time.sleep(5) 

            print("Locating datepicker...")
            datepicker = self.wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "header-datepicker__wrapper")))
            datepicker.click()
            
            time.sleep(1)
            
            try:
                custom_range_btn = self.driver.find_element(By.XPATH, "//li[contains(text(), 'Custom') or contains(text(), 'Customize')]")
                custom_range_btn.click()
            except:
                pass 

            time.sleep(1)

            start_dt = datetime.strptime(start_date, "%d.%m.%Y")
            end_dt = datetime.strptime(end_date, "%d.%m.%Y")
            end_dt_plus_1 = end_dt + timedelta(days=1)
            
            final_start_date = start_date
            final_end_date = end_dt_plus_1.strftime("%d.%m.%Y")
            
            print(f"Setting dates: {final_start_date} - {final_end_date}")

            start_input = self.wait.until(EC.visibility_of_element_located((By.NAME, "daterangepicker_start")))
            end_input = self.driver.find_element(By.NAME, "daterangepicker_end")
            
            start_input.click() 
            start_input.send_keys(webdriver.common.keys.Keys.CONTROL + "a")
            start_input.send_keys(webdriver.common.keys.Keys.DELETE)
            start_input.send_keys(final_start_date)
            
            end_input.click()
            end_input.send_keys(webdriver.common.keys.Keys.CONTROL + "a")
            end_input.send_keys(webdriver.common.keys.Keys.DELETE)
            end_input.send_keys(final_end_date)
            
            apply_btn = self.driver.find_element(By.CSS_SELECTOR, ".applyBtn")
            apply_btn.click()
            print("Dates applied.")
            
            time.sleep(3) 

            print("Clicking Export...")
            try:
                export_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Export')]")))
            except:
                export_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.secondary.small.with-icon.without-line-separator")))
            export_btn.click()
            
            time.sleep(1)
            
            print("Selecting CSV...")
            try:
                csv_option = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(@class, 'actions-list__item') and contains(., 'CSV file')]")))
                csv_option.click()
            except:
                csv_option = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(@class, 'actions-list__item') and contains(., 'CSV')]")))
                csv_option.click()
            
            print("Download initiated.")
            
            time.sleep(10)
            return True

        except Exception as e:
            print(f"Error scraping topic {topic_id}: {e}")
            return False

    def close(self):
        if self.driver:
            self.driver.quit()

    def process_latest_file(self, topic_title):
        files = [os.path.join(self.download_dir, f) for f in os.listdir(self.download_dir) if f.endswith(".csv")]
        if not files:
            return None
        
        latest_file = max(files, key=os.path.getctime)
        
        client_name = topic_title.split('_')[0]
        client_dir = os.path.join(self.download_dir, client_name)
        
        if not os.path.exists(client_dir):
            os.makedirs(client_dir)
            
        new_filename = f"{topic_title}.csv"
        new_path = os.path.join(client_dir, new_filename)
        
        if os.path.exists(new_path):
             timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
             new_filename = f"{topic_title}_{timestamp}.csv"
             new_path = os.path.join(client_dir, new_filename)

        shutil.move(latest_file, new_path)
        return new_path
