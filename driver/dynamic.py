import os
import uuid
import random
from seleniumwire import undetected_chromedriver as uc_webdriver_wire
from selenium_stealth import stealth
from dotenv import load_dotenv
from utils.func import load_from_file_json


load_dotenv(override=True)

class ChromeWebDriver:
    def create_driver(self):
        profile_id = str(uuid.uuid4())
        self.folder_temp = f"{os.path.abspath('chrome_data')}/{profile_id}"
        os.makedirs(self.folder_temp, exist_ok=True)
        self.stealth_params = self._get_random_stealth_params()
        self._set_chrome_options()
        self._create_chromedriver()
        self._apply_stealth_mode()
        return self.driver, self.folder_temp, self.current_proxy

    def _create_chromedriver(self):
        driver_version = os.getenv("DRIVER_VERSION", 136)
        proxies_list = load_from_file_json('proxies/proxies_list.json')
        random.shuffle(proxies_list)
        self.current_proxy = proxies_list[0]
        proxy = {
            'http':self.current_proxy,
            'https':self.current_proxy
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

    def _get_random_stealth_params(self):
        """Генерирует случайные но реалистичные параметры для stealth mode"""
        
        # Случайная платформа
        platforms = [
            {
                "platform": "Win32",
                "vendors": [
                    ("NVIDIA Corporation", ["NVIDIA GeForce GTX 1060", "NVIDIA GeForce RTX 2060", "NVIDIA GeForce RTX 3060"]),
                    ("Intel Inc.", ["Intel(R) UHD Graphics 630", "Intel(R) HD Graphics 620", "Intel Iris OpenGL Engine"]),
                    ("AMD", ["AMD Radeon RX 580", "AMD Radeon RX 5700", "Radeon(TM) RX Vega 10 Graphics"]),
                ]
            },
            {
                "platform": "MacIntel",
                "vendors": [
                    ("Apple Inc.", ["Apple M1", "Apple M2", "Apple GPU"]),
                    ("Intel Inc.", ["Intel(R) Iris(TM) Plus Graphics 640", "Intel Iris Pro OpenGL Engine"]),
                ]
            },
            {
                "platform": "Linux x86_64",
                "vendors": [
                    ("NVIDIA Corporation", ["NVIDIA GeForce GTX 1650", "NVIDIA GeForce RTX 2070"]),
                    ("Intel", ["Mesa Intel(R) UHD Graphics", "Mesa DRI Intel(R) HD Graphics 630"]),
                ]
            }
        ]
        
        # Выбираем случайную платформу
        platform_config = random.choice(platforms)
        platform = platform_config["platform"]
        
        # Выбираем случайного вендора и рендерер
        webgl_vendor, renderers = random.choice(platform_config["vendors"])
        renderer = random.choice(renderers)
        
        # Случайные языки
        language_sets = [
            ["en-US", "en"],
            ["en-GB", "en"],
            ["en-US", "en", "es"],
            ["en-GB", "en", "fr"],
        ]
        languages = random.choice(language_sets)
        
        return {
            "languages": languages,
            "vendor": "Google Inc.",
            "platform": platform,
            "webgl_vendor": webgl_vendor,
            "renderer": renderer,
            "fix_hairline": True
        }
    
    def _apply_stealth_mode(self):
        stealth(self.driver,
            languages=self.stealth_params["languages"],
            vendor=self.stealth_params["vendor"],
            platform=self.stealth_params["platform"],
            webgl_vendor=self.stealth_params["webgl_vendor"],
            renderer=self.stealth_params["renderer"],
            fix_hairline=self.stealth_params["fix_hairline"],
        )

    def _set_chrome_options(self):
        self.options = uc_webdriver_wire.ChromeOptions()
        lang_first = self.stealth_params["languages"][0]
        lang_str = ",".join(self.stealth_params["languages"])
        self.options.add_argument(f"--lang={lang_first}")
        self.options.add_argument(f"--accept-language={lang_str};q=0.9")
        self.options.add_argument(f"--intl.accept_languages={lang_str};q=0.9")
        self.options.add_argument('--ignore-ssl-errors=yes')
        self.options.add_argument('--ignore-certificate-errors')
        self.options.add_argument('--disable-application-cache')
        self.options.add_argument('--start-maximized')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-setuid-sandbox')
        self.options.add_argument('--disable-logging')
        self.options.add_argument('--log-level=3')