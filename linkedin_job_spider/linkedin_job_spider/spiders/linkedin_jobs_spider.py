import scrapy
import random
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from scrapy.selector import Selector
from fake_useragent import UserAgent
import scrapy
from urllib.parse import urljoin
from dotenv import load_dotenv
load_dotenv()

class LinkedInJobsSpider(scrapy.Spider):
    name = "linkedin_jobs"
    custom_settings = {
        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': random.uniform(3, 8),
       # Sync headers for Scrapy requests
        'DEFAULT_REQUEST_HEADERS': {
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.linkedin.com/',
        }
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ua = UserAgent()
        self.jobs_collected = 0
        self.max_jobs = 5

        # Desktop-only
        def get_desktop_headers():
            while True:
                ua = self.ua.random
                if not any(x in ua.lower() for x in ['mobile', 'iphone', 'android']):
                    return {
                        'User-Agent': ua,
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Referer': 'https://www.linkedin.com/'
                    }
        headers = get_desktop_headers()

        chrome_options = Options()
        chrome_options.add_argument(f"user-agent={headers['User-Agent']}")  
        chrome_options.add_argument(f"--lang={headers['Accept-Language']}") 
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        self.driver = webdriver.Chrome(
            service=Service(),
            options=chrome_options
        )
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Critical LinkedIn header 
        self.driver.execute_script("""
            Object.defineProperty(navigator, 'language', {value: 'en-US'});
            Object.defineProperty(navigator, 'languages', {value: ['en-US', 'en']});
        """)
    
    def human_delay(self):
        time.sleep(random.uniform(1.5, 4.5))  

    # mouse movement
    def human_mouse_movement(self):
        actions = ActionChains(self.driver)
        window_size = self.driver.get_window_size()
        width, height = window_size['width'], window_size['height']

        start_x = random.randint(0, width - 1)
        start_y = random.randint(0, height - 1)
        actions.move_by_offset(start_x, start_y).perform()
        time.sleep(random.uniform(0.2, 1))
        
        for _ in range(random.randint(3, 6)):
            offset_x = random.randint(-30, 30)
            offset_y = random.randint(-30, 30)
            next_x = max(0, min(start_x + offset_x, width - 1))
            next_y = max(0, min(start_y + offset_y, height - 1))
            actions.move_by_offset(next_x - start_x, next_y - start_y).perform()
            start_x, start_y = next_x, next_y
            time.sleep(random.uniform(0.2, 1))


    def human_type(self, element, text):
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.1, 0.3))  

    def start_requests(self):
        # credentials
        username = os.getenv('LINKEDIN_USER', 'tadeke1187@inkight.com')
        password = os.getenv('LINKEDIN_PASS', 'ZXCVbnm@231')

        self.driver.get("https://www.linkedin.com/login")
        
        try:
            # CAPTCHA detection before login
            if "security check" in self.driver.page_source.lower():
                self.logger.error("❌ CAPTCHA detected before login!")
                self.driver.save_screenshot("captcha_before_login.png")
                time.sleep(300)  # 5 minute pause

            email_field = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            self.human_type(email_field, username)
            
            password_field = self.driver.find_element(By.ID, "password")
            self.human_type(password_field, password)
            
            self.human_mouse_movement()  
            self.human_delay()
            
            self.driver.find_element(By.XPATH, "//button[@type='submit']").click()
            self.logger.info("✅ Waiting for login...")

            # CAPTCHA detection after login
            WebDriverWait(self.driver, 30).until(
                lambda driver: "security check" not in driver.page_source.lower(),
                "CAPTCHA detected during login"
            )

            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.global-nav__me"))
            )
            self.logger.info("✅ Login successful!")

            jobs_url = "https://www.linkedin.com/jobs/search/?keywords=Artificial%20Intelligence&location=Islamabad,Pakistan"
            self.driver.get(jobs_url)
            self.logger.info("✅ Navigating to jobs page...")

            # Updated job list handling
            try:
                WebDriverWait(self.driver, 25).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "ul.jobs-search__results-list"))
                )
                
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                while self.jobs_collected < self.max_jobs:
                    scroll_px = random.randint(300, 700)
                    self.driver.execute_script(f"window.scrollBy(0, {scroll_px})")
                    self.human_delay()
                    self.human_mouse_movement()  
                    
                    current_jobs = self.driver.find_elements(
                        By.CSS_SELECTOR, "li.jobs-search-results__list-item"
                    )
                    self.jobs_collected = len(current_jobs)
                    
                    if len(current_jobs) >= self.max_jobs:
                        break
                    
                    time.sleep(random.uniform(2.5, 5.5))

            except Exception as e:
                self.logger.error(f"❌ Error loading jobs: {str(e)}")
                self.driver.save_screenshot("error_screenshot.png")

            sel = Selector(text=self.driver.page_source)
            yield from self.parse_jobs(sel)

        except Exception as e:
            self.logger.error(f"❌ Critical error: {str(e)}")
            self.driver.save_screenshot("critical_error.png")

    #Job Parsing
    def parse_jobs(self, sel):
        """
        Parse each job card by locating live elements with Selenium,
        finding title, company, location and posted date elements directly.
        """
        cards = self.driver.find_elements(
            By.CSS_SELECTOR,
            "li.job-card-container, li.jobs-search-two-pane__job-card-container, li.scaffold-layout__list-item"
        )

        if not cards:
            self.logger.warning("⚠️ No job cards found via Selenium! Check selector patterns.")

        for card in cards[:self.max_jobs]:
            try:
                title_el = card.find_element(By.XPATH, ".//a[contains(@href,'/jobs/view')][1]")
                title = title_el.text.strip()
            except Exception:
                title = None

            try:
                company_el = card.find_element(
                    By.XPATH,
                    ".//h4[contains(@class,'entity-lockup__subtitle')]//span | .//div[@class='artdeco-entity-lockup__subtitle']//span"
                )
                company = company_el.text.strip()
            except Exception:
                company = None

            try:
                loc_el = card.find_element(
                    By.XPATH,
                    ".//ul[contains(@class,'metadata-wrapper')]/li[1] | .//div[contains(@class,'caption')]/span"
                )
                location = loc_el.text.strip()
            except Exception:
                location = None

            try:
                date_el = card.find_element(By.TAG_NAME, 'time')
                posted_date = date_el.get_attribute('datetime') or date_el.text.strip()
            except Exception:
                posted_date = None

            try:
                href = title_el.get_attribute('href')
                job_url = urljoin('https://www.linkedin.com', href) if href and href.startswith('/') else href
            except Exception:
                job_url = None

            # Debug prints
            print(f"Job Title: {title}")
            print(f"Company: {company}")
            print(f"Location: {location}")
            print(f"Posted Date: {posted_date}")
            print(f"Job URL: {job_url}")
            print("-"*40)

            yield {
                'job_title': title,
                'company_name': company,
                'location': location,
                'posted_date': posted_date,
                'job_url': job_url
            }

        self.logger.info(f"✅ Parsed {len(cards[:self.max_jobs])} job cards via Selenium live DOM.")

    def closed(self, reason):
        self.driver.quit()
        self.logger.info("✅ Browser closed successfully")