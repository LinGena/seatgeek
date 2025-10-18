import threading
import os
import sys
from dotenv import load_dotenv
import time
from proxies.get_proxies import update_proxies
from db.core import IsDbTable
from parser.get_tickets import GetTickets
from parser.get_events import GetEvents


load_dotenv(override=True)

os.environ['PYVIRTUALDISPLAY_DISPLAYFD'] = '0'

class StderrFilter:
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        self.buffer = ''

    def write(self, text):
        if 'BrokenPipeError' in text or 'TcpDisconnect' in text or 'seleniumwire' in text:
            return  
        self.original_stderr.write(text)

    def flush(self):
        self.original_stderr.flush()

sys.stderr = StderrFilter(sys.stderr)


def run_worker(worker_id):
    """Запускает GetTickets в отдельном потоке"""
    try:
        GetTickets().get()
    except Exception as ex:
        print(f"❌ Поток #{worker_id} ошибка: {ex}")


def first_run():
    from driver.dynamic import ChromeWebDriver
    import shutil
    try:
        init_driver = ChromeWebDriver()
        driver, folder_temp, proxy = init_driver.create_driver(first_run=True)
        try:
            driver.quit()
        except:
            pass
        try:
            time.sleep(2)
            shutil.rmtree(folder_temp)
        except:
            pass
    except Exception as ex:
        print(f"⚠️ Ошибка инициализации: {ex}")

def main():
    first_run()
    
    num_threads = int(os.getenv("THREADS_COUNT", 10))
    threads = []
    
    for i in range(1, num_threads + 1):
        thread = threading.Thread(target=run_worker, args=(i,), daemon=True)
        thread.start()
        threads.append(thread)
        time.sleep(2)  

    try:
        for thread in threads:
            thread.join()
        print("✅ Все потоки завершены!")
    except KeyboardInterrupt:
        print("\n⚠️ Получен сигнал остановки...")
        print("⏳ Ожидание завершения активных потоков...")


if __name__ == "__main__":
    IsDbTable().check()
    update_proxies()
    # GetEvents().get()
    
    main()
    
    # Запуск в однопоточном режиме
    # GetTickets().get()
