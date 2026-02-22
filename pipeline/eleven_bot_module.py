# -*- coding: utf-8 -*-
import requests
import json
import time
import logging
import sys
import os # Добавил импорт os
from typing import Optional

import socket

# Глобальный таймаут для сокетов
socket.setdefaulttimeout(60)

# --- Отключаем предупреждения об SSL ---
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# -----------------------------------------------

class VoiceSynthesizer:
    """
    Класс-модуль для инкапсуляции работы с АСИНХРОННЫМ API бота озвучки.
    """
    
    # --- Константы API ---
    BASE_URL = "https://voiceapiru.csv666.ru"
    BALANCE_URL = f"{BASE_URL}/balance"
    TASKS_URL = f"{BASE_URL}/tasks"
    
    # --- Константы запросов ---
    REQUEST_TIMEOUT = 60  # Увеличил до 60 сек
    DOWNLOAD_TIMEOUT = 120
    POLL_INTERVAL = 2  # Интервал опроса (секунды)
    POLL_TIMEOUT = 300 # Макс. время ожидания задачи (секунды) - увеличил до 5 мин

    def __init__(self, api_key: str, logger: Optional[logging.Logger] = None):
        """
        Инициализирует синтезатор с API-ключом.
        """
        if not api_key:
            raise ValueError("API-ключ для VoiceSynthesizer не предоставлен.")
            
        self.api_key = api_key
        
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger("VoiceSynthesizerFallback")
            if not self.logger.hasHandlers():
                self.logger.setLevel(logging.INFO)
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(logging.Formatter('%(asctime)s - (VCS Fallback) - %(message)s'))
                self.logger.addHandler(console_handler)
        
        self.logger.info("Модуль VoiceSynthesizer инициализирован.")

    def synthesize(self, text: str, template_uuid: str, output_path: str) -> bool:
        """
        Синтезирует аудио и сохраняет его в файл.
        Возвращает True в случае успеха, False в случае ошибки.
        """
        max_retries = 3
        
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": text,
            "template_uuid": template_uuid
        }
        
        output_filename = os.path.basename(str(output_path))
        
        for attempt in range(max_retries):
            try:
                # --- Шаг 1: Создание задачи ---
                self.logger.debug(f"Попытка {attempt + 1}: POST /tasks для файла {output_filename}")
                post_response = requests.post(
                    self.TASKS_URL, 
                    headers=headers, 
                    data=json.dumps(payload),
                    timeout=self.REQUEST_TIMEOUT,
                    verify=False
                )

                if post_response.status_code != 200 and post_response.status_code != 201:
                    self.logger.error(f"Ошибка API (HTTP {post_response.status_code}): {post_response.text}")
                    return False

                # --- Успешное создание задачи ---
                task_id = post_response.json().get("task_id")
                if not task_id:
                    self.logger.error(f"API не вернуло 'task_id': {post_response.json()}")
                    return False

                self.logger.debug(f"Попытка {attempt + 1}: Задача {task_id} создана. Начинаю опрос.")

                # --- Шаг 2: Опрос (Polling) результата ---
                result_url = f"{self.TASKS_URL}/{task_id}/result"
                start_time = time.time()

                while True:
                    if time.time() - start_time > self.POLL_TIMEOUT:
                        self.logger.error(f"Таймаут ожидания задачи {task_id}")
                        return False

                    get_headers = {"X-API-Key": self.api_key}
                    
                    get_response = requests.get(
                        result_url, 
                        headers=get_headers, 
                        timeout=self.DOWNLOAD_TIMEOUT, 
                        verify=False
                    )

                    if get_response.status_code == 200:
                        # --- УСПЕХ! ---
                        with open(output_path, "wb") as f:
                            f.write(get_response.content)
                        return True 
                    
                    elif get_response.status_code == 202:
                        # --- ЕЩЕ НЕ ГОТОВО ---
                        time.sleep(self.POLL_INTERVAL)
                    
                    else:
                        self.logger.error(f"HTTP {get_response.status_code} при опросе задачи {task_id}: {get_response.text}")
                        return False

            except Exception as e:
                self.logger.warning(f"Ошибка (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return False
        return False
