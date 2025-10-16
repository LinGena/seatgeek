import time
import random
import cv2
import numpy as np
import base64
from PIL import Image
from io import BytesIO
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from logging import Logger


class CaptchaSolver:
    """Класс для работы с DataDome капчей - ЧИСТАЯ версия БЕЗ логов и скриншотов"""
    
    def __init__(self, driver: WebDriver, logger: Logger):
        self.driver = driver
        self.logger = logger
    
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
                        print(f"⚠️  IP заблокирован DataDome (t=bv)")
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
                    
                    print(f"🔍 Найден активный iframe DataDome")
                    return True, False
                    
                except Exception as ex:
                    continue
            
            return False, False
        except Exception as ex:
            self.logger.error(f"Ошибка проверки капчи: {ex}")
            return False, False
    
    def detect_puzzle_gap_github_method(self, background_image, puzzle_piece_image):
        """ОРИГИНАЛЬНЫЙ метод из https://github.com/glizzykingdreko/Datadome-GeeTest-Captcha-Solver
        
        Template matching для поиска позиции кусочка паззла.
        Возвращает ЦЕНТР кусочка - это позиция для слайдера!
        """
        try:
            # Конвертируем PIL в numpy
            if isinstance(background_image, Image.Image):
                bg_array = np.array(background_image)
                bg_bgr = cv2.cvtColor(bg_array, cv2.COLOR_RGB2BGR)
            else:
                bg_bgr = background_image
            
            if isinstance(puzzle_piece_image, Image.Image):
                piece_array = np.array(puzzle_piece_image)
                piece_bgr = cv2.cvtColor(piece_array, cv2.COLOR_RGB2BGR)
            else:
                piece_bgr = puzzle_piece_image
            
            # ОРИГИНАЛЬНЫЙ КОД GITHUB: Apply edge detection
            edge_background = cv2.Canny(bg_bgr, 100, 200)
            edge_piece = cv2.Canny(piece_bgr, 100, 200)
            
            # Convert to RGB for visualization
            edge_background_rgb = cv2.cvtColor(edge_background, cv2.COLOR_GRAY2RGB)
            edge_piece_rgb = cv2.cvtColor(edge_piece, cv2.COLOR_GRAY2RGB)
            
            # Template matching
            res = cv2.matchTemplate(edge_background_rgb, edge_piece_rgb, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            # Calculate center
            h, w = edge_piece.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
                        
            # Возвращаем ЦЕНТР (позиция для слайдера)
            return center_x
            
        except Exception as ex:
            self.logger.error(f"Ошибка template matching: {ex}")
            return None
    
    def solve_slider_captcha(self) -> bool:
        """Решает DataDome/GeeTest капчу"""
        try:            
            # Находим iframe с капчей
            iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
            captcha_iframe = None
            
            for iframe in iframes:
                try:
                    src = iframe.get_attribute('src') or ''
                    if 'captcha-delivery.com' in src and iframe.is_displayed():
                        captcha_iframe = iframe
                        break
                except:
                    continue
            
            if not captcha_iframe:
                return False
            
            # Переключаемся в iframe
            self.driver.switch_to.frame(captcha_iframe)

            # Дополнительно ждем пока Canvas #2 получит позицию
            try:
                for attempt in range(10):
                    canvases_check = self.driver.find_elements(By.CSS_SELECTOR, "div#captcha__puzzle canvas")
                    if len(canvases_check) > 1:
                        block_style = canvases_check[1].get_attribute('style') or ''
                        if 'left' in block_style and 'left: 0px' not in block_style:
                            print(f"✅ Canvas #2 загружен")
                            break
                    time.sleep(0.5)
            except:
                pass
            
            # Ищем canvas с паззлом
            puzzle_canvas = None
            target_position = None
            
            try:
                puzzle_container = self.driver.find_element(By.CSS_SELECTOR, "div#captcha__puzzle")
                canvases = puzzle_container.find_elements(By.TAG_NAME, "canvas")
                
                if len(canvases) > 0:
                    puzzle_canvas = canvases[0]
                
                # Проверяем Canvas #2
                if len(canvases) > 1:
                    block_canvas = canvases[1]
                    block_style = block_canvas.get_attribute('style') or ''
                    
                    # Парсим left из style
                    if 'left:' in block_style or 'left :' in block_style:
                        try:
                            block_left = int(block_style.split('left')[1].split(':')[1].split('px')[0].strip())
                            target_position = block_left
                            print(f"   ⭐ Canvas #2 position: {block_left}px")
                        except:
                            pass
                            
            except Exception as e:
                self.logger.error(f"Ошибка при поиске canvas: {e}")
            
            # Получаем canvas data через JavaScript (с альфа-каналом!)
            final_target = None
            
            if puzzle_canvas:
                try:
                    # Canvas #1 - фон
                    bg_data_url = self.driver.execute_script("return arguments[0].toDataURL('image/png');", puzzle_canvas)
                    bg_data = bg_data_url.split(',')[1]
                    bg_bytes = base64.b64decode(bg_data)
                    bg_image = Image.open(BytesIO(bg_bytes))
                    
                    # Canvas #2 - кусочек
                    piece_image = None
                    if len(canvases) > 1:
                        piece_data_url = self.driver.execute_script("return arguments[0].toDataURL('image/png');", canvases[1])
                        piece_data = piece_data_url.split(',')[1]
                        piece_bytes = base64.b64decode(piece_data)
                        piece_full = Image.open(BytesIO(piece_bytes))
                        
                        # Вырезаем непрозрачную часть
                        piece_array = np.array(piece_full.convert('RGBA'))
                        
                        if piece_array.shape[2] == 4:
                            alpha = piece_array[:,:,3]
                            non_transparent = alpha > 10
                            
                            rows = np.any(non_transparent, axis=1)
                            cols = np.any(non_transparent, axis=0)
                            
                            if rows.any() and cols.any():
                                y_min, y_max = np.where(rows)[0][[0, -1]]
                                x_min, x_max = np.where(cols)[0][[0, -1]]
                                
                                # Вырезаем НАСТОЯЩИЙ кусочек
                                piece_image = piece_full.crop((x_min, y_min, x_max + 1, y_max + 1))
                            else:
                                piece_image = piece_full
                        else:
                            piece_image = piece_full
                    
                    # Применяем GitHub метод
                    if piece_image:
                        center_x = self.detect_puzzle_gap_github_method(bg_image, piece_image)
                        if center_x:
                            final_target = center_x
                            print(f"✅ Найдена позиция: {final_target}px")
                    
                except Exception as e:
                    self.logger.error(f"Ошибка анализа canvas: {e}")
            
            # Если не получилось через template matching - используем Canvas #2 position
            if final_target is None and target_position is not None:
                final_target = target_position
                print(f"   Используем позицию Canvas #2: {final_target}px")
            
            if final_target is None:
                self.driver.switch_to.default_content()
                return False
            
            # Находим слайдер
            slider = None
            try:
                slider = self.driver.find_element(By.CSS_SELECTOR, "div.slider")
                
                if not slider.is_displayed():
                    slider = None
            except Exception as e:
                self.logger.error(f"Слайдер не найден: {e}")
            
            if not slider:
                self.driver.switch_to.default_content()
                return False
            
            # Получаем текущую позицию слайдера
            current_left = 0
            style = slider.get_attribute('style') or ''
            if 'left:' in style:
                try:
                    left_str = style.split('left:')[1].split('px')[0].strip()
                    current_left = int(left_str)
                except:
                    pass
            
            # Рассчитываем смещение
            offset = final_target - current_left
            
            print(f"\n{'='*60}")
            print(f"📊 Движение слайдера:")
            print(f"   Текущая позиция: {current_left}px")
            print(f"   Целевая позиция: {final_target}px")
            print(f"   Смещение: {offset}px")
            print(f"{'='*60}\n")
            
            # Двигаем слайдер
            try:
                actions = ActionChains(self.driver)
                actions.click_and_hold(slider).pause(0.2)
                
                steps = 15
                for i in range(steps):
                    step_offset = offset / steps
                    step_offset += random.uniform(-0.5, 0.5)
                    actions.move_by_offset(step_offset, 0)
                    actions.pause(random.uniform(0.02, 0.05))
                
                actions.release().perform()
                time.sleep(1)
            except Exception as e:
                self.logger.error(f"Ошибка движения слайдера: {e}")
            
            time.sleep(1)
            
            # Возвращаемся в основной контекст
            self.driver.switch_to.default_content()
            
            # Проверяем результат
            time.sleep(1)
            has_captcha, _ = self.check_captcha()
            
            if not has_captcha:
                print(f"🎉 Капча решена!")
            return True

            
        except Exception as ex:
            self.logger.error(f"Ошибка решения капчи: {ex}")
            import traceback
            print(f"❌ Exception: {traceback.format_exc()}")
            
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            
            return False

