from environs import Env
from dataclasses import dataclass

@dataclass
class Db:
    db_user: str
    db_password: str
    db_database: str
    db_host: str
    db_port: int
    table_events:str
    table_tickets:str

@dataclass
class Logs:
    level: str
    dir: str
    format: str
    separate_log_without_rollover: bool

@dataclass
class Settings:
    db: Db
    logs: Logs

def get_settings(path: str):
    env = Env()
    env.read_env(path, override=True)

    return Settings(
        db=Db(
            db_user=env.str('DB_USER'),
            db_password=env.str('DB_PASSWORD'),
            db_database=env.str('DB_DATABASE'),
            db_host=env.str('DB_HOST'),
            db_port=env.int('DB_PORT'),
            table_events='seatgeek_events',
            table_tickets='seatgeek_tickets',
        ),
        logs=Logs(
            level=env.str('LOGS_LEVEL'),
            dir=env.str('LOGS_DIR'),
            format=env.str('LOGS_FORMAT'),
            separate_log_without_rollover=env.str('LOGS_ROLLOVER')
        )
    )

settings = get_settings('.env')
