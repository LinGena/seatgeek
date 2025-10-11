import requests
import random
from bs4 import BeautifulSoup
from db.core import Db
from utils.func import load_from_file_json
from utils.logger import Logger
from datetime import datetime


class GetEvents:
    def __init__(self):
        self.logger = Logger().get_logger(__name__)
        self.proxies_list = load_from_file_json('proxies/proxies_list.json')

    def get(self):
        task_name = datetime.now().strftime('%Y%m%d')
        url = 'https://seatgeek.com/sitemap/events.xml'
        content = self.get_page_response(url)
        if not content:
            return
        links = self.get_links(content)
        if not links:
            self.logger.critical(f'There are not links from sitemap')
            return
        for idx, link in enumerate(links, 1):
            print(f"\nОбработка sitemap {idx}/{len(links)}: {link}")
            content = self.get_page_response(link)
            if content:
                event_urls = self.get_links(content)
                if not event_urls:
                    self.logger.critical(f'There are not event URLs from sitemap {link}')
                    continue
                self.insert_events(event_urls, task_name)


    def insert_events(self, event_urls: list, task_name: str):
        if not event_urls:
            print("  Нет URL для вставки")
            return
        db = Db()
        batch_size = 10000
        total_batches = (len(event_urls) + batch_size - 1) // batch_size

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(event_urls))
            batch = event_urls[start_idx:end_idx]
            values_list = []
            for url in batch:
                event_id = url.rstrip('/').split('/')[-1]
                values_list.append((event_id, url, task_name))
            try:
                sql = f"""
                    INSERT IGNORE INTO {db.table_events} (event_id, event_url, task_name) 
                    VALUES (%s, %s, %s)
                """
                db.cursor.executemany(sql, values_list)
                db.connection.commit()
            except Exception as ex:
                print(f"  Ошибка в батче {batch_num + 1}: {ex}")
        db.close_connection()
        print(f"  Всего обработано URL: {len(event_urls)}")
            
    def get_links(self, content: str) -> list:
        xml = BeautifulSoup(content, 'lxml-xml')
        lists = set()
        for loc in xml.find_all("loc"):
            lists.add(loc.text)
        return list(lists)

    def get_page_response(self, url: str, count_retry: int = 0) -> str:
        if count_retry > 3:
            self.logger.critical(f'There is not page content from link {url}')
            return None
        try:
            random.shuffle(self.proxies_list)
            proxies = {'http': self.proxies_list[0], 'https': self.proxies_list[0]}
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.google.com/",
                "Connection": "keep-alive"
                }
            response = requests.get(url, proxies=proxies, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except:
            pass
        return self.get_page_response(url, count_retry + 1)