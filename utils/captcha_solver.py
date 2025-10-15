import time
import random
import cv2
import numpy as np
import os
import json
import base64
from datetime import datetime
from PIL import Image
from io import BytesIO
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from logging import Logger

class CaptchaSolver:
    """Класс для работы с DataDome капчей"""
    
    def __init__(self, driver: WebDriver, logger: Logger):
        self.driver = driver
        self.logger = logger
    
        # Создаём папку для скриншотов капчи
        self.screenshots_dir = "captcha_screenshots"
        os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # Логирование действий для отладки
        self.actions_log = []
        
    def _log_action(self, action: str, details: dict = None):
        """Логирует действие для последующего сохранения в JSON"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action
        }
        if details:
            log_entry.update(details)
        self.actions_log.append(log_entry)
    
    def _save_log(self):
        """Сохраняет лог действий в JSON файл"""
        try:
            log_file = os.path.join(self.screenshots_dir, "captcha_actions.json")
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(self.actions_log, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения лога: {e}")
    
    def check_captcha(self) -> tuple[bool, bool]:
        """Проверяет наличие АКТИВНОЙ капчи DataDome на странице
        Возвращает: (найдена_капча, ip_blocked)
        """
        try:
            # Проверяем наличие ВИДИМОГО iframe с geo.captcha-delivery.com
            iframes = self.driver.find_elements('tag name', 'iframe')
            for iframe in iframes:
                try:
                    src = iframe.get_attribute('src') or ''
                    
                    # Проверяем что это iframe капчи
                    if 'geo.captcha-delivery.com' not in src and 'captcha-delivery.com' not in src:
                        continue
                    
                    # Проверяем параметр t - должен быть t=fe (если t=bv то IP забанен)
                    if 't=bv' in src:
                        print(f"⚠️  IP заблокирован DataDome (t=bv)")
                        return False, True  # ip_blocked = True
                    
                    if 't=fe' not in src:
                        continue
                    
                    # Проверяем что iframe действительно видим и имеет размеры
                    if not iframe.is_displayed():
                        continue
                    
                    size = iframe.size
                    if size['width'] == 0 or size['height'] == 0:
                        continue
                    
                    # Проверяем что iframe не скрыт через CSS
                    visibility = iframe.value_of_css_property('visibility')
                    display = iframe.value_of_css_property('display')
                    
                    if visibility == 'hidden' or display == 'none':
                        continue
                    
                    print(f"🔍 Найден активный iframe DataDome (размер: {size['width']}x{size['height']})")
                    print(f"   URL: {src[:120]}...")
                    return True, False
                    
                except Exception as ex:
                    # Ошибка при проверке конкретного iframe - пропускаем
                    continue
            
            return False, False
        except Exception as ex:
            self.logger.error(f"Ошибка проверки капчи: {ex}")
            return False, False
    
    def save_page_with_captcha(self):
        """Сохраняет скриншот капчи (не всего экрана!)"""
        try:
            # Находим iframe с капчей и переключаемся в него
            iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
            for iframe in iframes:
                try:
                    src = iframe.get_attribute('src') or ''
                    if 'captcha-delivery.com' in src and iframe.is_displayed():
                        # Переключаемся в iframe
                        self.driver.switch_to.frame(iframe)
                        
                        # Делаем скриншот контейнера капчи внутри iframe
                        screenshot_filename = os.path.join(self.screenshots_dir, "captcha_before.png")
                        try:
                            # Пробуем найти div#captcha__puzzle
                            puzzle = self.driver.find_element(By.CSS_SELECTOR, "div#captcha__puzzle")
                            puzzle.screenshot(screenshot_filename)
                        except:
                            # Если не получилось, ищем главный контейнер
                            try:
                                main = self.driver.find_element(By.CSS_SELECTOR, "div.main__container")
                                main.screenshot(screenshot_filename)
                            except:
                                # В крайнем случае - body
                                body = self.driver.find_element(By.TAG_NAME, "body")
                                body.screenshot(screenshot_filename)
                        
                        # Возвращаемся обратно
                        self.driver.switch_to.default_content()
                        print(f"📸 Капча обнаружена! Скриншот: {screenshot_filename}")
                        return
                except:
                    self.driver.switch_to.default_content()
                    continue
            
            print(f"📸 Капча обнаружена!")
            
        except Exception as ex:
            self.logger.error(f"Ошибка сохранения страницы с капчей: {ex}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
    
    def detect_puzzle_gap(self, background_image, puzzle_piece_image=None):
        """Определяет X-позицию паззла используя template matching (ОРИГИНАЛЬНЫЙ метод из GitHub)
        
        МЕТОД ИЗ https://github.com/glizzykingdreko/Datadome-GeeTest-Captcha-Solver:
        - Применяем Canny edge detection к обоим изображениям
        - Template matching находит где кусочек совпадает с фоном
        - Возвращаем ЦЕНТР найденного кусочка (center_x)
        - Это и есть позиция куда должен двигаться слайдер!
        
        Args:
            background_image: PIL Image или numpy array фона
            puzzle_piece_image: PIL Image или numpy array кусочка (опционально)
        
        Returns:
            (center_x, width) - ЦЕНТР позиции кусочка и его ширина
            None - если не удалось определить или нет puzzle_piece
        """
        try:
            # Конвертируем PIL Image в numpy array для OpenCV
            bg_array = np.array(background_image)
            bg_bgr = cv2.cvtColor(bg_array, cv2.COLOR_RGB2BGR)
            
            # Если есть кусочек паззла - используем ОРИГИНАЛЬНЫЙ метод из GitHub
            if puzzle_piece_image is not None:
                piece_array = np.array(puzzle_piece_image)
                piece_bgr = cv2.cvtColor(piece_array, cv2.COLOR_RGB2BGR)
                
                # ТОЧНО КАК В GITHUB: Apply edge detection
                edge_background = cv2.Canny(bg_bgr, 100, 200)
                edge_piece = cv2.Canny(piece_bgr, 100, 200)
                
                # Сохраняем для отладки
                cv2.imwrite(os.path.join(self.screenshots_dir, "bg_edges.png"), edge_background)
                cv2.imwrite(os.path.join(self.screenshots_dir, "piece_edges.png"), edge_piece)
                
                # ТОЧНО КАК В GITHUB: Convert to RGB for visualization
                edge_background_rgb = cv2.cvtColor(edge_background, cv2.COLOR_GRAY2RGB)
                edge_piece_rgb = cv2.cvtColor(edge_piece, cv2.COLOR_GRAY2RGB)
                
                # ТОЧНО КАК В GITHUB: Template matching
                res = cv2.matchTemplate(edge_background_rgb, edge_piece_rgb, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                
                # ТОЧНО КАК В GITHUB: Calculate required values
                h, w = edge_piece.shape[:2]
                top_left = max_loc
                bottom_right = (top_left[0] + w, top_left[1] + h)
                
                # ЦЕНТР кусочка - это позиция для слайдера!
                center_x = top_left[0] + w // 2
                center_y = top_left[1] + h // 2
                
                # Рисуем результат КАК В GITHUB
                debug_img = bg_bgr.copy()
                cv2.rectangle(debug_img, top_left, bottom_right, (0, 0, 255), 2)
                # Зеленая вертикальная линия на ЦЕНТРЕ
                cv2.line(debug_img, (center_x, 0), (center_x, bg_bgr.shape[0]), (0, 255, 0), 2)
                # Зеленая горизонтальная линия
                cv2.line(debug_img, (0, center_y), (bg_bgr.shape[1], center_y), (0, 255, 0), 2)
                
                cv2.imwrite(os.path.join(self.screenshots_dir, "template_match_result.png"), debug_img)
                
                print(f"   Template matching (GitHub method): центр кусочка at {center_x}px (confidence: {max_val:.3f})")
                
                # Возвращаем ЦЕНТР кусочка (позиция для слайдера) и ширину
                return (center_x, w)
            
            # Метод контуров - CANNY + правильные критерии
            gray = cv2.cvtColor(bg_bgr, cv2.COLOR_BGR2GRAY)
            cv2.imwrite(os.path.join(self.screenshots_dir, "captcha_gray.png"), gray)
            
            # Canny edge detection
            edges = cv2.Canny(gray, 50, 150)
            cv2.imwrite(os.path.join(self.screenshots_dir, "captcha_edges.png"), edges)
            
            # Ищем САМЫЙ БОЛЬШОЙ КОНТУР (это и есть вырез!)
            height, width = gray.shape
            
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # УНИВЕРСАЛЬНОЕ РЕШЕНИЕ: ищем по ФОРМЕ, а не по позиции!
            # Вырез паззла может быть В ЛЮБОМ месте (слева, центр, справа)
            puzzle_candidates = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = cv2.contourArea(contour)
                
                # УНИВЕРСАЛЬНЫЕ КРИТЕРИИ ВЫРЕЗА ПАЗЗЛА:
                # 1. Размер: ширина 20-150px, высота 20-150px (широкий диапазон!)
                # 2. НЕ на краю: 5 < x < width-5
                # 3. Форма: не слишком узкий (h/w > 0.5) и не слишком широкий (h/w < 2)
                # 4. Достаточная площадь: area > 100
                if 20 < w < 150 and 20 < h < 150:
                    if 5 < x < width - 5:  # Не на краю
                        aspect_ratio = h / w if w > 0 else 0
                        if 0.5 < aspect_ratio < 2.0 and area > 100:  # Разумная форма
                            center_x = x + w // 2
                            puzzle_candidates.append({
                                'x': x,
                                'y': y,
                                'w': w,
                                'h': h,
                                'area': area,
                                'center_x': center_x,
                                'aspect_ratio': aspect_ratio
                            })
            
            if puzzle_candidates:
                # Сортируем по площади - берем самый большой подходящий
                puzzle_candidates.sort(key=lambda c: c['area'], reverse=True)
                
                best = puzzle_candidates[0]
                gap_left_edge = best['x']
                gap_center = best['center_x']
                
                # Рисуем найденный контур для отладки (используем bg_bgr который уже есть)
                debug_img = bg_bgr.copy()
                
                # Рисуем прямоугольник вокруг выреза
                cv2.rectangle(debug_img, (best['x'], best['y']), (best['x']+best['w'], best['y']+best['h']), (0, 0, 255), 2)
                
                # Рисуем вертикальную линию на ЦЕНТРЕ (ТОЛСТАЯ КРАСНАЯ)
                cv2.line(debug_img, (gap_center, 0), (gap_center, height), (0, 0, 255), 3)
                
                # Рисуем целевую позицию (левый + width/3.25 + 3) ЗЕЛЁНОЙ ТОЛСТОЙ
                target_pos = gap_left_edge + int(best['w'] / 3.25) + 3
                cv2.line(debug_img, (target_pos, 0), (target_pos, height), (0, 255, 0), 3)
                
                cv2.imwrite(os.path.join(self.screenshots_dir, "contours_method.png"), debug_img)
                
                # Возвращаем ЛЕВЫЙ КРАЙ выреза и ШИРИНУ (для старого метода)
                return (gap_left_edge, best['w'])
            
            return None
            
        except Exception as ex:
            self.logger.error(f"Ошибка анализа puzzle: {ex}")
            return None
    
    def solve_slider_captcha(self) -> bool:
        """Решает DataDome/GeeTest капчу - ОРИГИНАЛЬНЫЙ метод из GitHub
        
        ЛОГИКА (https://github.com/glizzykingdreko/Datadome-GeeTest-Captcha-Solver):
        ==============================================================================
        1. Получаем два canvas из капчи:
           - Canvas #1: Фоновое изображение с вырезом
           - Canvas #2: Кусочек паззла (overlay поверх Canvas #1)
        
        2. Template Matching (Canny 100,200):
           - Применяем Canny edge detection к обоим canvas
           - cv2.matchTemplate находит где кусочек совпадает с фоном
           - Вычисляем ЦЕНТР найденной позиции: center_x = max_loc[0] + width/2
           - Это УНИВЕРСАЛЬНОЕ решение - работает для ЛЮБОЙ позиции выреза!
        
        3. Позиция слайдера:
           - Слайдер двигается на позицию center_x (ЦЕНТР кусочка)
           - Это позиция из их кода - БЕЗ дополнительных формул!
        
        4. Движение:
           - offset = center_x - current_position
           - ActionChains с плавным движением (НЕ МЕНЯЕМ - работает!)
        
        5. Fallback (если нет Canvas #2):
           - Используем метод контуров на Canvas #1
           - Формула: left_edge + width/3.25 + 3
        
        Возвращает: True если капча решена успешно
        """
        try:
            print(f"🎯 Решаем капчу с помощью OpenCV template matching...")
            self._log_action("start_solving", {"method": "OpenCV template matching + human-like movement"})
            
            # Находим iframe с капчей
            iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
            captcha_iframe = None
            
            for iframe in iframes:
                try:
                    src = iframe.get_attribute('src') or ''
                    if 'captcha-delivery.com' in src and iframe.is_displayed():
                        captcha_iframe = iframe
                        self._log_action("iframe_found", {"src": src[:100]})
                        break
                except:
                    continue
            
            if not captcha_iframe:
                self._log_action("error", {"message": "iframe не найден"})
                return False
            
            # Переключаемся в iframe
            self.driver.switch_to.frame(captcha_iframe)
            self._log_action("switched_to_iframe")
            
            # Ждём загрузки капчи - ВАЖНО: нужно дождаться пока Canvas #2 получит style.left!
            print(f"⏳ Ожидаем полной загрузки капчи...")
            time.sleep(3)
            
            # Дополнительно ждем пока Canvas #2 (кусочек) получит позицию
            try:
                for attempt in range(10):
                    canvases_check = self.driver.find_elements(By.CSS_SELECTOR, "div#captcha__puzzle canvas")
                    if len(canvases_check) > 1:
                        block_style = canvases_check[1].get_attribute('style') or ''
                        if 'left' in block_style and 'left: 0px' not in block_style:
                            print(f"✅ Canvas #2 загружен с позицией: {block_style}")
                            break
                    time.sleep(0.5)
            except:
                pass
            

            
            # Ищем canvas с паззлом (из 111.html: div#captcha__puzzle > canvas)
            puzzle_canvas = None
            target_slider_position = None  # ЦЕЛЕВАЯ позиция для слайдера
            
            try:
                # Ищем div#captcha__puzzle
                puzzle_container = self.driver.find_element(By.CSS_SELECTOR, "div#captcha__puzzle")
                
                # Ищем все canvas внутри
                canvases = puzzle_container.find_elements(By.TAG_NAME, "canvas")
                self._log_action("canvas_elements_found", {"count": len(canvases)})
                
                # Берём первый canvas (основное изображение паззла)
                if len(canvases) > 0:
                    puzzle_canvas = canvases[0]
                    canvas_loc = puzzle_canvas.location
                    canvas_size = puzzle_canvas.size
                    self._log_action("canvas_background_found", {
                        "position": {"x": canvas_loc['x'], "y": canvas_loc['y']},
                        "size": {"width": canvas_size['width'], "height": canvas_size['height']}
                    })
                
                # Проверяем второй canvas (блок паззла с class="block")
                if len(canvases) > 1:
                    block_canvas = canvases[1]
                    block_loc = block_canvas.location
                    block_size = block_canvas.size
                    block_style = block_canvas.get_attribute('style') or ''
                    block_class = block_canvas.get_attribute('class') or ''
                    
                    # Пытаемся получить реальную позицию Canvas #2 через JavaScript
                    try:
                        # Получаем inline style.left если есть
                        inline_left = self.driver.execute_script("""
                            var elem = arguments[0];
                            var inlineStyle = elem.style.left;
                            var computedStyle = window.getComputedStyle(elem).left;
                            var rect = elem.getBoundingClientRect();
                            var parent = elem.parentElement.getBoundingClientRect();
                            var relativeLeft = rect.left - parent.left;
                            return {
                                inline_left: inlineStyle,
                                computed_left: computedStyle,
                                relative_left: relativeLeft
                            };
                        """, block_canvas)
                        
                        # Пытаемся спарсить left из inline style
                        if inline_left.get('inline_left'):
                            try:
                                parsed_left = int(inline_left['inline_left'].replace('px', ''))
                                target_slider_position = parsed_left
                                print(f"   ⭐ Canvas #2 inline style left={parsed_left}px")
                            except:
                                pass
                        
                        # Если не получилось из inline, используем relative position
                        if target_slider_position is None and inline_left.get('relative_left'):
                            rel_left = int(inline_left['relative_left'])
                            target_slider_position = rel_left
                            print(f"   ⭐ Canvas #2 relative left={rel_left}px")
                        
                        self._log_action("canvas_block_position_check", {
                            "inline_left": inline_left.get('inline_left', 'N/A'),
                            "computed_left": inline_left.get('computed_left', 'N/A'),
                            "relative_left": inline_left.get('relative_left', 0),
                            "target_slider_from_canvas": target_slider_position
                        })
                    except Exception as e:
                        self._log_action("error", {"message": f"Ошибка получения позиции Canvas #2: {e}"})
                    
                    # Парсим left из style
                    if target_slider_position is None and ('left:' in block_style or 'left :' in block_style):
                        try:
                            block_left = int(block_style.split('left')[1].split(':')[1].split('px')[0].strip())
                            target_slider_position = block_left
                            print(f"   ⭐ Canvas #2 style left={block_left}px")
                            self._log_action("canvas_block_has_left_style", {"left": block_left})
                        except:
                            pass
                            
            except Exception as e:
                self._log_action("error", {"message": f"Ошибка при поиске canvas: {e}"})
            
            # Анализируем canvas с паззлом - используем TEMPLATE MATCHING!
            gap_x = None
            gap_width = None
            used_template_matching = False  # Флаг какой метод использовался
            
            if puzzle_canvas:
                try:
                    # Canvas #1 - получаем через JavaScript (toDataURL сохраняет как есть)
                    bg_data_url = self.driver.execute_script("return arguments[0].toDataURL('image/png');", puzzle_canvas)
                    bg_data = bg_data_url.split(',')[1]  # Убираем "data:image/png;base64,"
                    bg_bytes = base64.b64decode(bg_data)
                    bg_image = Image.open(BytesIO(bg_bytes))
                    bg_image.save(os.path.join(self.screenshots_dir, "canvas_background.png"))
                    
                    # Canvas #2 - получаем через JavaScript с АЛЬФА-КАНАЛОМ!
                    piece_image = None
                    if len(canvases) > 1:
                        piece_data_url = self.driver.execute_script("return arguments[0].toDataURL('image/png');", canvases[1])
                        piece_data = piece_data_url.split(',')[1]
                        piece_bytes = base64.b64decode(piece_data)
                        piece_full = Image.open(BytesIO(piece_bytes))
                        piece_full.save(os.path.join(self.screenshots_dir, "canvas_piece_full.png"))
                        
                        # Вырезаем НЕПРОЗРАЧНУЮ часть (настоящий кусочек паззла!)
                        piece_array = np.array(piece_full.convert('RGBA'))
                        
                        if piece_array.shape[2] == 4:
                            # Есть альфа канал - вырезаем непрозрачные пиксели
                            alpha = piece_array[:,:,3]
                            non_transparent = alpha > 10
                            
                            rows = np.any(non_transparent, axis=1)
                            cols = np.any(non_transparent, axis=0)
                            
                            if rows.any() and cols.any():
                                y_min, y_max = np.where(rows)[0][[0, -1]]
                                x_min, x_max = np.where(cols)[0][[0, -1]]
                                
                                # Вырезаем НАСТОЯЩИЙ кусочек!
                                piece_image = piece_full.crop((x_min, y_min, x_max + 1, y_max + 1))
                                piece_image.save(os.path.join(self.screenshots_dir, "canvas_piece.png"))
                                print(f"   ✅ Вырезали кусочек: {piece_image.width}x{piece_image.height}px из {piece_full.width}x{piece_full.height}px")
                            else:
                                print(f"   ⚠️  Альфа-канал пустой, используем полный canvas")
                                piece_image = piece_full
                        else:
                            print(f"   ⚠️  Нет альфа-канала в PNG")
                            piece_image = piece_full
                        
                        if piece_image:
                            self._log_action("both_canvas_saved", {
                                "background": "canvas_background.png",
                                "piece": "canvas_piece.png",
                                "piece_size": {"width": piece_image.width, "height": piece_image.height}
                            })
                    
                    # Анализируем с помощью template matching (метод из GitHub)
                    if piece_image:
                        print(f"🎯 Используем TEMPLATE MATCHING (метод из GitHub)")
                        used_template_matching = True
                    gap_result = self.detect_puzzle_gap(bg_image, piece_image)
                    
                    if gap_result is not None:
                        gap_x, gap_width = gap_result
                        method = "template_matching" if piece_image else "contours"
                        
                        if piece_image:
                            # Template matching возвращает ЦЕНТР кусочка
                            print(f"✅ Gap найден методом {method}: ЦЕНТР кусочка={gap_x}px, ширина={gap_width}px")
                            self._log_action("gap_detected", {
                                "center_x": gap_x,
                                "width": gap_width,
                                "method": method
                            })
                        else:
                            # Контуры возвращают левый край
                            print(f"✅ Gap найден методом {method}: левый край={gap_x}px, ширина={gap_width}px")
                            self._log_action("gap_detected", {
                                "left_edge_x": gap_x,
                                "width": gap_width,
                                "method": method
                            })
                    else:
                        gap_x, gap_width = None, None
                    
                except Exception as e:
                    self._log_action("error", {"message": f"Ошибка анализа canvas: {e}"})
            
            # Если не получилось с canvas, пробуем скриншот iframe
            if gap_x is None:
                self._log_action("fallback_to_iframe_screenshot")
                iframe_screenshot = self.driver.get_screenshot_as_png()
                iframe_image = Image.open(BytesIO(iframe_screenshot))
                iframe_image.save(os.path.join(self.screenshots_dir, "captcha_iframe.png"))
                gap_result = self.detect_puzzle_gap(iframe_image)
                if gap_result:
                    gap_x, gap_width = gap_result
                else:
                    gap_x, gap_width = None, None
            
            if gap_x is None:
                self._log_action("error", {"message": "Не удалось определить позицию выреза"})
                self.driver.switch_to.default_content()
                return False
            
            # Определяем целевую позицию для слайдера
            if target_slider_position is not None:
                # Используем позицию Canvas #2 если получилось извлечь
                # Попробуем БЕЗ +20px - может быть это уже правильная позиция
                final_target = target_slider_position
                print(f"   Canvas #2 position: {target_slider_position}px → Slider target = {final_target}px")
            elif used_template_matching:
                # МЕТОД GITHUB: Template matching возвращает ЦЕНТР кусочка
                # Это и есть целевая позиция для слайдера - БЕЗ формул!
                final_target = gap_x
                print(f"   Template matching (GitHub): ЦЕНТР кусочка = {gap_x}px → Слайдер НА {final_target}px")
            else:
                # Метод контуров: возвращает левый край, применяем формулу
                final_target = gap_x + int(gap_width / 3.25) + 3
                print(f"   Контуры: левый край={gap_x}px → Слайдер на {final_target}px")
            
            # Находим слайдер - ищем ТОЧНО элемент div.slider
            slider = None
            try:
                slider = self.driver.find_element(By.CSS_SELECTOR, "div.slider")
                
                if slider.is_displayed():
                    slider_class = slider.get_attribute('class')
                    slider_style = slider.get_attribute('style')
                    slider_size = slider.size
                    slider_loc = slider.location
                    
                    self._log_action("slider_found", {
                        "class": slider_class,
                        "style": slider_style,
                        "size": {"width": slider_size['width'], "height": slider_size['height']},
                        "position": {"x": slider_loc['x'], "y": slider_loc['y']}
                    })
                else:
                    slider = None
            except Exception as e:
                self._log_action("error", {"message": f"Слайдер не найден: {e}"})
            
            if not slider:
                self._log_action("error", {"message": "Не удалось найти элемент слайдера"})
                self.driver.switch_to.default_content()
                return False
            
            # Получаем текущую позицию слайдера из style
            current_left = 0
            style = slider.get_attribute('style') or ''
            if 'left:' in style:
                try:
                    left_str = style.split('left:')[1].split('px')[0].strip()
                    current_left = int(left_str)
                except:
                    pass
            
            # Рассчитываем смещение (сколько пикселей нужно сдвинуть)
            offset = final_target - current_left
            
            print(f"\n{'='*60}")
            print(f"📊 РАСЧЁТ ДВИЖЕНИЯ СЛАЙДЕРА:")
            print(f"   Текущая позиция слайдера: {current_left}px")
            print(f"   Целевая позиция: {final_target}px")
            print(f"   Требуется сдвинуть: {offset}px")
            print(f"{'='*60}\n")
            
            # Логируем расчёт движения
            method_name = "template_matching" if used_template_matching else "contours"
            self._log_action("calculate_movement", {
                "gap_position": gap_x,
                "method": method_name,
                "target_position": final_target,
                "current_position": current_left,
                "offset": offset,
                "direction": "right" if offset > 0 else "left"
            })
            
            # Движение слайдера с имитацией человеческого поведения
            # ВОЗВРАЩАЕМ РАБОЧИЙ МЕТОД ActionChains!
            success = False
            
            try:
                self._log_action("try_method_1", {"method": "ActionChains drag_and_drop_by_offset", "offset": offset})
                actions = ActionChains(self.driver)
                actions.click_and_hold(slider).pause(0.2)
                
                # Двигаем в несколько этапов для имитации человека
                steps = 15
                for i in range(steps):
                    step_offset = offset / steps
                    step_offset += random.uniform(-0.5, 0.5)
                    actions.move_by_offset(step_offset, 0)
                    actions.pause(random.uniform(0.02, 0.05))
                
                actions.release().perform()
                time.sleep(1)
                self._log_action("method_1_success")
                success = True
            except Exception as e:
                self._log_action("method_1_failed", {"error": str(e)})
            try:
                # Ищем контейнер капчи внутри iframe
                screenshot_path = os.path.join(self.screenshots_dir, "captcha_after_move.png")
                
                # Пробуем найти puzzle контейнер и сделать его скриншот
                try:
                    puzzle_container = self.driver.find_element(By.CSS_SELECTOR, "div#captcha__puzzle")
                    puzzle_container.screenshot(screenshot_path)
                except:
                    # Если не получилось, пробуем найти главный контейнер капчи
                    try:
                        main_container = self.driver.find_element(By.CSS_SELECTOR, "div.main__container")
                        main_container.screenshot(screenshot_path)
                    except:
                        # В крайнем случае делаем скриншот body внутри iframe
                        body = self.driver.find_element(By.TAG_NAME, "body")
                        body.screenshot(screenshot_path)
                
                print(f"📸 Скриншот капчи после движения: {screenshot_path}")
                
                # Проверяем текущую позицию слайдера
                current_style = slider.get_attribute('style') or ''
                if 'left:' in current_style:
                    try:
                        current_pos = int(current_style.split('left:')[1].split('px')[0].strip())
                        diff = abs(current_pos - final_target)
                        self._log_action("slider_final_position", {
                            "current_pos": current_pos,
                            "target_pos": final_target,
                            "difference": diff,
                            "success": diff <= 5
                        })
                    except:
                        pass
            except Exception as e:
                self._log_action("error", {"message": f"Не удалось сохранить скриншот: {e}"})
            
            # Сохраняем лог действий
            self._save_log()
            
            # ПАУЗА чтобы пользователь успел выключить скрипт и посмотреть результат
            print(f"\n{'='*60}")
            print(f"⏸️  ПАУЗА 10 СЕКУНД для проверки результата")
            print(f"   Откройте: {self.screenshots_dir}/captcha_after_move.png")
            print(f"   Лог действий: {self.screenshots_dir}/captcha_actions.json")
            print(f"   Нажмите Ctrl+C если хотите остановить скрипт")
            print(f"{'='*60}\n")
            time.sleep(10)
            
            time.sleep(1)
            
            # Возвращаемся в основной контекст
            self.driver.switch_to.default_content()
            
            # Проверяем результат
            time.sleep(1)
            has_captcha, _ = self.check_captcha()
            
            if not has_captcha:
                print(f"🎉 Капча решена!")
                self._log_action("captcha_solved", {"success": True})
                self._save_log()
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
