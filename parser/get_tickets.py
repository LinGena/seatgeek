import time
import shutil
import json
import gzip
import logging
from datetime import datetime
from driver.dynamic import ChromeWebDriver
from utils.logger import Logger
from db.core import Db
from pyvirtualdisplay import Display
import sys


logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
logging.getLogger('seleniumwire').setLevel(logging.ERROR)
logging.getLogger('seleniumwire.thirdparty.mitmproxy').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.ERROR)

class GetTickets:
    def __init__(self):
        self.db = None
        self.driver = None
        self.folder_temp = None
        self.logger = Logger().get_logger(__name__)
        self.display = None

    def get(self):
        try:
            if sys.platform == 'linux':
                self.display = Display(visible=False, size=(1920, 1080))
                self.display.start()
            chrome_driver = ChromeWebDriver()
            self.driver, self.folder_temp, self.current_proxy = chrome_driver.create_driver()
            self.db = Db()

            while True:
                self.task_id = None
                self.task_name = None
                event_url = self.get_event_url()
                if not event_url:
                    break
                self.get_api_content(event_url)
        except Exception as ex:
            if 'DataDome' in str(ex):
                self.close_driver()
                return self.get()
            else:
                print(ex)
                self.close_driver()
                return self.get()
        finally:
            self.close_driver()

    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        if self.folder_temp:
            try:
                time.sleep(2)
                shutil.rmtree(self.folder_temp)
            except:
                pass
        if self.display:
            try:
                self.display.stop()
            except:
                pass
        if self.db:
            self.db.close_connection()

    def update_status(self, status: str):
        if self.task_id:
            sql = f"UPDATE {self.db.table_events} SET status=%s WHERE id=%s"
            self.db.insert(sql,(status, self.task_id))

    def get_event_url(self) -> str | None:
        try:
            sql = f"SELECT id, event_url, task_name FROM {self.db.table_events} WHERE status IS NULL ORDER BY RAND() LIMIT 1 FOR UPDATE"
            rows = self.db.select(sql)
            if not rows:
                return None
            self.task_id = rows[0][0]
            self.task_name = rows[0][2]
            self.update_status('processing')
            return rows[0][1]
        except Exception as ex:
            self.logger.error(f"Ошибка при получении события: {ex}")
        return None
    
    def get_api_content(self, event_url: str, wait_time: int = 30):
        try:
            self.driver.execute_cdp_cmd("Network.clearBrowserCache", {})
            del self.driver.requests
            self.driver.get(event_url)
            
            api_request = None
            start_time = time.time()
            while time.time() - start_time < wait_time:
                for request in self.driver.requests:
                    if '/api/event_listings_v2' in request.url:
                        if request.response and request.response.status_code == 200:
                            api_request = request
                            break
                if api_request:
                    break 
                time.sleep(0.5)
                if event_url != self.driver.current_url:
                    raise Exception(f'url unavailable')
                has_captcha, ip_blocked = self.check_captcha()
                if ip_blocked or has_captcha:
                    raise Exception('DataDome')

            if not api_request:
                self.update_status(None)
                print(f'No api_request')
                return
            
            if api_request.response:
                try:
                    response_body = api_request.response.body
                    try:
                        response_content = gzip.decompress(response_body).decode('utf-8')
                    except:
                        response_content = response_body.decode('utf-8')
                    response_data = json.loads(response_content)
                    if response_data:
                        all_listings = self.get_all_listings(response_data)
                        if all_listings:
                            self.insert_tikects(all_listings, self.task_name)
                            self.update_status('success')
                        else:
                            self.update_status('no listings')
                except Exception as ex:
                    self.logger.error(f"Ошибка сохранения response: {ex}")
            else:
                self.update_status(None)
        except Exception as ex:
            self.update_status(None)
            if 'DataDome' in str(ex):
                raise Exception('DataDome')
            if 'url unavailable' in str(ex):
                self.update_status('unavailable')
                return
            self.logger.error(f"Ошибка: {ex}")
            self.update_status(None)
        return

    def get_all_listings(self, data: dict):
        all_listings = []
        if data.get('listings'):
            for listing in data['listings']:
                try:
                    listing_dict = self.listing_to_dict(listing)
                except Exception as ex:
                    self.logger.error(f"Ошибка преобразования листинга: {ex}")
                    continue
                all_listings.append(listing_dict)
        return all_listings 

    def listing_to_dict(self, listing: dict) -> dict:    
        seat_numbers = listing.get('ss', [])
        seat_numbers_str = ','.join(map(str, seat_numbers)) if seat_numbers else ''
        cache_time = datetime.utcnow().strftime('%m/%d/%Y %H:%M:%S')
        return {
            # "marketplace": 'seatgeek',
            "event_id": listing.get('e', ''),
            "listing_id": listing.get('id', ''),
            "section_id": listing.get('s', ''),
            "section_name": listing.get('sf', ''),
            "section_name_raw": listing.get('sr', ''),
            "row_name": listing.get('r', ''),
            "seat_numbers": seat_numbers_str,
            "ticket_quantity_lots": listing.get('q', ''),
            "ticket_quantity": listing.get('q', ''),
            "value_score": listing.get('dq', {}).get('dq', ''),
            "quality_score": listing.get('dq', {}).get('ddq', ''),
            "listing_notes": listing.get('ptd', ''),
            "display_price_pre_checkout": listing.get('p', ''),
            "all_in_price_pre_checkout": listing.get('pf', ''),
            "display_price_checkout": listing.get('dp', ''),
            "buyer_fee_checkout": listing.get('f', ''),
            "other_fee_checkout": '',
            "sales_tax_checkout": '',
            "all_in_price_checkout": listing.get('dp', ''),
            "cache_time": cache_time
        }      
    
    def insert_tikects(self, datas: list[dict], task_name: str):
        if not datas:
            return
        try:
            sql = f"""
                INSERT INTO {self.db.table_tickets} (
                    event_id, listing_id, section_id, section_name, section_name_raw,
                    row_name, seat_numbers, ticket_quantity_lots, ticket_quantity,
                    value_score, quality_score, listing_notes,
                    display_price_pre_checkout, all_in_price_pre_checkout,
                    display_price_checkout, buyer_fee_checkout,
                    other_fee_checkout, sales_tax_checkout, all_in_price_checkout,
                    cache_time, task_name
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            batch_size = 1000
            total_inserted = 0
            for i in range(0, len(datas), batch_size):
                batch = datas[i:i + batch_size]
                values_list = []
                for listing in batch:
                    values = (
                        listing.get('event_id'),
                        listing.get('listing_id'),
                        listing.get('section_id'),
                        listing.get('section_name'),
                        listing.get('section_name_raw'),
                        listing.get('row_name'),
                        listing.get('seat_numbers'),
                        listing.get('ticket_quantity_lots'),
                        listing.get('ticket_quantity'),
                        listing.get('value_score'),
                        listing.get('quality_score'),
                        listing.get('listing_notes'),
                        listing.get('display_price_pre_checkout'),
                        listing.get('all_in_price_pre_checkout'),
                        listing.get('display_price_checkout'),
                        listing.get('buyer_fee_checkout'),
                        listing.get('other_fee_checkout'),
                        listing.get('sales_tax_checkout'),
                        listing.get('all_in_price_checkout'),
                        listing.get('cache_time'),
                        task_name
                    )
                    values_list.append(values)
                self.db.cursor.executemany(sql, values_list)
                self.db.connection.commit()
                total_inserted += len(values_list)
            print(f'  Вставлено {total_inserted} листингов')
        except Exception as ex:
            print(f'Ошибка вставки tickets: {ex}')

    def check_captcha(self) -> tuple[bool, bool]:
        """Проверяет наличие АКТИВНОЙ капчи DataDome на странице
        Возвращает: (найдена_капча, ip_blocked)
        """
        try:
            iframes = self.driver.find_elements('tag name', 'iframe')
            for iframe in iframes:
                try:
                    src = iframe.get_attribute('src') or ''
                    
                    if 'geo.captcha-delivery.com' not in src and 'captcha-delivery.com' not in src:
                        continue
                    
                    if 't=bv' in src:
                        return False, True
                    
                    if 't=fe' not in src:
                        continue
                    
                    if not iframe.is_displayed():
                        continue
                    
                    size = iframe.size
                    if size['width'] == 0 or size['height'] == 0:
                        continue
                    
                    visibility = iframe.value_of_css_property('visibility')
                    display = iframe.value_of_css_property('display')
                    
                    if visibility == 'hidden' or display == 'none':
                        continue
                    
                    return True, False
                    
                except Exception as ex:
                    continue
            
            return False, False
        except Exception as ex:
            self.logger.error(f"Ошибка проверки капчи: {ex}")
            return False, False