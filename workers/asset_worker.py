import os
import time
import requests
import random
import subprocess
import shutil
from sqlalchemy.orm import Session
from database import SessionLocal, Settings, AssetHistory
from config import PIXABAY_API_KEY, ASSET_SEARCH_TAGS, MAX_ASSETS_COUNT, BASE_DIR

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
USED_ASSETS_DIR = os.path.join(BASE_DIR, "assets", "used")

def get_video_dimensions(filepath):
    """
    Возвращает (width, height) видео через ffprobe.
    """
    cmd = [
        "ffprobe", 
        "-v", "error", 
        "-select_streams", "v:0", 
        "-show_entries", "stream=width,height", 
        "-of", "csv=s=x:p=0", 
        filepath
    ]
    try:
        output = subprocess.check_output(cmd).decode("utf-8").strip()
        if output:
            w, h = map(int, output.split('x'))
            return w, h
    except Exception as e:
        print(f"[AssetWorker] Error checking dims: {e}")
    return 0, 0

def download_file(url, filepath, check_active_func=None):
    try:
        print(f"[AssetWorker] Downloading {os.path.basename(filepath)}...")
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    # Проверяем активность во время загрузки
                    if check_active_func and not check_active_func():
                        print(f"[AssetWorker] Worker deactivated, cancelling download.")
                        if os.path.exists(filepath):
                            os.remove(filepath)
                        return False
                    f.write(chunk)
        
        if os.path.getsize(filepath) < 50000:
             print(f"[AssetWorker] ❌ File too small.")
             os.remove(filepath)
             return False
        
        # Проверка ориентации
        w, h = get_video_dimensions(filepath)
        if w > 0 and h > w: # Высота больше ширины = вертикальное
            print(f"[AssetWorker] ❌ Vertical video detected ({w}x{h}). Removing.")
            os.remove(filepath)
            return False
             
        print(f"[AssetWorker] ✅ Downloaded: {filepath}")
        return True
    except Exception as e:
        print(f"[AssetWorker] ❌ Download error: {e}")
        return False

def fetch_pixabay_videos(tag, db: Session, check_active_func):
    """
    Ищет видео на Pixabay по тегу и скачивает их.
    check_active_func - функция для проверки активности воркера
    """
    print(f"[AssetWorker] Searching Pixabay for: '{tag}'")
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q={tag}&per_page=10&orientation=horizontal&min_width=1280"
    
    try:
        # Проверяем активность перед запросом
        if not check_active_func():
            return False
            
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"[AssetWorker] API Error {response.status_code}")
            return False

        data = response.json()
        hits = data.get("hits", [])
        
        downloaded_count = 0
        
        for video in hits:
            # Проверяем активность перед каждой итерацией
            if not check_active_func():
                print(f"[AssetWorker] Worker deactivated, stopping download.")
                return False
                
            video_id = str(video.get("id"))
            
            # 1. Проверяем историю (качали ли мы это?)
            history = db.query(AssetHistory).filter_by(source='pixabay', source_id=video_id).first()
            if history:
                # print(f"[AssetWorker] Skip {video_id} (already in history).")
                continue
                
            filename = f"pixabay_{video_id}.mp4"
            filepath = os.path.join(ASSETS_DIR, filename)
            
            # Проверяем файлы
            if os.path.exists(filepath): continue
                
            # Ищем ссылку (Large > Medium)
            videos_dict = video.get("videos", {})
            download_url = videos_dict.get("large", {}).get("url") or videos_dict.get("medium", {}).get("url")
            
            if not download_url: continue
            
            # Проверяем активность перед загрузкой
            if not check_active_func():
                print(f"[AssetWorker] Worker deactivated, stopping download.")
                return False
                
            if download_file(download_url, filepath, check_active_func):
                # 2. Записываем в историю
                new_history = AssetHistory(
                    source='pixabay', 
                    source_id=video_id, 
                    local_path=filepath
                )
                db.add(new_history)
                db.commit()
                
                downloaded_count += 1
                
                # Проверяем лимит в папке
                files_count = len([f for f in os.listdir(ASSETS_DIR) if f.endswith('.mp4')])
                if files_count >= MAX_ASSETS_COUNT:
                    print("[AssetWorker] Max assets limit reached.")
                    return True
                    
                time.sleep(1) # Пауза
                
        return downloaded_count > 0

    except Exception as e:
        print(f"[AssetWorker] Error fetching Pixabay: {e}")
        return False

def run_asset_worker():
    """
    Воркер, который следит за количеством ассетов.
    """
    if not os.path.exists(ASSETS_DIR): os.makedirs(ASSETS_DIR, exist_ok=True)
    if not os.path.exists(USED_ASSETS_DIR): os.makedirs(USED_ASSETS_DIR, exist_ok=True)
        
    print("AssetWorker started (waiting for activation)...")
    
    current_tag_idx = 0
    last_inactive_message = 0

    while True:
        try:
            db: Session = SessionLocal()
            settings = db.query(Settings).first()
            
            is_active = False
            if settings:
                try: is_active = settings.asset_manager_active
                except: pass

            if not is_active:
                current_time = time.time()
                if current_time - last_inactive_message >= 60:  # Раз в минуту
                    print("[AssetWorker] Inactive (waiting for activation)...")
                    last_inactive_message = current_time
                db.close()
                time.sleep(2)
                continue
                
            # Считаем ТОЛЬКО активные (не использованные) ассеты
            files = [f for f in os.listdir(ASSETS_DIR) if f.endswith(('.mp4', '.webm'))]
            
            # Если меньше максимума - докачиваем
            if len(files) < MAX_ASSETS_COUNT:
                tag = ASSET_SEARCH_TAGS[current_tag_idx]
                
                # Функция для проверки активности
                def check_active():
                    try:
                        db_check = SessionLocal()
                        settings_check = db_check.query(Settings).first()
                        is_active_check = False
                        if settings_check:
                            try: 
                                is_active_check = settings_check.asset_manager_active
                            except: 
                                pass
                        db_check.close()
                        return is_active_check
                    except:
                        return False
                
                fetch_pixabay_videos(tag, db, check_active)
                
                current_tag_idx = (current_tag_idx + 1) % len(ASSET_SEARCH_TAGS)
            else:
                time.sleep(5)
            
            db.close()
            time.sleep(5) 

        except Exception as e:
            print(f"[AssetWorker] Critical error: {e}")
            time.sleep(5)
