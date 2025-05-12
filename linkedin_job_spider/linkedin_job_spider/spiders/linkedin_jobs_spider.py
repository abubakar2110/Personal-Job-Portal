import scrapy
import random
import time
import os
import json
import datetime
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from scrapy.selector import Selector
from fake_useragent import UserAgent
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
        self.max_jobs = 5  # You can adjust this value as needed
        self.collected_data = []  # Store job data here
        self.max_retries = 3  # Maximum retries for scraping each job
        self.required_fields = ['job_title', 'company_name', 'location', 'posted_date', 'job_url', 'job_description']

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

    def expand_job_description(self):
        """Attempt to expand the 'Show more' button in job descriptions"""
        try:
            # Try multiple selectors for the 'Show more' button
            show_more_selectors = [
                "button.show-more-less-html__button--more",
                "button.artdeco-button--tertiary",
                "button.show-more-less-button",
                "button[aria-label='Show more']",
                "button[aria-label='See more']",
                "button.inline-show-more-text__button",
                ".show-more-less-html__button"
            ]
            
            for selector in show_more_selectors:
                try:
                    # First try finding buttons that contain "show more" text
                    show_more_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for show_more in show_more_buttons:
                        if show_more.is_displayed() and "more" in show_more.text.lower():
                            self.human_delay()
                            self.human_mouse_movement()
                            show_more.click()
                            time.sleep(random.uniform(1, 2))  # Wait for expansion
                            self.logger.info("✅ Expanded job description 'Show more' button")
                            # Check for additional "Show more" buttons that might appear after expanding
                            self.human_delay()
                except Exception as e:
                    self.logger.debug(f"Show more button selector {selector} failed: {str(e)}")
            
            # Try a more aggressive approach - click any button that might be a "show more" button
            try:
                all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                for button in all_buttons:
                    if button.is_displayed() and "more" in button.text.lower():
                        self.human_delay()
                        self.human_mouse_movement()
                        button.click()
                        time.sleep(random.uniform(1, 2))
                        self.logger.info("✅ Clicked on potential 'Show more' button")
            except Exception as e:
                self.logger.debug(f"Fallback show more approach failed: {str(e)}")
                
            return True  # Return True regardless to continue with description extraction
        except Exception as e:
            self.logger.warning(f"⚠️ Error in expand_job_description: {str(e)}")
            return False

    def convert_relative_date(self, relative_date_text):
        """
        Convert LinkedIn's relative date format (e.g., "3 days ago", "1 week ago")
        to an actual date (YYYY-MM-DD format)
        """
        if not relative_date_text or relative_date_text == "Date not available":
            return relative_date_text
            
        # Clean up the input text
        relative_date_text = relative_date_text.lower().strip()
        
        # Handle special cases
        if "just now" in relative_date_text or "now" in relative_date_text:
            return datetime.datetime.now().strftime("%Y-%m-%d")
            
        if "active" in relative_date_text and "ago" not in relative_date_text:
            return datetime.datetime.now().strftime("%Y-%m-%d")
            
        if "posted" in relative_date_text:
            relative_date_text = relative_date_text.replace("posted", "").strip()
            
        # Extract time value and unit using regex
        pattern = r'(\d+)\s+(hour|hours|hr|hrs|day|days|week|weeks|month|months|year|years)'
        match = re.search(pattern, relative_date_text)
        
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            # Calculate the date
            current_date = datetime.datetime.now()
            
            if unit in ['hour', 'hours', 'hr', 'hrs']:
                relative_date = current_date - datetime.timedelta(hours=value)
            elif unit in ['day', 'days']:
                relative_date = current_date - datetime.timedelta(days=value)
            elif unit in ['week', 'weeks']:
                relative_date = current_date - datetime.timedelta(weeks=value)
            elif unit in ['month', 'months']:
                # Approximating a month as 30 days
                relative_date = current_date - datetime.timedelta(days=value * 30)
            elif unit in ['year', 'years']:
                # Approximating a year as 365 days
                relative_date = current_date - datetime.timedelta(days=value * 365)
            else:
                # If can't determine, return the original text but add the current date
                return f"{relative_date_text} (as of {current_date.strftime('%Y-%m-%d')})"
                
            # Format the date as YYYY-MM-DD
            formatted_date = relative_date.strftime("%Y-%m-%d")
            
            # Return both the original text and the calculated date
            return f"{relative_date_text} ({formatted_date})"
        else:
            # If couldn't parse the pattern, return original with current date
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            return f"{relative_date_text} (as of {current_date})"

    def extract_posted_date(self, job_detail_container=None):
        """Extract posted date from job details page"""
        try:
            date_selectors = [
                ".jobs-unified-top-card__posted-date",
                ".jobs-details__job-summary-text",
                ".job-posting-date",
                ".jobs-unified-top-card__subtitle-secondary-grouping span",
                ".jobs-unified-top-card__content-meta-container span",
                ".job-details-jobs-unified-top-card__primary-description-container span"
            ]
            
            # If a container is provided, search within it
            element_to_search = job_detail_container if job_detail_container else self.driver
            
            for selector in date_selectors:
                try:
                    date_elements = element_to_search.find_elements(By.CSS_SELECTOR, selector)
                    for element in date_elements:
                        text = element.text.strip()
                        if any(time_word in text.lower() for time_word in ["ago", "hour", "day", "week", "month", "active"]):
                            self.logger.info(f"Found date using selector: {selector}")
                            return text
                except Exception:
                    continue
            
            # If no specific selectors work, try looking at all spans in the top card
            try:
                top_card = element_to_search.find_element(By.CSS_SELECTOR, ".jobs-unified-top-card, .job-details-jobs-unified-top-card")
                spans = top_card.find_elements(By.TAG_NAME, "span")
                for span in spans:
                    text = span.text.strip()
                    if text and any(time_word in text.lower() for time_word in ["ago", "hour", "day", "week", "month", "active", "posted"]):
                        return text
            except Exception as e:
                self.logger.debug(f"Failed to find date in top card: {str(e)}")
            
            # As a last resort, search all spans on the page
            try:
                all_spans = element_to_search.find_elements(By.TAG_NAME, "span")
                for span in all_spans:
                    text = span.text.strip()
                    if text and any(time_word in text.lower() for time_word in ["ago", "hour", "day", "week", "month", "active", "posted"]):
                        return text
            except Exception as e:
                self.logger.debug(f"Failed to find date in all spans: {str(e)}")
                
            return None
        except Exception as e:
            self.logger.warning(f"⚠️ Error in extract_posted_date: {str(e)}")
            return None

    def normalize_posted_date(self, posted_date):
        """Normalize the posted date format and convert to actual date"""
        if not posted_date:
            return "Date not available"
            
        posted_date = posted_date.strip()
        
        # If it's a datetime attribute, keep it as is (already in standardized format)
        if posted_date and any(x in posted_date.lower() for x in ["hour", "day", "week", "month", "minute", "ago", "posted", "active"]):
            # Remove extra whitespace and ensure consistent formatting
            posted_date = ' '.join(posted_date.split())
            
            # Replace common variations
            posted_date = posted_date.replace("Posted ", "")
            
            # Convert to actual date
            return self.convert_relative_date(posted_date)
        
        return posted_date

    def get_job_description(self):
        """
        Extract job description with multiple fallback strategies
        and retry logic for robustness
        """
        # Sleep to ensure the content is loaded
        time.sleep(random.uniform(2, 3))
        
        # Try to expand the "Show more" button in job description
        self.expand_job_description()
        
        # Save the page source for debugging
        with open("job_detail_page.html", "w", encoding="utf-8") as f:
            f.write(self.driver.page_source)
            
        # Print the current URL for debugging
        self.logger.info(f"Current URL: {self.driver.current_url}")
            
        job_description = None
        
        # First approach: Use the most specific selectors
        description_selectors = [
            ".jobs-description-content__text",
            ".jobs-description__content",
            ".jobs-description",
            ".show-more-less-html__markup",
            "#job-details",
            ".jobs-box__html-content", 
            ".description__text"
        ]
        
        for selector in description_selectors:
            try:
                desc_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                if desc_element and desc_element.is_displayed():
                    job_description = desc_element.text.strip()
                    if job_description:
                        self.logger.info(f"✅ Found job description using selector: {selector}")
                        break
            except Exception:
                continue
        
        # Second approach: Try to get text from all elements that might contain the description
        if not job_description:
            try:
                # Find the main job details container
                job_details_container = self.driver.find_element(By.CSS_SELECTOR, ".jobs-details__main-content, .jobs-description, .job-view-layout")
                
                # Extract all paragraphs and list items within it
                text_elements = job_details_container.find_elements(By.CSS_SELECTOR, "p, li, span.jobs-box__body")
                
                # Combine all text
                if text_elements:
                    combined_text = "\n".join([elem.text.strip() for elem in text_elements if elem.text.strip()])
                    if combined_text:
                        job_description = combined_text
                        self.logger.info("✅ Found job description by combining paragraph elements")
            except Exception as e:
                self.logger.debug(f"Second approach failed: {str(e)}")
        
        # Third approach: Extract from the main panel as a whole
        if not job_description:
            try:
                main_panel = self.driver.find_element(By.CSS_SELECTOR, ".jobs-details__main-panel, .job-view-page")
                if main_panel:
                    # First try to find specific content areas within the panel
                    content_areas = main_panel.find_elements(By.CSS_SELECTOR, ".jobs-description, .job-details, .jobs-box__html-content")
                    
                    if content_areas:
                        # Combine text from all content areas
                        combined_text = "\n".join([area.text.strip() for area in content_areas if area.text.strip()])
                        if combined_text:
                            job_description = combined_text
                            self.logger.info("✅ Found job description from content areas in main panel")
                    
                    # If still no description, get all text from the main panel
                    if not job_description:
                        panel_text = main_panel.text.strip()
                        if panel_text:
                            # Remove common header elements like "Job details", "About the job", etc.
                            lines = panel_text.split("\n")
                            filtered_lines = []
                            skip_next = False
                            
                            for line in lines:
                                if skip_next:
                                    skip_next = False
                                    continue
                                    
                                if any(header in line.lower() for header in ["job details", "about the job", "about company"]):
                                    skip_next = True
                                    continue
                                
                                filtered_lines.append(line)
                            
                            cleaned_text = "\n".join(filtered_lines)
                            if cleaned_text:
                                job_description = cleaned_text
                                self.logger.info("✅ Found job description from entire main panel")
            except Exception as e:
                self.logger.debug(f"Third approach failed: {str(e)}")
                
        # Fourth approach (desperate): Get any text on the page that might be a job description
        if not job_description:
            try:
                # Look for elements that contain job description text
                possible_elements = self.driver.find_elements(By.XPATH, 
                    "//*[contains(text(), 'responsibilities') or contains(text(), 'requirements') or contains(text(), 'qualifications') or contains(text(), 'about the job')]"
                )
                
                if possible_elements:
                    # For each element, try to get its parent container which might contain the full description
                    for element in possible_elements:
                        try:
                            # Go up multiple levels to find a container
                            for _ in range(5):  # Try up to 5 levels up
                                parent = element.find_element(By.XPATH, "..")
                                parent_text = parent.text.strip()
                                
                                # If the parent has substantial text, it might be the job description
                                if parent_text and len(parent_text) > 200:  # Arbitrary threshold for "substantial"
                                    job_description = parent_text
                                    self.logger.info("✅ Found job description from parent of keyword element")
                                    break
                                
                                # Move up to the next parent
                                element = parent
                        except Exception:
                            continue
                            
                        if job_description:
                            break
            except Exception as e:
                self.logger.debug(f"Fourth approach failed: {str(e)}")
        
        # Return the description or a default message
        if job_description:
            return job_description
        else:
            self.logger.warning("⚠️ Could not find job description using any method")
            return "Description not available after multiple attempts"

    def check_complete_data(self, job_data):
        """Check if all required fields are present and non-empty"""
        missing_fields = []
        for field in self.required_fields:
            value = job_data.get(field)
            if not value or value == "N/A" or (field == 'job_description' and value == "Description not available after multiple attempts"):
                missing_fields.append(field)
                
        if missing_fields:
            self.logger.warning(f"⚠️ Missing fields: {', '.join(missing_fields)}")
            return False
        return True

    def validate_company_name(self, job_title, company_name):
        """Ensure company name is not the same as job title"""
        if not company_name or company_name == "N/A":
            return False
            
        if job_title and company_name in job_title:
            return False
            
        return True

    def extract_company_name(self, card):
        """Extract company name with special validation"""
        try:
            # Try multiple selectors for company name
            company_selectors = [
                ".job-card-container__company-name",
                ".job-card-container__primary-description",
                ".artdeco-entity-lockup__subtitle span",
                ".job-card-list__entity-lockup span",
                ".job-card-container__metadata-wrapper span",
                ".base-search-card__subtitle a"
            ]
            
            company = None
            for selector in company_selectors:
                try:
                    company_el = card.find_element(By.CSS_SELECTOR, selector)
                    company = company_el.text.strip()
                    self.logger.info(f"Found company using selector: {selector}")
                    break
                except Exception:
                    continue
                    
            # If company is still None, try XPath approach
            if not company:
                company_xpath_selectors = [
                    ".//h4[contains(@class,'entity-lockup__subtitle')]//span",
                    ".//div[@class='artdeco-entity-lockup__subtitle']//span",
                    ".//div[contains(@class,'base-search-card__subtitle')]//a",
                    ".//a[contains(@class,'job-card-container__company-name')]",
                    ".//div[contains(@class,'job-card-container__company-name')]",
                    ".//div[contains(@class,'base-search-card__subtitle')]//span",
                    ".//span[contains(@class,'job-card-container__primary-description')]"
                ]
                
                for selector in company_xpath_selectors:
                    try:
                        company_el = card.find_element(By.XPATH, selector)
                        company = company_el.text.strip()
                        self.logger.info(f"Found company using XPath selector: {selector}")
                        break
                    except Exception:
                        continue
                    
            # If still no company, look at the detail page
            if not company and self.driver:
                try:
                    # Look for company name in the job details page
                    company_detail_selectors = [
                        ".jobs-unified-top-card__company-name",
                        ".jobs-top-card__company-url",
                        ".topcard__org-name-link",
                        ".jobs-company__name"
                    ]
                    
                    for selector in company_detail_selectors:
                        try:
                            company_el = self.driver.find_element(By.CSS_SELECTOR, selector)
                            company = company_el.text.strip()
                            self.logger.info(f"Found company on detail page using selector: {selector}")
                            break
                        except Exception:
                            continue
                except Exception as e:
                    self.logger.debug(f"Failed to find company on detail page: {str(e)}")
            
            return company
        except Exception as e:
            self.logger.warning(f"⚠️ Error in extract_company_name: {str(e)}")
            return None

    def parse_jobs(self, sel):
        """
        Parse each job card by locating live elements with Selenium,
        finding title, company, location and posted date elements directly.
        Also clicks on each job to extract the full description.
        """
        cards = self.driver.find_elements(
            By.CSS_SELECTOR,
            "li.job-card-container, li.jobs-search-two-pane__job-card-container, li.scaffold-layout__list-item"
        )

        if not cards:
            self.logger.warning("⚠️ No job cards found via Selenium! Check selector patterns.")

        for index, card in enumerate(cards[:self.max_jobs]):
            # Initialize job data
            job_data = {field: "N/A" for field in self.required_fields}
            
            # Track if we need to retry this job
            retry_count = 0
            complete_data = False
            
            while not complete_data and retry_count < self.max_retries:
                if retry_count > 0:
                    self.logger.info(f"Retrying job {index+1} (attempt {retry_count+1}/{self.max_retries})...")
                    self.human_delay()
                
                try:
                    title_el = card.find_element(By.XPATH, ".//a[contains(@href,'/jobs/view')][1]")
                    job_data['job_title'] = title_el.text.strip()
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to extract job title: {str(e)}")
                
                # Extract company name with validation
                company = self.extract_company_name(card)
                if company and self.validate_company_name(job_data['job_title'], company):
                    job_data['company_name'] = company

                try:
                    loc_el = card.find_element(
                        By.XPATH,
                        ".//ul[contains(@class,'metadata-wrapper')]/li[1] | .//div[contains(@class,'caption')]/span"
                    )
                    job_data['location'] = loc_el.text.strip()
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to extract location: {str(e)}")

                try:
                    href = title_el.get_attribute('href')
                    job_url = urljoin('https://www.linkedin.com', href) if href and href.startswith('/') else href
                    job_data['job_url'] = job_url
                except Exception as e:
                    self.logger.warning(f"⚠️ Failed to extract job URL: {str(e)}")
                    
                # Click on the job card to load details
                try:
                    self.human_mouse_movement()
                    title_el.click()
                    self.human_delay()  # Wait for job details to load
                    
                    # Additional delay to ensure job details are fully loaded
                    time.sleep(random.uniform(3, 5))
                    
                    # Try to extract posted date from the details page
                    posted_date = self.extract_posted_date()
                    if posted_date:
                        job_data['posted_date'] = self.normalize_posted_date(posted_date)
                    
                    # Get job description
                    job_description = self.get_job_description()
                    if job_description:
                        job_data['job_description'] = job_description
                    
                    # If we got this far, try company name again from the detail page
                    if not self.validate_company_name(job_data['job_title'], job_data['company_name']):
                        company_selectors = [
                            ".jobs-unified-top-card__company-name",
                            ".jobs-top-card__company-url",
                            ".topcard__org-name-link",
                            ".jobs-company__name"
                        ]
                        
                        for selector in company_selectors:
                            try:
                                company_el = self.driver.find_element(By.CSS_SELECTOR, selector)
                                company = company_el.text.strip()
                                if company and self.validate_company_name(job_data['job_title'], company):
                                    job_data['company_name'] = company
                                    self.logger.info(f"Found company on detail page: {company}")
                                    break
                            except Exception:
                                continue
                except Exception as e:
                    self.logger.warning(f"⚠️ Error clicking job card or loading description: {str(e)}")
                
                # Try to get share URL if available (more permanent than standard URL)
                try:
                    share_button = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Share job']")
                    self.human_mouse_movement()
                    share_button.click()
                    time.sleep(random.uniform(1, 2))
                    
                    copy_link_button = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-label='Copy link']"))
                    )
                    
                    # The share URL may be in a data attribute or as text
                    share_url_element = self.driver.find_element(By.CSS_SELECTOR, "div.artdeco-modal__content input")
                    share_url = share_url_element.get_attribute("value")
                    if share_url:
                        job_data['job_url'] = share_url
                    
                    # Close the share modal
                    close_button = self.driver.find_element(By.CSS_SELECTOR, "button[aria-label='Dismiss']")
                    close_button.click()
                    time.sleep(random.uniform(0.5, 1.5))
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not get share URL: {str(e)}")
                
                # Make one final attempt to get posted date if still missing
                if job_data['posted_date'] == "N/A":
                    # Try to find any date-like text in the page
                    try:
                        all_spans = self.driver.find_elements(By.TAG_NAME, "span")
                        for span in all_spans:
                            text = span.text.strip().lower()
                            if any(x in text for x in ["ago", "hour", "day", "week", "month", "posted", "active"]):
                                job_data['posted_date'] = self.normalize_posted_date(span.text.strip())
                                self.logger.info(f"Found posted date on final attempt: {job_data['posted_date']}")
                                break
                    except Exception as e:
                        self.logger.debug(f"Final posted date attempt failed: {str(e)}")
                
                # Check if we have complete data
                complete_data = self.check_complete_data(job_data)
                if complete_data:
                    self.logger.info(f"✅ Successfully collected all data for job {index+1}")
                    break
                
                retry_count += 1
                
                # If we've hit max retries but still don't have complete data
                if retry_count >= self.max_retries and not complete_data:
                    self.logger.warning(f"⚠️ Failed to get complete data for job {index+1} after {self.max_retries} retries")
                    
                    # Set default values for any missing fields
                    if job_data['posted_date'] == "N/A":
                        job_data['posted_date'] = "Recently posted (estimated)"
                        
                    if job_data['job_description'] == "N/A":
                        # Create a basic description from the job title and company
                        job_data['job_description'] = f"This is a job posting for {job_data['job_title']} at {job_data['company_name']}. " \
                                                     f"The job is located in {job_data['location']}. " \
                                                     f"Please visit the job URL for more details about this position."
            
            # Store data for export (even if incomplete)
            self.collected_data.append(job_data)
            
            # Debug prints
            print(f"Job Title: {job_data.get('job_title', 'N/A')}")
            print(f"Company: {job_data.get('company_name', 'N/A')}")
            print(f"Location: {job_data.get('location', 'N/A')}")
            print(f"Posted Date: {job_data.get('posted_date', 'N/A')}")
            print(f"Job URL: {job_data.get('job_url', 'N/A')}")
            
            # Print first 100 chars of description with "..." if it's longer
            job_desc = job_data.get('job_description', 'N/A')
            print(f"Job Description: {job_desc[:100]}{'...' if len(job_desc) > 100 else ''}")
            print("-"*40)
            
            yield job_data
        
        self.logger.info(f"✅ Parsed {len(cards[:self.max_jobs])} job cards via Selenium live DOM.")
        
        # Export all collected data
        self.export_to_json()
        self.export_to_txt()
    
    def export_to_json(self):
        """Export collected job data to a JSON file"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"linkedin_jobs_{timestamp}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.collected_data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"✅ Successfully exported data to {filename}")
        except Exception as e:
            self.logger.error(f"❌ Error exporting to JSON: {str(e)}")
    
    def export_to_txt(self):
        """Export collected job data to a TXT file"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"linkedin_jobs_{timestamp}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                for job in self.collected_data:
                    f.write(f"Job Title: {job.get('job_title', 'N/A')}\n")
                    f.write(f"Company: {job.get('company_name', 'N/A')}\n")
                    f.write(f"Location: {job.get('location', 'N/A')}\n")
                    f.write(f"Posted Date: {job.get('posted_date', 'N/A')}\n")
                    f.write(f"Job URL: {job.get('job_url', 'N/A')}\n")
                    f.write(f"Job Description:\n{job.get('job_description', 'N/A')}\n")
                    f.write("-" * 80 + "\n\n")
            self.logger.info(f"✅ Successfully exported data to {filename}")
        except Exception as e:
            self.logger.error(f"❌ Error exporting to TXT: {str(e)}")

    def closed(self, reason):
        self.driver.quit()
        self.logger.info("✅ Browser closed successfully")