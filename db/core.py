from mysql.connector import connect, Error
import time
from config.settings import settings
from utils.logger import Logger


class Db():
    def __init__(self):
        self.logger = Logger().get_logger(__name__)
        self.connecting()
        self.table_tasks = settings.db.table_tasks    
        self.table_datas = settings.db.table_datas 

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
        if self.check_tables(self.table_tasks):
            self.create_tasks()
        if self.check_tables(self.table_datas):
            self.create_datas()

    def create_tasks(self) -> None:
        self.insert(f"""
            CREATE TABLE `{self.table_tasks}` (
                `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `year` VARCHAR(255),
                `make` VARCHAR(255),
                `type` VARCHAR(255),
                `model` VARCHAR(255),
                `engine` VARCHAR(255),
                `response` JSON,
                `status` INTEGER,
                `date_update` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_year (year),
                INDEX idx_make (make),
                INDEX idx_type (type),
                INDEX idx_model (model),
                INDEX idx_engine (engine),
                UNIQUE KEY uniq_year_make_model_engine (year(50), make(50), type(50), model(50), engine(70))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """)

    def create_datas(self) -> None:
        self.insert(f"""
            CREATE TABLE `{self.table_datas}` (
                `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                `datas` JSON,
                `URL` VARCHAR(255),
                `Timestamp` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """)
    
    def check_tables(self, table_name: str) -> bool:
        sql = f"SHOW TABLES FROM {settings.db.db_database} LIKE '{table_name}'"
        rows = self.select(sql)
        if len(rows) == 0:
            return True
        return False