import time
import random
import json
import logging
from pathlib import Path
from typing import Optional
from enum import Enum, auto
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Импортируем из текущего пакета
from utils import get_chrome_executable_path, should_disable_chrome_version_check, get_chrome_version_main

# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') # Убрал глобальную настройку
logger = logging.getLogger("AuthModule")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

LANGUAGE_KEYWORDS = [
    'Language', 'Bahasa', 'Язык', 'Sprache', 'Idioma', 'Langue', 'Linguagem',
    '言語', '語言', 'ภาษา', 'Dil', 'Lingua', 'Språk', 'Jazyk', 'Nyelv', 'Kieli', 'Cilt', 'Lenga'
]

class AuthStatus(Enum):
    SUCCESS = auto()
    FAILURE_BAD_PASSWORD = auto()
    FAILURE_RECOVERY_NEEDED = auto()
    FAILURE_UNEXPECTED = auto()

class GoogleAuth:
    def __init__(
        self,
        email: str,
        password: str,
        profile_path: str,
        cookie_path: str,
        recovery_email: Optional[str] = None,
        proxy: Optional[str] = None,
        user_agent: Optional[str] = None
    ):
        self.email = email
        self.password = password
        self.recovery_email = recovery_email
        self.profile_path = Path(profile_path)
        self.cookie_path = Path(cookie_path)
        self.proxy = proxy
        self.user_agent = user_agent
        self.timeout = 20
        self.driver = None

    def _create_proxy_extension(self) -> Optional[str]:
        if not self.proxy or 'http' not in self.proxy:
            return None

        logging.info("Создание расширения для прокси...")
        try:
            proxy_parts = self.proxy.replace("http://", "").split(":")
            user, password = proxy_parts[0], proxy_parts[1].split("@")[0]
            host, port = proxy_parts[1].split("@")[1], proxy_parts[2]
        except Exception as e:
            logger.error(f"Ошибка парсинга прокси: {e}")
            return None

        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Chrome Proxy",
            "permissions": ["proxy", "tabs", "unlimitedStorage", "storage", "<all_urls>", "webRequest", "webRequestBlocking"],
            "background": { "scripts": ["background.js"] },
            "minimum_chrome_version":"22.0.0"
        }
        """
        background_js = f"""
        var config = {{
                mode: "fixed_servers",
                rules: {{
                  singleProxy: {{
                    scheme: "http",
                    host: "{host}",
                    port: parseInt({port})
                  }},
                  bypassList: ["localhost"]
                }}
              }};
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        function callbackFn(details) {{
            return {{
                authCredentials: {{
                    username: "{user}",
                    password: "{password}"
                }}
            }};
        }}
        chrome.webRequest.onAuthRequired.addListener(
                    callbackFn,
                    {{urls: ["<all_urls>"]}},
                    ['blocking']
        );
        """
        
        plugin_dir = self.profile_path / "proxy_plugin"
        plugin_dir.mkdir(exist_ok=True, parents=True)
        
        with open(plugin_dir / "manifest.json", "w") as f:
            f.write(manifest_json)
        with open(plugin_dir / "background.js", "w") as f:
            f.write(background_js)
            
        return str(plugin_dir.resolve())

    def _setup_driver(self):
        logging.info("Настройка Chrome драйвера...")
        chrome_path = get_chrome_executable_path()
        disable_version_check = should_disable_chrome_version_check()
        
        options = uc.ChromeOptions()
        # Создаем папку профиля, если её нет
        self.profile_path.mkdir(parents=True, exist_ok=True)
        options.add_argument(f'--user-data-dir={str(self.profile_path.resolve())}')
        
        if self.user_agent:
            options.add_argument(f'--user-agent={self.user_agent}')

        proxy_plugin_path = self._create_proxy_extension()
        if proxy_plugin_path:
            # Для плагина прокси
            options.add_argument(f'--load-extension={proxy_plugin_path}')
        elif self.proxy and 'http' not in self.proxy:
            # Простой прокси без пароля
            options.add_argument(f'--proxy-server={self.proxy}')

        driver_kwargs = {
            'options': options,
            'browser_executable_path': chrome_path
        }
        
        if disable_version_check:
            forced_version = get_chrome_version_main()
            if forced_version:
                 driver_kwargs['version_main'] = forced_version
            else:
                 driver_kwargs['version_main'] = None
        
        self.driver = uc.Chrome(**driver_kwargs)
        self.wait = WebDriverWait(self.driver, self.timeout)

    def _save_cookies(self):
        logging.info("Сохранение cookies...")
        self.cookie_path.parent.mkdir(exist_ok=True, parents=True)
        try:
            all_cookies_data = self.driver.execute_cdp_cmd("Network.getAllCookies", {})
            with open(self.cookie_path, "w", encoding="utf-8") as f:
                json.dump(all_cookies_data['cookies'], f, indent=2)
            logging.info(f"✅ Куки сохранены в {self.cookie_path}")
        except Exception as e:
            logging.error(f"Ошибка сохранения куки: {e}")

    def _handle_recovery(self) -> bool:
        if not self.recovery_email:
            logging.error("Требуется подтверждение, но резервная почта не предоставлена.")
            return False
            
        try:
            logging.info("Обнаружен запрос на подтверждение. Пытаюсь использовать резервную почту...")
            recovery_option_xpath = "//*[contains(text(), 'Подтвердите резервный адрес') or contains(text(), 'Confirm your recovery email')]"
            self.wait.until(EC.element_to_be_clickable((By.XPATH, recovery_option_xpath))).click()
            
            email_input_id = "knowledge-preregistered-email-response"
            email_field = self.wait.until(EC.visibility_of_element_located((By.ID, email_input_id)))
            email_field.send_keys(self.recovery_email)
            
            next_button_xpath = "//button[contains(., 'Далее') or contains(., 'Next')]"
            self.wait.until(EC.element_to_be_clickable((By.XPATH, next_button_xpath))).click()
            
            logging.info("Резервная почта успешно введена.")
            return True
        except TimeoutException:
            logging.error("Не удалось найти элементы для подтверждения через резервную почту.")
            return False

    def login(self) -> AuthStatus:
        try:
            self._setup_driver()
            self.driver.get("https://accounts.google.com/signin")
            time.sleep(3)

            if "myaccount.google.com" in self.driver.current_url:
                logging.info("✅ Обнаружена активная сессия. Вход выполнен.")
                self._save_cookies()
                return AuthStatus.SUCCESS

            try:
                email_input = self.wait.until(EC.visibility_of_element_located((By.ID, "identifierId")))
                email_input.send_keys(self.email)
                self.driver.find_element(By.ID, "identifierNext").click()
            except TimeoutException:
                # Возможно уже введен email
                pass
            
            try:
                password_input = self.wait.until(EC.visibility_of_element_located((By.NAME, "Passwd")))
                password_input.send_keys(self.password)
                self.driver.find_element(By.ID, "passwordNext").click()
            except TimeoutException:
                logging.error("Не удалось найти поле пароля")
                return AuthStatus.FAILURE_UNEXPECTED

            time.sleep(5)

            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()

            if "myaccount.google.com" in current_url or "youtube.com" in current_url:
                logging.info("✅ Успешная авторизация (прямой вход).")
                self._save_cookies()
                return AuthStatus.SUCCESS
            
            if "wrong password" in page_source or "неверный пароль" in page_source:
                return AuthStatus.FAILURE_BAD_PASSWORD

            if "verify it's you" in page_source or "подтвердите, что это вы" in page_source:
                if self._handle_recovery():
                    time.sleep(5)
                    if "myaccount.google.com" in self.driver.current_url:
                        self._save_cookies()
                        return AuthStatus.SUCCESS
                return AuthStatus.FAILURE_RECOVERY_NEEDED

            return AuthStatus.FAILURE_UNEXPECTED

        except Exception as e:
            logging.error(f"Ошибка авторизации: {e}", exc_info=True)
            return AuthStatus.FAILURE_UNEXPECTED
        finally:
            if self.driver:
                self.driver.quit()

    def change_language(self, language_name: str) -> bool:
        try:
            self._setup_driver()
            logging.info(f"Попытка сменить язык на '{language_name}'...")
            self.driver.get("https://www.youtube.com/")
            time.sleep(3)

            # 1. Аватар
            avatar_selectors = ['ytd-masthead button#avatar-btn', 'button#avatar-btn']
            avatar_element = None
            for selector in avatar_selectors:
                try:
                    avatar_element = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    if avatar_element: break
                except: continue
            
            if not avatar_element:
                logging.error("Не удалось найти аватар")
                return False
            avatar_element.click()
            time.sleep(2)

            # 2. Меню 'Язык'
            language_menu_element = None
            for keyword in LANGUAGE_KEYWORDS:
                xpath = f"//tp-yt-paper-item[.//yt-formatted-string[contains(text(), '{keyword.lower()}')]]"
                try:
                    language_menu_element = WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                    if language_menu_element: break
                except: continue
            
            if not language_menu_element:
                logging.error("Не удалось найти пункт 'Язык'")
                return False
            language_menu_element.click()
            time.sleep(2)

            # 3. Выбор языка
            target_language_xpath = f"//tp-yt-paper-item[.//yt-formatted-string[text()='{language_name}']]"
            try:
                target_language_element = self.wait.until(EC.element_to_be_clickable((By.XPATH, target_language_xpath)))
                target_language_element.click()
                time.sleep(3)
                logging.info(f"✅ Язык изменен на '{language_name}'")
                return True
            except:
                logging.error(f"Не удалось найти язык '{language_name}'")
                return False

        except Exception as e:
            logging.error(f"Ошибка смены языка: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()

