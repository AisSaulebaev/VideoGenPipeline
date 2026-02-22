import os
import time
import re
import shutil
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from database import SessionLocal, Task, Settings
from config import ELEVENSLABS_BOT_API_KEY, ELEVENLABSBOT_MALE_VOICE_ID, VOICE_CHUNK_SIZE, TTS_WORKER_THREADS, BASE_DIR
from pipeline.eleven_bot_module import VoiceSynthesizer

AUDIO_OUTPUT_DIR = os.path.join(BASE_DIR, "temp_audio")
TEMP_CHUNKS_DIR = os.path.join(BASE_DIR, "temp_chunks")

# Настройка логгера
logger = logging.getLogger("VoicerWorker")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def chunk_text(text: str, max_chunk_size: int) -> list[str]:
    """Нарезает текст на куски, не разрывая предложения."""
    chunks = []
    current_chunk = ""
    # Разделяем по предложениям
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        if not sentence: continue
            
        if len(current_chunk) + len(sentence) + 1 > max_chunk_size and current_chunk:
            chunks.append(current_chunk)
            current_chunk = sentence
        else:
            if current_chunk: current_chunk += " " + sentence
            else: current_chunk = sentence
            
    if current_chunk: chunks.append(current_chunk)
    return chunks

def run_voicer_worker():
    """
    Воркер озвучки через VoiceSynthesizer (ElevenLabs Bot).
    """
    if not os.path.exists(AUDIO_OUTPUT_DIR): os.makedirs(AUDIO_OUTPUT_DIR)
    if not os.path.exists(TEMP_CHUNKS_DIR): os.makedirs(TEMP_CHUNKS_DIR)

    print("Voicer worker started (waiting for activation)...")
    
    # Инициализация синтезатора
    try:
        synthesizer = VoiceSynthesizer(api_key=ELEVENSLABS_BOT_API_KEY, logger=logger)
    except Exception as e:
        print(f"[Voicer] Failed to init synthesizer: {e}")
        return

    last_inactive_message = 0

    while True:
        try:
            db: Session = SessionLocal()
            settings = db.query(Settings).first()

            if not settings or not settings.voicer_active:
                current_time = time.time()
                if current_time - last_inactive_message >= 60:  # Раз в минуту
                    print("[Voicer] Inactive (waiting for activation)...")
                    last_inactive_message = current_time
                db.close()
                time.sleep(2)
                continue

            task = db.query(Task).filter(Task.status == "pending_voice").first()
            
            if task:
                print(f"[Voicer] Processing task: {task.filename}")
                task.status = "voicing"
                db.commit()
                
                try:
                    # 1. Нарезаем текст
                    chunks = chunk_text(task.content, VOICE_CHUNK_SIZE)
                    print(f"[Voicer] Split into {len(chunks)} chunks.")
                    
                    task_chunks_dir = os.path.join(TEMP_CHUNKS_DIR, str(task.id))
                    if not os.path.exists(task_chunks_dir): os.makedirs(task_chunks_dir)
                    
                    generated_files = []
                    futures = {}
                    total_chunks = len(chunks)
                    cached_count = 0
                    
                    # 2. Озвучиваем параллельно
                    with ThreadPoolExecutor(max_workers=TTS_WORKER_THREADS) as executor:
                        for i, chunk in enumerate(chunks):
                            chunk_filename = f"chunk_{i:04d}.mp3"
                            chunk_path = os.path.join(task_chunks_dir, chunk_filename)
                            
                            # Если уже есть (кэш), пропускаем
                            if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 1024:
                                generated_files.append(chunk_path)
                                cached_count += 1
                                continue
                                
                            future = executor.submit(
                                synthesizer.synthesize, 
                                chunk, 
                                ELEVENLABSBOT_MALE_VOICE_ID, 
                                chunk_path
                            )
                            futures[future] = (chunk_path, i + 1)  # Сохраняем номер чанка
                        
                        if cached_count > 0:
                            print(f"[Voicer] Found {cached_count}/{total_chunks} cached chunks.")
                        
                        completed_count = cached_count
                        for future in as_completed(futures):
                            path, chunk_num = futures[future]
                            # result() вызовет исключение, если что-то не так, или вернет True/False
                            try:
                                print(f"[Voicer] Processing chunk {chunk_num}/{total_chunks}...")
                                if future.result(timeout=180): # 3 минуты на чанк максимум
                                    generated_files.append(path)
                                    completed_count += 1
                                    print(f"[Voicer] ✅ Chunk {chunk_num}/{total_chunks} completed ({completed_count}/{total_chunks} total)")
                                else:
                                    raise Exception(f"Failed to synthesize chunk (API returned False): {os.path.basename(path)}")
                            except TimeoutError:
                                raise Exception(f"Timeout processing chunk: {os.path.basename(path)}")
                    
                    # 3. Склеиваем через FFMPEG
                    generated_files.sort() # Важно!
                    
                    final_audio_filename = f"{task.filename.replace('.txt', '')}.mp3"
                    final_audio_path = os.path.join(AUDIO_OUTPUT_DIR, final_audio_filename)
                    
                    concat_list_path = os.path.join(task_chunks_dir, "concat.txt")
                    with open(concat_list_path, 'w', encoding='utf-8') as f:
                        for mp3 in generated_files:
                            f.write(f"file '{os.path.abspath(mp3)}'\n")
                            
                    cmd = [
                        "ffmpeg", "-f", "concat", "-safe", "0",
                        "-i", concat_list_path,
                        "-c", "copy", "-y",
                        final_audio_path
                    ]
                    
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    
                    # 4. Чистим
                    try: shutil.rmtree(task_chunks_dir)
                    except: pass
                    
                    # 5. Сохраняем результат
                    task.audio_path = final_audio_path
                    task.status = "pending_merge"
                    db.commit()
                    print(f"[Voicer] ✅ Completed task: {task.filename}")

                except Exception as e:
                    print(f"[Voicer] Error: {e}")
                    task.status = "ERROR"
                    task.error_message = str(e)
                    db.commit()
            
            db.close()
            time.sleep(2)

        except Exception as e:
            print(f"[Voicer] Critical error: {e}")
            time.sleep(5)
