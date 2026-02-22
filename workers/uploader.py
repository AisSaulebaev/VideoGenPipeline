import os
import pickle
import time
import datetime
import logging
import random
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from sqlalchemy import func

from database import SessionLocal, Task, Settings, GoogleAccount, UploadHistory
from config import (
    CLIENT_SECRETS_FILE, TOKENS_DIR, YOUTUBE_SCOPES,
    UPLOAD_SCHEDULE_TIMES, UPLOADER_CHUNK_SIZE_MB, UPLOADER_SMALL_FILE_THRESHOLD_MB,
    UPLOADED_VIDEOS_DIR
)

# Настройка логгера
logger = logging.getLogger("UploaderWorker")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def get_authenticated_service(account: GoogleAccount):
    """Создает сервис YouTube API для аккаунта."""
    token_path = os.path.join(TOKENS_DIR, f"{account.email}.pickle")
    if not os.path.exists(token_path):
        if account.token_path and os.path.exists(account.token_path):
            token_path = account.token_path
        else:
            logger.error(f"Token not found for {account.email}")
            return None

    creds = None
    try:
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    except Exception as e:
        logger.error(f"Error loading token for {account.email}: {e}")
        return None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                logger.info(f"Refreshing token for {account.email}...")
                creds.refresh(Request())
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)
            except Exception as e:
                logger.error(f"Error refreshing token for {account.email}: {e}")
                return None
        else:
            logger.error(f"Token for {account.email} is invalid and cannot be refreshed.")
            return None

    try:
        service = build('youtube', 'v3', credentials=creds, cache_discovery=False)
        return service
    except Exception as e:
        logger.error(f"Error building YouTube service for {account.email}: {e}")
        return None

def get_next_schedule_time(account_id: int, db):
    """
    Вычисляет следующее время публикации для аккаунта с учетом списка слотов.
    """
    # Получаем последнюю запись из истории для этого аккаунта
    last_upload = db.query(UploadHistory).filter(
        UploadHistory.account_id == account_id
    ).order_by(UploadHistory.scheduled_time.desc()).first()

    now = datetime.datetime.now()
    
    # Парсим слоты времени
    # Пример: [(18, 0), (19, 0)]
    slots = []
    for t_str in UPLOAD_SCHEDULE_TIMES:
        try:
            h, m = map(int, t_str.split(':'))
            slots.append((h, m))
        except: pass
    
    if not slots:
        slots = [(18, 0)] # Default fallback
    
    slots.sort() # Гарантируем порядок: 18:00, 19:00

    if not last_upload or not last_upload.scheduled_time:
        # Если истории нет, ищем первый слот СЕГОДНЯ, который больше текущего времени
        start_date = now
        for h, m in slots:
            candidate = start_date.replace(hour=h, minute=m, second=0, microsecond=0)
            if candidate > now:
                return candidate
        
        # Если сегодня все слоты прошли, берем первый слот ЗАВТРА
        first_h, first_m = slots[0]
        return (start_date + datetime.timedelta(days=1)).replace(hour=first_h, minute=first_m, second=0, microsecond=0)

    else:
        # Если история есть, отталкиваемся от последнего времени
        last_dt = last_upload.scheduled_time
        
        # Ищем слот, соответствующий времени последней загрузки (или ближайший следующий)
        # Просто перебираем слоты того же дня
        current_slot_idx = -1
        
        # Попробуем найти точное совпадение времени
        for i, (h, m) in enumerate(slots):
            if last_dt.hour == h and last_dt.minute == m:
                current_slot_idx = i
                break
        
        if current_slot_idx != -1 and current_slot_idx < len(slots) - 1:
            # Есть еще слот сегодня
            next_h, next_m = slots[current_slot_idx + 1]
            return last_dt.replace(hour=next_h, minute=next_m, second=0, microsecond=0)
        else:
            # Слоты на этот день кончились (или не нашли совпадения), переходим на следующий день на первый слот
            first_h, first_m = slots[0]
            # Важно: добавляем день к дате ПОСЛЕДНЕЙ загрузки, а не к NOW
            # Но если последняя загрузка была давно (позавчера), то мы все равно хотим продолжить цепочку?
            # Или хотим "догнать" до сегодня?
            # User: "отталкиваемся от последнего загруженного видео"
            # Значит цепочка непрерывная. Даже если скрипт не работал неделю, он начнет планировать с той даты.
            # Это может создать очередь в прошлом, что плохо для publishAt (оно должно быть в будущем).
            
            next_day_candidate = (last_dt + datetime.timedelta(days=1)).replace(hour=first_h, minute=first_m, second=0, microsecond=0)
            
            # Корректировка: если next_day_candidate в прошлом (скрипт долго спал), 
            # переносим на "сегодня" или "завтра" ближайшее.
            if next_day_candidate < now:
                # Начинаем поиск от NOW
                for h, m in slots:
                    candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if candidate > now:
                        return candidate
                # Если сегодня нет, то завтра утром
                return (now + datetime.timedelta(days=1)).replace(hour=first_h, minute=first_m, second=0, microsecond=0)
            
            return next_day_candidate

def upload_video(service, task: Task, schedule_time: datetime.datetime):
    """Загружает видео на YouTube."""
    if not os.path.exists(task.final_video_path):
        logger.error(f"Video file not found: {task.final_video_path}")
        return None

    # Используем сгенерированные метаданные или фоллбэк
    title = task.title if task.title else os.path.splitext(task.filename)[0]
    
    # Ограничение YouTube: 100 символов
    if len(title) > 100:
        logger.warning(f"Title too long ({len(title)} chars). Truncating...")
        # Оставляем место для многоточия, если нужно, или просто режем
        # Лучше резать аккуратно, но пока жестко
        title = title[:99] + "…"
    
    description = task.description if task.description else f"Video generated automatically.\n\n{title}"
    
    # ISO формат для publishAt
    publish_at_str = schedule_time.isoformat() + "Z"

    # Импорт тегов
    from config import YOUTUBE_TAGS

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': YOUTUBE_TAGS,
            'categoryId': '24'
        },
        'status': {
            'privacyStatus': 'private', # Обязательно private
            'publishAt': publish_at_str,
            'selfDeclaredMadeForKids': False
        }
    }

    file_size = os.path.getsize(task.final_video_path)
    chunk_size = UPLOADER_CHUNK_SIZE_MB * 1024 * 1024
    
    media = MediaFileUpload(
        task.final_video_path,
        mimetype='video/mp4',
        chunksize=chunk_size,
        resumable=True
    )

    logger.info(f"Uploading '{title}' scheduled for {publish_at_str}...")
    
    try:
        request = service.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info(f"Upload progress: {progress}%") 
        
        if 'id' in response:
            return response['id']
        else:
            return None

    except HttpError as e:
        if e.resp.status in [403, 429]:
             return "QUOTA_EXCEEDED"
        logger.error(f"HTTP Error: {e}")
        return None
    except Exception as e:
        logger.error(f"Upload Error: {e}")
        return None

def run_uploader_worker():
    """Основной цикл воркера загрузки."""
    if not os.path.exists(UPLOADED_VIDEOS_DIR):
        os.makedirs(UPLOADED_VIDEOS_DIR, exist_ok=True)
        
    print("Uploader worker started (waiting for activation)...")

    last_inactive_message = 0

    while True:
        try:
            db = SessionLocal()
            settings = db.query(Settings).first()
            
            if not settings or not settings.uploader_active:
                current_time = time.time()
                if current_time - last_inactive_message >= 60:  # Раз в минуту
                    print("[Uploader] Inactive...")
                    last_inactive_message = current_time
                db.close()
                time.sleep(5)
                continue

            # Ищем задачу pending_upload
            task = db.query(Task).filter(Task.status == "pending_upload").first()
            
            if task:
                print(f"[Uploader] Processing task: {task.filename}")
                
                # 1. Ищем валидные аккаунты
                accounts = db.query(GoogleAccount).filter(GoogleAccount.is_active == True).all()
                valid_accounts = []
                for acc in accounts:
                    token_path = os.path.join(TOKENS_DIR, f"{acc.email}.pickle")
                    if os.path.exists(token_path) or (acc.token_path and os.path.exists(acc.token_path)):
                        valid_accounts.append(acc)
                
                if not valid_accounts:
                    logger.warning("No active Google Accounts with tokens!")
                    time.sleep(10)
                    db.close()
                    continue

                # 2. Выбираем аккаунт (Round Robin по дате последнего запланированного видео)
                best_account = None
                best_time = None
                
                for acc in valid_accounts:
                    last_upload = db.query(UploadHistory).filter(UploadHistory.account_id == acc.id).order_by(UploadHistory.scheduled_time.desc()).first()
                    
                    if not last_upload:
                        # Аккаунт девственно чист, берем его сразу
                        best_account = acc
                        break
                    else:
                        if best_time is None or last_upload.scheduled_time < best_time:
                            best_time = last_upload.scheduled_time
                            best_account = acc
                
                if not best_account:
                    best_account = valid_accounts[0] # Fallback

                logger.info(f"Selected account: {best_account.email}")
                
                # 3. Считаем время
                schedule_time = get_next_schedule_time(best_account.id, db)
                
                # 4. Меняем статус на uploading
                task.status = "uploading"
                db.commit()
                
                # 5. Загружаем
                try:
                    service = get_authenticated_service(best_account)
                    if service:
                        video_id = upload_video(service, task, schedule_time)
                        
                        if video_id == "QUOTA_EXCEEDED":
                            logger.warning(f"Quota exceeded for {best_account.email}")
                            task.status = "pending_upload" # Вернем
                            best_account.daily_limit_reached_at = datetime.datetime.now()
                            db.commit()
                            
                        elif video_id:
                            logger.info(f"Video uploaded: {video_id}")
                            
                            # ЗАГРУЗКА ПРЕВЬЮ
                            if task.thumbnail_path and os.path.exists(task.thumbnail_path):
                                try:
                                    logger.info(f"Uploading thumbnail: {task.thumbnail_path}")
                                    service.thumbnails().set(
                                        videoId=video_id,
                                        media_body=MediaFileUpload(task.thumbnail_path)
                                    ).execute()
                                    logger.info("Thumbnail set successfully.")
                                except Exception as thumb_e:
                                    logger.error(f"Error uploading thumbnail: {thumb_e}")

                            task.status = "uploaded" # Статус самого таска
                            
                            # ЗАПИСЬ В ИСТОРИЮ
                            history = UploadHistory(
                                task_id=task.id,
                                account_id=best_account.id,
                                youtube_video_id=video_id,
                                scheduled_time=schedule_time,
                                uploaded_at=datetime.datetime.now()
                            )
                            db.add(history)
                            
                            # Перемещаем файл
                            import shutil
                            dest_path = os.path.join(UPLOADED_VIDEOS_DIR, os.path.basename(task.final_video_path))
                            shutil.move(task.final_video_path, dest_path)
                            task.final_video_path = dest_path 
                            
                            db.commit()
                        else:
                             raise Exception("Upload failed (no ID)")
                    else:
                        raise Exception("No service")

                except Exception as e:
                    logger.error(f"Error processing upload: {e}")
                    task.status = "UPLOAD_ERROR"
                    task.error_message = str(e)
                    db.commit()
            
            db.close()
            time.sleep(5)
            
        except Exception as e:
            print(f"[Uploader] Critical error: {e}")
            time.sleep(10)
