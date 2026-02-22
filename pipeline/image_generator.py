# -*- coding: utf-8 -*-
import requests
import json
import time
import logging
import sys
import os
from pathlib import Path
from typing import Optional

# --- Отключаем предупреждения об SSL ---
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# -----------------------------------------------

class ImageGenerator:
    """
    Класс-модуль для работы с API генерации изображений.
    """
    
    def __init__(self, base_url: str, api_key: str, logger: Optional[logging.Logger] = None):
        if not api_key or not api_key.strip():
            raise ValueError("API-ключ для ImageGenerator не предоставлен.")
            
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger("ImageGen")
            if not self.logger.hasHandlers():
                self.logger.setLevel(logging.INFO)
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(logging.Formatter('%(asctime)s - (IMG) - %(message)s'))
                self.logger.addHandler(console_handler)
        
        self.create_url = f"{self.base_url}/create"
        self.result_base_url = f"{self.base_url}/tasks" 
        # Настройки опроса
        self.POLL_INTERVAL = 4 
        self.POLL_TIMEOUT = 300 # 5 минут максимум на одну картинку

    def generate_image(self, prompt: str, aspect_ratio: str, output_path: str) -> bool:
        """
        Генерирует изображение и сохраняет его по указанному пути.
        """
        max_retries = 2
        
        headers = {
            "X-API-Key": self.api_key, 
            "Content-Type": "application/json"
        }
        
        payload = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "version": "latest"
        }
        
        output_path_obj = Path(output_path)
        output_filename = output_path_obj.name
        
        for attempt in range(max_retries):
            try:
                # --- Шаг 1: Создание задачи ---
                self.logger.info(f"Запрос на генерацию изображения: {output_filename}")
                
                # В image_generator.py из примера URL: /api/v1/image/create
                # В eleven_bot_module.py URL: https://voiceapiru.csv666.ru/tasks
                # Проверим, какой URL правильный для картинок.
                # Пользователь сказал: "Волт тут есть генерация картинок, ключ используется тот же, что и у генерации звука (один сервис)"
                # И "Только посмотри, BASE_URL немного изменился (у нас в генерации звука другой домен)"
                # Значит, нужно уточнить URL. В примере D:\Softs\SuperVideoWriting\SuperVideoWriting\api\image_generator.py
                # URL: /api/v1/image/create
                # BASE_URL нужно будет передать правильный.
                
                post_response = requests.post(
                    self.create_url, 
                    headers=headers, 
                    json=payload,
                    timeout=30,
                    verify=False
                )

                if post_response.status_code != 200 and post_response.status_code != 201:
                    self.logger.error(f"Ошибка API (Create): {post_response.status_code} - {post_response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return False

                task_data = post_response.json()
                task_id = task_data.get("task_id")
                
                if not task_id:
                    self.logger.error(f"API не вернуло task_id: {task_data}")
                    return False

                self.logger.info(f"Задача создана: {task_id}. Ожидание результата...")

                # --- Шаг 2: Опрос (Polling) результата ---
                # В примере: /api/v1/image/tasks/{id}/result?as_file=true
                result_url = f"{self.result_base_url}/{task_id}/result"
                
                start_time = time.time()
                while True:
                    if time.time() - start_time > self.POLL_TIMEOUT:
                        self.logger.error(f"Таймаут генерации задачи {task_id}")
                        return False

                    try:
                        get_response = requests.get(
                            result_url, 
                            headers={"X-API-Key": self.api_key}, 
                            params={"as_file": "true"},
                            timeout=60, 
                            verify=False
                        )
                    except Exception as e:
                        self.logger.warning(f"Ошибка при опросе: {e}")
                        time.sleep(self.POLL_INTERVAL)
                        continue

                    if get_response.status_code == 200:
                        # УСПЕХ: Мы получили бинарный файл
                        output_path_obj.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path_obj, "wb") as f:
                            f.write(get_response.content)
                        self.logger.info(f"✅ Изображение сохранено: {output_filename}")
                        return True
                    
                    elif get_response.status_code == 202:
                        # Задача еще в процессе
                        time.sleep(self.POLL_INTERVAL)
                    
                    elif get_response.status_code in [404, 500, 401]:
                        self.logger.error(f"Ошибка опроса {task_id}: {get_response.status_code} - {get_response.text}")
                        return False
                    else:
                        time.sleep(self.POLL_INTERVAL)

            except Exception as e:
                self.logger.error(f"Исключение в ImageGenerator: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    return False
                
        return False

