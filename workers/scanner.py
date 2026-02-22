import os
import time
import shutil
import json
from sqlalchemy.orm import Session
from database import SessionLocal, Task, Settings
from config import BASE_DIR, SCENARIOS_SOURCE_DIR

# Папка для обработанных сценариев
DONE_SCENARIOS_DIR = os.path.join(BASE_DIR, "scenarios_processed")

def run_scanner_worker():
    """
    Воркер, который сканирует папку SCENARIOS_SOURCE_DIR на наличие новых папок со сценариями.
    В каждой папке должны быть:
    - full_story.txt - текст сценария
    - state_initial.json - метаданные (meta.title)
    """
    # Создаем папку для обработанных сценариев, если нет
    if not os.path.exists(DONE_SCENARIOS_DIR):
        os.makedirs(DONE_SCENARIOS_DIR)

    print("Scanner worker started (waiting for activation)...")
    
    last_inactive_message = 0
    
    while True:
        try:
            db: Session = SessionLocal()
            settings = db.query(Settings).first()
            
            if not settings or not settings.scanner_active:
                current_time = time.time()
                if current_time - last_inactive_message >= 60:  # Раз в минуту
                    print("[Scanner] Inactive (waiting for activation)...")
                    last_inactive_message = current_time
                db.close()
                time.sleep(2)
                continue
                
            # Если активен - сканируем
            if not os.path.exists(SCENARIOS_SOURCE_DIR):
                os.makedirs(SCENARIOS_SOURCE_DIR)
                print(f"[Scanner] Created source directory: {SCENARIOS_SOURCE_DIR}")
                db.close()
                time.sleep(5)
                continue
                
            # Получаем список папок (не файлов)
            scenario_folders = [
                f for f in os.listdir(SCENARIOS_SOURCE_DIR)
                if os.path.isdir(os.path.join(SCENARIOS_SOURCE_DIR, f))
            ]
            
            for folder_name in scenario_folders:
                scenario_path = os.path.join(SCENARIOS_SOURCE_DIR, folder_name)
                
                # Проверяем, есть ли уже такой сценарий в базе
                existing_task = db.query(Task).filter(Task.filename == folder_name).first()
                
                if existing_task:
                    print(f"[Scanner] Scenario '{folder_name}' already exists in DB. Skipping.")
                    continue
                
                # Проверяем наличие необходимых файлов
                story_file = os.path.join(scenario_path, "full_story.txt")
                state_file = os.path.join(scenario_path, "state_initial.json")
                
                if not os.path.exists(story_file):
                    print(f"[Scanner] Missing 'full_story.txt' in '{folder_name}'. Skipping.")
                    continue
                    
                if not os.path.exists(state_file):
                    print(f"[Scanner] Missing 'state_initial.json' in '{folder_name}'. Skipping.")
                    continue
                
                try:
                    # Читаем текст сценария
                    with open(story_file, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    
                    if not content:
                        print(f"[Scanner] 'full_story.txt' is empty in '{folder_name}'. Skipping.")
                        continue
                    
                    # Читаем метаданные
                    title = None
                    try:
                        with open(state_file, "r", encoding="utf-8") as f:
                            state_data = json.load(f)
                        
                        # Извлекаем title из meta.title
                        if isinstance(state_data, dict):
                            meta = state_data.get("meta", {})
                            if isinstance(meta, dict):
                                title = meta.get("title")
                    except Exception as e:
                        print(f"[Scanner] Warning: Could not read title from state_initial.json in '{folder_name}': {e}")
                    
                    # Создаем задачу
                    new_task = Task(
                        filename=folder_name,
                        content=content,
                        title=title,  # Сохраняем готовое название, если есть
                        status="pending_voice"
                    )
                    db.add(new_task)
                    db.commit()
                    print(f"[Scanner] ✅ Added new task: '{folder_name}'" + (f" (title: {title})" if title else ""))
                    
                    # Перемещаем папку в обработанные
                    dest_path = os.path.join(DONE_SCENARIOS_DIR, folder_name)
                    if os.path.exists(dest_path):
                        # Если уже есть - удаляем старую
                        shutil.rmtree(dest_path)
                    shutil.move(scenario_path, dest_path)
                    print(f"[Scanner] Moved '{folder_name}' to processed folder.")
                    
                except Exception as e:
                    print(f"[Scanner] Error processing scenario '{folder_name}': {e}")
            
            db.close()
            time.sleep(5) # Пауза между сканированиями
            
        except Exception as e:
            print(f"[Scanner] Critical error: {e}")
            time.sleep(5)

