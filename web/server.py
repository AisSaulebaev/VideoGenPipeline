import os
import json
import pickle
import shutil
import threading
from datetime import datetime
from fastapi import FastAPI, Request, Form, HTTPException, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import exc
from google_auth_oauthlib.flow import InstalledAppFlow
import undetected_chromedriver as uc

from database import SessionLocal, Task, Settings, GoogleAccount, UploadHistory, init_db
from config import CLIENT_SECRETS_FILE, TOKENS_DIR, YOUTUBE_SCOPES, BASE_DIR
from auth_module import GoogleAuth, AuthStatus

# Импортируем утилиты для браузера
from utils import get_chrome_executable_path, should_disable_chrome_version_check, get_chrome_version_main

app = FastAPI()

# --- STATIC FILES & TEMPLATES ---
# Путь к папке проекта (VideoGenPipeline)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
app.mount("/media", StaticFiles(directory=PROJECT_ROOT), name="media")

# Путь к шаблонам относительно папки проекта
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "web", "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Разрешаем OAuth через HTTP (для локального теста)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Глобальный словарь для запущенных браузеров: {account_id: driver_instance}
ACTIVE_MANUAL_BROWSERS = {}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    db: Session = SessionLocal()
    try:
        tasks = db.query(Task).order_by(Task.id.desc()).all()
        settings = db.query(Settings).first()
        if not settings: settings = Settings()
        
        accounts = db.query(GoogleAccount).all()
        
        # Обогащаем список аккаунтов информацией о запущенном браузере
        acc_list = []
        for acc in accounts:
            acc.is_browser_running = (acc.id in ACTIVE_MANUAL_BROWSERS)
            acc_list.append(acc)
            
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "tasks": tasks, 
            "settings": settings,
            "accounts": acc_list
        })
    finally:
        db.close()

# --- WORKER CONTROLS ---

@app.post("/toggle_worker")
async def toggle_worker(worker_name: str = Form(...)):
    db: Session = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings:
            settings = Settings()
            db.add(settings)
            
        if worker_name == "scanner": settings.scanner_active = not settings.scanner_active
        elif worker_name == "voicer": settings.voicer_active = not settings.voicer_active
        elif worker_name == "video_maker": settings.video_maker_active = not settings.video_maker_active
        elif worker_name == "asset_manager": settings.asset_manager_active = not settings.asset_manager_active
        elif worker_name == "uploader": settings.uploader_active = not settings.uploader_active
        elif worker_name == "metadata": settings.metadata_worker_active = not settings.metadata_worker_active
            
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

# --- API (JSON) FOR AUTO-UPDATE ---

@app.get("/api/tasks")
async def get_tasks_api():
    """Возвращает список задач в JSON для авто-обновления."""
    db: Session = SessionLocal()
    try:
        tasks = db.query(Task).order_by(Task.id.desc()).all()
        return [
            {
                "id": t.id,
                "filename": t.filename,
                "content": t.content,
                "status": t.status,
                "final_video_path": os.path.relpath(t.final_video_path, BASE_DIR).replace('\\', '/') if t.final_video_path and os.path.exists(t.final_video_path) else None,
                "title": t.title,
                "description": t.description,
                "thumbnail_path": os.path.relpath(t.thumbnail_path, BASE_DIR).replace('\\', '/') if t.thumbnail_path and os.path.exists(t.thumbnail_path) else None
            }
            for t in tasks
        ]
    finally:
        db.close()

@app.get("/api/upload_history")
async def get_upload_history_api():
    """Возвращает историю загрузок."""
    db: Session = SessionLocal()
    try:
        history = db.query(UploadHistory).order_by(UploadHistory.uploaded_at.desc()).limit(50).all()
        result = []
        for h in history:
            task = db.query(Task).get(h.task_id)
            acc = db.query(GoogleAccount).get(h.account_id)
            result.append({
                "id": h.id,
                "task_filename": task.filename if task else "Deleted",
                "account_email": acc.email if acc else "Deleted",
                "youtube_video_id": h.youtube_video_id,
                "scheduled_time": h.scheduled_time.strftime('%Y-%m-%d %H:%M') if h.scheduled_time else "-",
                "uploaded_at": h.uploaded_at.strftime('%Y-%m-%d %H:%M'),
                "link": f"https://youtu.be/{h.youtube_video_id}" if h.youtube_video_id else ""
            })
        return result
    finally:
        db.close()

@app.get("/api/workers_status")
async def get_workers_status_api():
    """Возвращает статусы воркеров."""
    db: Session = SessionLocal()
    try:
        settings = db.query(Settings).first()
        if not settings: settings = Settings()
        return {
            "scanner": settings.scanner_active,
            "voicer": settings.voicer_active,
            "video_maker": settings.video_maker_active,
            "asset_manager": settings.asset_manager_active,
            "uploader": settings.uploader_active,
            "metadata": settings.metadata_worker_active
        }
    finally:
        db.close()

# --- TASK CONTROLS ---

@app.post("/delete_task")
async def delete_task(task_id: int = Form(...)):
    db: Session = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            try:
                if task.audio_path and os.path.exists(task.audio_path): os.remove(task.audio_path)
                if task.final_video_path and os.path.exists(task.final_video_path): os.remove(task.final_video_path)
            except: pass
            db.delete(task)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/update_status")
async def update_status(task_id: int = Form(...), new_status: str = Form(...)):
    db: Session = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = new_status
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/", status_code=303)

# --- ACCOUNT CONTROLS ---

@app.post("/accounts/import")
async def import_accounts(file: UploadFile = File(...)):
    db: Session = SessionLocal()
    try:
        content = await file.read()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return RedirectResponse(url="/?error=InvalidJSON", status_code=303)
        
        if isinstance(data, list):
            count = 0
            for item in data:
                email = item.get("email") or item.get("login")
                if not email: continue

                existing = db.query(GoogleAccount).filter(GoogleAccount.email == email).first()
                if existing: continue
                
                new_acc = GoogleAccount(
                    email=email,
                    password=item.get("password", ""),
                    recovery_email=item.get("recovery_email", ""),
                    proxy=item.get("proxy", ""),
                    user_agent=item.get("user_agent", ""),
                    profile_path=item.get("profile_path", ""),
                    cookie_path=item.get("cookie_path", ""),
                    notes=item.get("notes", "")
                )
                db.add(new_acc)
                count += 1
            
            db.commit()
            return RedirectResponse(url=f"/#accounts", status_code=303)
        else:
            return RedirectResponse(url="/?error=JSONNotList", status_code=303)

    except Exception as e:
        return RedirectResponse(url=f"/?error={str(e)}", status_code=303)
    finally:
        db.close()


@app.post("/accounts/add")
async def add_account(email: str = Form(...), password: str = Form(""), recovery_email: str = Form("")):
    db: Session = SessionLocal()
    try:
        if db.query(GoogleAccount).filter(GoogleAccount.email == email).first():
            return RedirectResponse(url="/?error=AccountExists", status_code=303)
            
        new_acc = GoogleAccount(
            email=email,
            password=password,
            recovery_email=recovery_email
        )
        db.add(new_acc)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/#accounts", status_code=303)

@app.post("/accounts/delete")
async def delete_account(account_id: int = Form(...)):
    db: Session = SessionLocal()
    try:
        acc = db.query(GoogleAccount).filter(GoogleAccount.id == account_id).first()
        if acc:
            # Закрываем браузер если открыт
            if account_id in ACTIVE_MANUAL_BROWSERS:
                try:
                    ACTIVE_MANUAL_BROWSERS[account_id].quit()
                    del ACTIVE_MANUAL_BROWSERS[account_id]
                except: pass

            if acc.token_path and os.path.exists(acc.token_path):
                os.remove(acc.token_path)
            db.delete(acc)
            db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/#accounts", status_code=303)

# === SELENIUM / AUTH ACTIONS ===

@app.post("/accounts/login_selenium")
async def login_selenium(account_id: int = Form(...)):
    """Автоматический логин через Selenium."""
    db: Session = SessionLocal()
    try:
        acc = db.query(GoogleAccount).filter(GoogleAccount.id == account_id).first()
        if not acc: return RedirectResponse(url="/#accounts", status_code=303)
        
        # Если профиль/куки не заданы, создаем пути по умолчанию
        if not acc.profile_path:
            safe_folder_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in acc.email)
            base_profiles = os.path.join(BASE_DIR, "profiles")
            acc.profile_path = os.path.abspath(os.path.join(base_profiles, safe_folder_name))
            acc.cookie_path = os.path.abspath(os.path.join(acc.profile_path, "cookies.json"))
            db.commit()

        auth = GoogleAuth(
            email=acc.email,
            password=acc.password,
            profile_path=acc.profile_path,
            cookie_path=acc.cookie_path,
            recovery_email=acc.recovery_email,
            proxy=acc.proxy,
            user_agent=acc.user_agent
        )
        
        status = auth.login()
        acc.last_login_status = status.name
        acc.last_checked_at = datetime.now()
        db.commit()
        
    except Exception as e:
        print(f"Selenium Login Error: {e}")
    finally:
        db.close()
    return RedirectResponse(url="/#accounts", status_code=303)

@app.post("/accounts/change_language")
async def change_language(account_id: int = Form(...), lang: str = Form("English (US)")):
    """Смена языка через Selenium."""
    db: Session = SessionLocal()
    try:
        acc = db.query(GoogleAccount).filter(GoogleAccount.id == account_id).first()
        if not acc: return RedirectResponse(url="/#accounts", status_code=303)
        
        auth = GoogleAuth(
            email=acc.email, password=acc.password,
            profile_path=acc.profile_path, cookie_path=acc.cookie_path,
            proxy=acc.proxy, user_agent=acc.user_agent
        )
        result = auth.change_language(lang)
        if result:
            acc.language_changed = True
            acc.language_target = lang
            db.commit()
    except Exception as e:
        print(f"Change Lang Error: {e}")
    finally:
        db.close()
    return RedirectResponse(url="/#accounts", status_code=303)

@app.post("/accounts/browser/open")
async def open_browser(account_id: int = Form(...)):
    """Открыть браузер вручную (профиль пользователя)."""
    if account_id in ACTIVE_MANUAL_BROWSERS:
        return RedirectResponse(url="/#accounts", status_code=303)

    db: Session = SessionLocal()
    try:
        acc = db.query(GoogleAccount).filter(GoogleAccount.id == account_id).first()
        if not acc: return RedirectResponse(url="/#accounts", status_code=303)

        # Ensure paths
        if not acc.profile_path:
            safe_folder_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in acc.email)
            base_profiles = os.path.join(BASE_DIR, "profiles")
            acc.profile_path = os.path.abspath(os.path.join(base_profiles, safe_folder_name))
            db.commit()

        chrome_path = get_chrome_executable_path()
        disable_version_check = should_disable_chrome_version_check()

        options = uc.ChromeOptions()
        options.add_argument(f'--user-data-dir={acc.profile_path}')
        if acc.user_agent: options.add_argument(f'--user-agent={acc.user_agent}')
        if acc.proxy and 'http' not in acc.proxy: options.add_argument(f'--proxy-server={acc.proxy}')
        
        driver_kwargs = {'options': options, 'browser_executable_path': chrome_path}
        if disable_version_check:
            ver = get_chrome_version_main()
            driver_kwargs['version_main'] = ver if ver else None

        driver = uc.Chrome(**driver_kwargs)
        driver.get("https://www.youtube.com")
        
        ACTIVE_MANUAL_BROWSERS[account_id] = driver
        
    except Exception as e:
        print(f"Open Browser Error: {e}")
    finally:
        db.close()
    return RedirectResponse(url="/#accounts", status_code=303)

@app.post("/accounts/browser/close")
async def close_browser(account_id: int = Form(...)):
    """Закрыть браузер вручную."""
    if account_id in ACTIVE_MANUAL_BROWSERS:
        try:
            ACTIVE_MANUAL_BROWSERS[account_id].quit()
            del ACTIVE_MANUAL_BROWSERS[account_id]
        except: pass
    return RedirectResponse(url="/#accounts", status_code=303)

# === OAUTH TOKEN GENERATION ===

@app.get("/accounts/{account_id}/auth")
async def authorize_account(account_id: int):
    """Запускает OAuth flow для аккаунта. Ссылка выводится в консоль."""
    db: Session = SessionLocal()
    try:
        acc = db.query(GoogleAccount).filter(GoogleAccount.id == account_id).first()
        if not acc:
            return {"status": "error", "message": "Account not found"}
            
        if not os.path.exists(CLIENT_SECRETS_FILE):
            return {"status": "error", "message": f"Client secrets file not found at {CLIENT_SECRETS_FILE}"}

        # Создаем Flow
        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, YOUTUBE_SCOPES
        )
        # Указываем Redirect URI (должен совпадать с Console)
        flow.redirect_uri = "http://127.0.0.1:8000/oauth2callback"
        
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=str(account_id) # Передаем ID аккаунта в state
        )
        
        # Вывод ссылки в консоль сервера
        print(f"\n{'='*50}\n[Auth] Authorization Link for {acc.email}:\n{auth_url}\n{'='*50}\n")
        
        return {"status": "ok", "url": auth_url}
    finally:
        db.close()

@app.get("/oauth2callback")
async def oauth2callback(state: str, code: str):
    """Принимает код от Google и сохраняет токен."""
    db: Session = SessionLocal()
    try:
        account_id = int(state)
        acc = db.query(GoogleAccount).filter(GoogleAccount.id == account_id).first()
        if not acc:
            return HTMLResponse("Account not found for state", status_code=400)

        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, YOUTUBE_SCOPES, state=state
        )
        flow.redirect_uri = "http://127.0.0.1:8000/oauth2callback"
        
        # Обмениваем код на токен
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Сохраняем в файл
        token_filename = f"{acc.email}.pickle"
        token_path = os.path.join(TOKENS_DIR, token_filename)
        
        with open(token_path, 'wb') as token_file:
            pickle.dump(creds, token_file)
            
        # Обновляем БД
        acc.is_authenticated = True
        acc.token_path = token_path
        db.commit()
        
        return RedirectResponse(url="/#accounts")
    except Exception as e:
        return HTMLResponse(f"Auth Error: {e}", status_code=500)
    finally:
        db.close()
