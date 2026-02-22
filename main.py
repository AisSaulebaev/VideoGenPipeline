import threading
import time
import os
import sys
import uvicorn
import logging
from pathlib import Path

# Добавляем текущую директорию в sys.path для автономной работы
BASE_DIR = Path(__file__).parent.absolute()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ФИКС КОДИРОВКИ ДЛЯ WINDOWS КОНСОЛИ (безопасный способ)
if sys.platform.startswith('win'):
    try:
        os.system('chcp 65001 > nul')
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Относительные импорты (работают из папки VideoGenPipeline)
from database import init_db, SessionLocal, Settings, Task
from workers.scanner import run_scanner_worker
from workers.voicer import run_voicer_worker
from workers.video_maker import run_video_maker_worker
from workers.asset_worker import run_asset_worker
from workers.uploader import run_uploader_worker
from workers.metadata_worker import run_metadata_worker
from web.server import app

def reset_state_on_startup():
    print("Resetting system state...")
    db = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings:
            settings = Settings()
            db.add(settings)
        
        settings.scanner_active = False
        settings.voicer_active = False
        settings.video_maker_active = False
        settings.asset_manager_active = False
        settings.uploader_active = False
        settings.metadata_worker_active = False
        
        stuck_voicing = db.query(Task).filter(Task.status == "voicing").all()
        for t in stuck_voicing:
            print(f"  Resetting stuck task {t.id}: voicing -> pending_voice")
            t.status = "pending_voice"
            
        stuck_merging = db.query(Task).filter(Task.status == "merging").all()
        for t in stuck_merging:
            print(f"  Resetting stuck task {t.id}: merging -> pending_merge")
            t.status = "pending_merge"
            
        stuck_metadata = db.query(Task).filter(Task.status == "generating_metadata").all()
        for t in stuck_metadata:
            print(f"  Resetting stuck task {t.id}: generating_metadata -> pending_metadata")
            t.status = "pending_metadata"

        stuck_uploading = db.query(Task).filter(Task.status == "uploading").all()
        for t in stuck_uploading:
            print(f"  Resetting stuck task {t.id}: uploading -> pending_upload")
            t.status = "pending_upload"
        
        db.commit()
        print("System state reset complete.")
    except Exception as e:
        print(f"Error resetting system state: {e}")
    finally:
        db.close()

def start_worker_threads():
    workers = [
        ("Scanner", run_scanner_worker),
        ("Voicer", run_voicer_worker),
        ("VideoMaker", run_video_maker_worker),
        ("AssetWorker", run_asset_worker),
        ("Metadata", run_metadata_worker),
        ("Uploader", run_uploader_worker)
    ]

    for name, target in workers:
        t = threading.Thread(target=target, daemon=True)
        t.start()
        print(f"{name} worker thread started.")

def run_server():
    """Запуск uvicorn в отдельном потоке"""
    import logging
    # Отключаем access логи (спам от веб-сервера)
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn.access": {
                "handlers": [],
                "level": "WARNING",
                "propagate": False,
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["default"],
        },
    }
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=log_config)

def main():
    print("Initializing Database...")
    init_db()
    
    reset_state_on_startup()

    print("Starting Worker Threads...")
    start_worker_threads()

    print("Starting Web Server at http://127.0.0.1:8000")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    print("System is running. Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        os._exit(0)

if __name__ == "__main__":
    main()
