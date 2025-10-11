from mysql.connector import connect, Error
import time
from config.settings import settings
from utils.logger import Logger


class Db():
    def __init__(self):
        self.logger = Logger().get_logger(__name__)
        self.connecting()
        self.table_events= settings.db.table_events
        self.table_tickets= settings.db.table_tickets

    def connecting(self, max_retries=10, delay=5) -> None:    
        for attempt in range(max_retries):
            try:
                self.connection = connect(
                    host=settings.db.db_host,
                    port=settings.db.db_port,
                    user=settings.db.db_user,
                    password=settings.db.db_password,
                    database=settings.db.db_database
                )
                self.cursor = self.connection.cursor()
                return 
            except Error as e:
                self.logger.error(f"Connection failed: {e}")
                time.sleep(delay)
        raise Exception("Could not connect to the database after multiple attempts")

    def __del__(self):
        self.close_connection()

    def insert(self, sql: str, params: tuple = None) -> None:
        if not params:
            self.cursor.execute(sql)
        else:
            self.cursor.execute(sql, params)
        self.connection.commit()

    def select(self, sql: str) -> list:
        self.cursor.execute(sql)
        rows = self.cursor.fetchall() 
        return rows
        
    def close_connection(self) -> None:
        self.connection.close()


class IsDbCreated():
    def check(self) -> None:
        for attempt in range(5):
            try:
                connection = connect(host=settings.db.db_host, 
                                     port=settings.db.db_port, 
                                     user=settings.db.db_user, 
                                     password=settings.db.db_password)
                cursor = connection.cursor()
                cursor.execute("SET GLOBAL sql_mode=(SELECT REPLACE(@@sql_mode, 'ONLY_FULL_GROUP_BY', ''))")
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {settings.db.db_database}")
                connection.close()
                IsDbTable().check()
                return
            except Error as e:
                print(f"Connection failed: {e}")
                time.sleep(5)
        raise Exception("Could not connect to MySQL for database creation after multiple attempts.")


class IsDbTable(Db):
    def __init__(self):
        super().__init__()

    def check(self) -> None:
        if self.check_tables(self.table_events):
            self.create_events()
        if self.check_tables(self.table_tickets):
            self.create_tickets()

    def create_events(self) -> None:
        self.insert(f"""
            CREATE TABLE `{self.table_events}` (
                `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `event_id` VARCHAR(255) NOT NULL,
                `event_url` VARCHAR(500),
                `date_added` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `task_name` VARCHAR(50) NOT NULL,
                `status` VARCHAR(50),
                UNIQUE KEY `unique_event_task` (`event_id`, `task_name`),
                INDEX `idx_task_name` (`task_name`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """)

    def create_tickets(self) -> None:
        self.insert(f"""
            CREATE TABLE `{self.table_tickets}` (
                `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `event_id` VARCHAR(50) NOT NULL,
                `listing_id` VARCHAR(255),
                `section_id` VARCHAR(50),
                `section_name` VARCHAR(255),
                `section_name_raw` VARCHAR(255),
                `row_name` VARCHAR(50),
                `seat_numbers` TEXT,
                `ticket_quantity_lots` VARCHAR(255),
                `ticket_quantity` VARCHAR(255),
                `value_score` VARCHAR(255),
                `quality_score` VARCHAR(255),
                `listing_notes` TEXT,
                `display_price_pre_checkout` VARCHAR(255),
                `all_in_price_pre_checkout` VARCHAR(255),
                `display_price_checkout` VARCHAR(255),
                `buyer_fee_checkout` VARCHAR(255),
                `other_fee_checkout` VARCHAR(255),
                `sales_tax_checkout` VARCHAR(255),
                `all_in_price_checkout` VARCHAR(255),
                `cache_time` VARCHAR(50),
                `date_added` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `task_name` VARCHAR(50),
                INDEX idx_event_id (event_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """)
    
    def check_tables(self, table_name: str) -> bool:
        sql = f"SHOW TABLES FROM {settings.db.db_database} LIKE '{table_name}'"
        rows = self.select(sql)
        if len(rows) == 0:
            return True
        return False