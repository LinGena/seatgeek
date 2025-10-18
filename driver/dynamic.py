import os
import uuid
import random
import json
import logging
import sys
from seleniumwire import undetected_chromedriver as uc_webdriver_wire
from dotenv import load_dotenv
from utils.func import load_from_file_json
from proxies.proxy_ext import load_proxy

# Подавляем ошибки Selenium Wire
logging.getLogger('seleniumwire').setLevel(logging.CRITICAL)
logging.getLogger('seleniumwire.thirdparty.mitmproxy').setLevel(logging.CRITICAL)

# Подавляем вывод mitmproxy в stderr (BrokenPipeError и т.д.)
# Сохраняем оригинальный stderr для восстановления если нужно
_original_stderr = sys.stderr

load_dotenv(override=True)

class ChromeWebDriver:
    def create_driver(self, first_run: bool = False):
        profile_id = str(uuid.uuid4())
        self.first_run = first_run
        self.folder_temp = f"{os.path.abspath('chrome_data')}/{profile_id}"
        proxies_list = load_from_file_json('proxies/proxies_list.json')
        random.shuffle(proxies_list)
        self.current_proxy = proxies_list[0]
        self._force_en_locale()
        os.makedirs(self.folder_temp, exist_ok=True)
        self._set_chrome_options()
        self._create_chromedriver()
        return self.driver, self.folder_temp, self.current_proxy

    def _create_chromedriver(self):
        driver_version = os.getenv("DRIVER_VERSION", 135)
        if sys.platform != 'linux': 
            proxy = {
                'http':self.current_proxy,
                'https':self.current_proxy
            }
            import socket
            def get_free_port():
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('127.0.0.1', 0))
                    s.listen(1)
                    port = s.getsockname()[1]
                return port
        
            seleniumwire_port = get_free_port()
        
            seleniumwire_options = {
                'proxy': proxy,
                'suppress_connection_errors': True,
                'disable_capture': False, 
                'request_storage': 'memory',
                'port': seleniumwire_port,  # Уникальный порт для каждого потока
                'disable_encoding': True,  # Отключаем лишнюю обработку
            }
        
            # Создаем драйвер
            if self.first_run:
                self.driver = uc_webdriver_wire.Chrome(version_main=int(driver_version),
                                            user_data_dir=self.folder_temp,
                                            options=self.options,
                                            seleniumwire_options=seleniumwire_options)
            else:
                self.driver = uc_webdriver_wire.Chrome(version_main=int(driver_version),
                                            user_data_dir=self.folder_temp,
                                            user_multi_procs=True,
                                            options=self.options,
                                            seleniumwire_options=seleniumwire_options)
        else:
            if self.first_run:
                self.driver = uc_webdriver_wire.Chrome(version_main=int(driver_version),
                                            user_data_dir=self.folder_temp,
                                            options=self.options)
            else:
                self.driver = uc_webdriver_wire.Chrome(version_main=int(driver_version),
                                            user_data_dir=self.folder_temp,
                                            user_multi_procs=True,
                                            options=self.options)

        
        self.driver.set_page_load_timeout(60)
        
        # Подавляем traceback от mitmproxy в фоновом потоке
        import warnings
        warnings.filterwarnings("ignore", category=ResourceWarning)

        # Отключаем логирование CDP
        try:
            self.driver.execute_cdp_cmd("Log.disable", {})
        except:
            pass
        self.driver.execute_cdp_cmd("Network.enable", {})
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'language', {
                    get: () => 'en-US'
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(Intl, 'DateTimeFormat', {
                    get: () => function() {
                        return { resolvedOptions: () => ({ locale: 'en-US' }) }
                    }
                });
            """
        })
        self.driver.execute_cdp_cmd(
            "Network.setExtraHTTPHeaders",
            {
                "headers": {
                    "Accept-Language": "en-US,en;q=0.9"
                }
            }
        )   

    def _set_chrome_options(self):
        if sys.platform == 'linux':
            extensions = []
            proxy_extension_path = load_proxy(self.current_proxy, self.folder_temp)
            extensions.append(proxy_extension_path)
            self.options.add_argument(f"--load-extension={','.join(extensions)}")
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
        self.options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
        prefs = {
            'enable_do_not_track': True,
            "webrtc.ip_handling_policy": "disable_non_proxied_udp",
            "webrtc.multiple_routes_enabled": False,
            "webrtc.nonproxied_udp_enabled": False,
            "profile.default_content_setting_values.notifications": 1,
            'profile.managed_default_content_settings.images': 2,
            'profile.managed_default_content_settings.media_stream': 2
        }
        self.options.add_experimental_option("prefs", prefs)


    def _force_en_locale(self):
        prefs_dir = os.path.join(self.folder_temp, "Default")
        os.makedirs(prefs_dir, exist_ok=True)
        prefs_file = os.path.join(prefs_dir, "Preferences")
        prefs_data = {
            "intl": {
                "accept_languages": "en-US,en"
            },
            "browser": {
                "check_default_browser": False
            },
            "sync": {
                "setup_completed": True
            },
            "distribution": {
                "suppress_first_run_default_browser_prompt": True
            },
            "profile": {
                "exit_type": "None",
                "exited_cleanly": True
            },
            "safebrowsing": {
                "enabled": False
            },
            "extensions": {
                "settings": {}
            },
            "theme": {
                "use_system_theme": False
            }
        }
        with open(prefs_file, "w", encoding='utf-8') as f:
            json.dump(prefs_data, f, ensure_ascii=False, indent=2)