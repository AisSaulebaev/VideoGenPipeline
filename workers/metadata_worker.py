import time
from sqlalchemy.orm import Session
from database import SessionLocal, Task, Settings
from pipeline.ai_module import AIModule

def run_metadata_worker():
    print("MetadataWorker started (waiting for activation)...")
    
    # Инициализируем AI модуль один раз (он подгрузит ключ)
    try:
        ai_module = AIModule()
    except Exception as e:
        print(f"[Metadata] Failed to init AI Module: {e}")
        return

    last_inactive_message = 0

    while True:
        try:
            db: Session = SessionLocal()
            settings = db.query(Settings).first()

            if not settings or not settings.metadata_worker_active:
                current_time = time.time()
                if current_time - last_inactive_message >= 60:  # Раз в минуту
                    print("[Metadata] Inactive...")
                    last_inactive_message = current_time
                db.close()
                time.sleep(2)
                continue

            task = db.query(Task).filter(Task.status == "pending_metadata").first()
            
            if task:
                print(f"[Metadata] Processing task: {task.filename}")
                task.status = "generating_metadata"
                db.commit()
                
                try:
                    # Title уже есть из state_initial.json (scanner его загрузил)
                    # Генерируем только описание
                    print(f"[Metadata] Generating description...")
                    meta = ai_module.generate_metadata(task.content)
                    
                    if meta:
                        task.description = meta.get("description")
                        print(f"[Metadata] Description generated.")
                    else:
                        print(f"[Metadata] ⚠️ Failed to generate description.")

                    # Title должен быть
                    if not task.title:
                        task.title = task.filename

                    # Генерация картинки (ОБЯЗАТЕЛЬНО)
                    print(f"[Metadata] Generating thumbnail via Selenium...")
                    thumb_path = ai_module.generate_thumbnail(task.title, task.id)
                    
                    if thumb_path:
                        task.thumbnail_path = thumb_path
                        print(f"[Metadata] Thumbnail saved: {thumb_path}")
                        task.status = "pending_upload"
                        print(f"[Metadata] ✅ Task ready for upload.")
                    else:
                        print(f"[Metadata] ⚠️ Failed to generate thumbnail. Task NOT ready for upload.")
                        # Ставим статус ошибки, чтобы не грузить без картинки
                        task.status = "error" 
                        task.error_message = "Thumbnail generation failed (Selenium/Manual Timeout)"

                    db.commit()

                except Exception as e:
                    print(f"[Metadata] Error processing task: {e}")
                    task.status = "error"
                    task.error_message = f"Metadata Error: {str(e)}"
                    db.commit()
            
            db.close()
            time.sleep(2)

        except Exception as e:
            print(f"[Metadata] Critical error: {e}")
            time.sleep(5)
