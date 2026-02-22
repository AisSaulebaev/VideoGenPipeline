import os
import time
import logging
import base64
import requests
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import BASE_DIR, CHROME_EXECUTABLE_PATH, CHROME_VERSION_MAIN

logger = logging.getLogger("SeleniumGen")

# Глобальный экземпляр драйвера, чтобы не закрывался
_global_driver = None

class SeleniumImageGenerator:
    def __init__(self):
        self.download_dir = str(BASE_DIR / "temp_downloads")
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
            
        self.profile_path = str(BASE_DIR / "profiles" / "image_gen")
        if not os.path.exists(self.profile_path):
            os.makedirs(self.profile_path)

    def _get_driver(self):
        """Возвращает существующий драйвер или создает новый"""
        global _global_driver
        
        # Проверяем, жив ли драйвер
        if _global_driver:
            try:
                _global_driver.current_url # Проверка жизни
                return _global_driver
            except:
                logger.warning("Драйвер был закрыт, пересоздаем...")
                _global_driver = None

        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={self.profile_path}")
        options.add_argument("--no-first-run")
        
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)

        logger.info("Запуск браузера (долгоживущая сессия)...")
        _global_driver = uc.Chrome(
            options=options, 
            browser_executable_path=CHROME_EXECUTABLE_PATH,
            version_main=CHROME_VERSION_MAIN
        )
        return _global_driver

    def generate_image(self, prompt: str, output_path: str) -> bool:
        """
        Использует открытый браузер. Ждет пока пользователь нажмет Launch (по появлению #prompt).
        """
        driver = self._get_driver()
        
        target_url = "https://aistudio.google.com/apps/6551fd22-6617-4b82-9d01-cf82d6c19095?showAssistant=true&showPreview=true"
        
        try:
            # Проверяем URL, если не тот - переходим
            if target_url not in driver.current_url:
                logger.info(f"Переход на {target_url}")
                driver.get(target_url)
            
            # --- ОЖИДАНИЕ ПРИЛОЖЕНИЯ ---
            logger.info("="*50)
            logger.info("Ждем появления поля ввода #prompt...")
            logger.info("ПОЖАЛУЙСТА, НАЖМИТЕ 'LAUNCH' ИЛИ АКТИВИРУЙТЕ ПРИЛОЖЕНИЕ В БРАУЗЕРЕ!")
            logger.info("="*50)
            
            # Пытаемся найти поле ввода в цикле (с поддержкой iframe)
            # Ждем долго (например 5 минут), пока пользователь нажмет
            input_box = None
            max_wait = 300 # 5 минут на ручной запуск
            start_wait = time.time()
            
            while time.time() - start_wait < max_wait:
                try:
                    # 1. Проверяем в текущем контексте
                    try:
                        input_box = driver.find_element(By.CSS_SELECTOR, "#prompt")
                        if input_box:
                            logger.info("Поле #prompt найдено!")
                            break
                    except:
                        pass
                    
                    # 2. Проверяем iframes
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for frame in iframes:
                        try:
                            driver.switch_to.frame(frame)
                            if len(driver.find_elements(By.CSS_SELECTOR, "#prompt")) > 0:
                                input_box = driver.find_element(By.CSS_SELECTOR, "#prompt")
                                logger.info("Поле #prompt найдено в iframe!")
                                break
                            driver.switch_to.default_content()
                        except:
                            driver.switch_to.default_content()
                    
                    if input_box:
                        break
                        
                    time.sleep(2)
                    
                except Exception as e:
                    pass
            
            if not input_box:
                logger.error("Таймаут ожидания ручного запуска приложения.")
                return False

            # --- ГЕНЕРАЦИЯ ---
            logger.info("Вводим промпт...")
            input_box.click()
            time.sleep(0.5)
            # Очистка JS-ом надежнее
            driver.execute_script("arguments[0].value = '';", input_box)
            input_box.send_keys(Keys.CONTROL + "a")
            input_box.send_keys(Keys.DELETE)
            time.sleep(0.5)
            
            input_box.send_keys(prompt)
            time.sleep(1)
            
            logger.info("Нажимаем кнопку генерации...")
            # Ищем кнопку рядом
            try:
                # Селектор из прошлых попыток
                btn_selector = "#root > div > main > div.w-full.max-w-2xl.mx-auto.mb-12 > div > form > div.flex.items-end > button"
                driver.find_element(By.CSS_SELECTOR, btn_selector).click()
            except:
                logger.warning("Кнопка не найдена, жмем Enter")
                input_box.send_keys(Keys.ENTER)
            
            logger.info("Ждем результат (60 сек)...")
            time.sleep(5)
            
            # --- ОЖИДАНИЕ КАРТИНКИ ---
            gallery_selector = "#root > div > main > div.animate-in.fade-in.slide-in-from-bottom-8.duration-700 > div.grid"
            
            # Ждем появления галереи
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, gallery_selector))
            )
            
            # Ждем обновления картинок (можно сравнить кол-во или просто подождать)
            time.sleep(5)
            
            images = driver.find_elements(By.CSS_SELECTOR, f"{gallery_selector} img")
            if images:
                # Берем первую (обычно новые в начале)
                target_img = images[0]
                src = target_img.get_attribute("src")
                logger.info(f"Найдена картинка: {src[:30]}...")
                
                if src.startswith("data:image"):
                    header, encoded = src.split(",", 1)
                    data = base64.b64decode(encoded)
                    with open(output_path, "wb") as f:
                        f.write(data)
                elif src.startswith("http"):
                    resp = requests.get(src)
                    if resp.status_code == 200:
                        with open(output_path, "wb") as f:
                            f.write(resp.content)
                
                logger.info(f"✅ Картинка сохранена: {output_path}")
                
                # Не закрываем драйвер!
                return True
            else:
                logger.error("Картинки не найдены.")
                return False

        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return False
