from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, DateTime, Float, ForeignKey, JSON, func, event
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.ext.declarative import declarative_base
import datetime
import os
from pathlib import Path

# Путь к БД относительно папки проекта
BASE_DIR = Path(__file__).parent.absolute()
DB_PATH = str(BASE_DIR / "video_gen.db")

Base = declarative_base()

class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    scanner_active = Column(Boolean, default=False)
    voicer_active = Column(Boolean, default=False)
    video_maker_active = Column(Boolean, default=False)
    metadata_worker_active = Column(Boolean, default=False) # New worker
    asset_manager_active = Column(Boolean, default=False)
    uploader_active = Column(Boolean, default=False)

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    content = Column(Text)
    status = Column(String, default="NEW") # NEW, VOICED, DONE, ERROR
    audio_path = Column(String, nullable=True)
    final_video_path = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # --- Metadata ---
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    thumbnail_path = Column(String, nullable=True)

    # Связи (опционально, если нужны)
    # upload_history = relationship("UploadHistory", back_populates="task")

class UploadHistory(Base):
    __tablename__ = "upload_history"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey('tasks.id'))
    account_id = Column(Integer, ForeignKey('google_accounts.id'))
    
    youtube_video_id = Column(String)
    scheduled_time = Column(DateTime) # Когда публикуется
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow) # Когда загрузили физически
    
    task = relationship("Task")
    account = relationship("GoogleAccount", back_populates="uploads")

class AssetHistory(Base):
    __tablename__ = "asset_history"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String) 
    source_id = Column(String) 
    local_path = Column(String)
    downloaded_at = Column(DateTime, default=datetime.datetime.utcnow)

class GoogleAccount(Base):
    __tablename__ = 'google_accounts'
    id = Column(Integer, primary_key=True)
    email = Column(String(191), nullable=False, unique=True)
    password = Column(String(255), nullable=False) 
    recovery_email = Column(String(255), nullable=True)

    profile_path = Column(Text, nullable=True)
    cookie_path = Column(Text, nullable=True) 

    proxy = Column(String(255), nullable=True)
    user_agent = Column(Text, nullable=True)
    language_target = Column(String(50), nullable=False, default='English (US)') 
    language_changed = Column(Boolean, nullable=False, default=False) 
    last_login_status = Column(String(50), nullable=True) 
    last_checked_at = Column(DateTime, nullable=True) 
    is_active = Column(Boolean, nullable=False, default=True) 
    daily_limit_reached_at = Column(DateTime, nullable=True)
    limit_cycle_started_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    token_path = Column(String(255), nullable=True)
    is_authenticated = Column(Boolean, default=False)
    is_browser_running = Column(Boolean, default=False)
    
    token_created = Column(Boolean, nullable=False, default=False)
    is_working = Column(Boolean, nullable=False, default=True) 
    is_free = Column(Boolean, nullable=False, default=True)

    uploads = relationship("UploadHistory", back_populates="account")

engine = create_engine(
    f"sqlite:///{DB_PATH}", 
    connect_args={"check_same_thread": False, "timeout": 30}
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_and_update_db_schema():
    """Проверяет и добавляет недостающие колонки в таблицу tasks."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    
    # 1. Проверяем таблицу tasks
    if "tasks" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("tasks")]
        
        with engine.connect() as conn:
            if "account_id" not in columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN account_id INTEGER REFERENCES google_accounts(id)"))
            if "youtube_video_id" not in columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN youtube_video_id VARCHAR"))
            if "publish_date" not in columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN publish_date DATETIME"))
            if "uploaded_at" not in columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN uploaded_at DATETIME"))
            
            # Metadata
            if "title" not in columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN title VARCHAR"))
            if "description" not in columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN description TEXT"))
            if "thumbnail_path" not in columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN thumbnail_path VARCHAR"))
                
            conn.commit()

    # 2. Проверяем таблицу settings
    if "settings" in inspector.get_table_names():
        columns = [c["name"] for c in inspector.get_columns("settings")]
        with engine.connect() as conn:
            if "uploader_active" not in columns:
                conn.execute(text("ALTER TABLE settings ADD COLUMN uploader_active BOOLEAN DEFAULT 0"))
            if "metadata_worker_active" not in columns:
                conn.execute(text("ALTER TABLE settings ADD COLUMN metadata_worker_active BOOLEAN DEFAULT 0"))
            conn.commit()

    # 3. Создаем upload_history, если нет (через metadata create_all это делается автоматом, 
    # но только если таблицы нет вообще. Если мы добавили класс позже, create_all создаст таблицу)
    # Поэтому тут ничего делать не нужно, init_db вызовет create_all.

def init_db():
    Base.metadata.create_all(bind=engine)
    check_and_update_db_schema()
