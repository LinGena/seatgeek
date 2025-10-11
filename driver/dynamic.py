import os
import uuid
import random
from seleniumwire import undetected_chromedriver as uc_webdriver_wire
from dotenv import load_dotenv
from utils.func import load_from_file_json


load_dotenv(override=True)

class ChromeWebDriver:
    def create_driver(self):
        profile_id = str(uuid.uuid4())
        self.folder_temp = f"{os.path.abspath('chrome_data')}/{profile_id}"
        os.makedirs(self.folder_temp, exist_ok=True)
        self._set_chrome_options()
        self._create_chromedriver()
        return self.driver, self.folder_temp

    def _create_chromedriver(self):
        driver_version = os.getenv("DRIVER_VERSION", 136)
        proxies_list = load_from_file_json('proxies/proxies_list.json')
        random.shuffle(proxies_list)
        proxy = {
            'http':proxies_list[0],
            'https':proxies_list[0]
        }
        seleniumwire_options = {
            'proxy': proxy,
            'suppress_connection_errors': True,
            'disable_capture': False, 
            'request_storage': 'memory'
        }
        self.driver = uc_webdriver_wire.Chrome(version_main=int(driver_version),
                                    user_data_dir=self.folder_temp,
                                    enable_cdp_events=True,
                                    options=self.options,
                                    seleniumwire_options=seleniumwire_options)
        self.driver.set_page_load_timeout(60) 

    def _set_chrome_options(self):
        self.options = uc_webdriver_wire.ChromeOptions()
        self.options.add_argument("--lang=en-US")
        self.options.add_argument("--accept-language=en-US,en;q=0.9")
        self.options.add_argument("--intl.accept_languages=en-US,en;q=0.9")
        self.options.add_argument('--ignore-ssl-errors=yes')
        self.options.add_argument('--ignore-certificate-errors')
        self.options.add_argument('--disable-application-cache')
        self.options.add_argument('--start-maximized')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-setuid-sandbox')
        self.options.add_argument('--disable-logging')
        self.options.add_argument('--log-level=3')