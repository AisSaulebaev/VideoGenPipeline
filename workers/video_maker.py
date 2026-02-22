import os
import time
import subprocess
import random
import shutil
import re
from sqlalchemy.orm import Session
from database import SessionLocal, Task, Settings
from config import BASE_DIR, VIDEO_QUALITY_CRF

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
USED_ASSETS_DIR = os.path.join(BASE_DIR, "assets", "used")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

def get_audio_duration(audio_path):
    cmd = [
        "ffprobe", 
        "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", 
        audio_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"[VideoMaker] Error getting duration: {e}")
        return 0

def get_video_bitrate(video_path):
    """
    Получает битрейт исходного видео в Мбит/с.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=bit_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        bitrate_bps = result.stdout.strip()
        if bitrate_bps and bitrate_bps.isdigit():
            # Конвертируем из бит/с в Мбит/с
            bitrate_mbps = int(bitrate_bps) / 1000000
            return bitrate_mbps
        else:
            # Если не удалось получить, пробуем через format
            cmd_format = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=bit_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]
            result_format = subprocess.run(cmd_format, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            bitrate_bps = result_format.stdout.strip()
            if bitrate_bps and bitrate_bps.isdigit():
                bitrate_mbps = int(bitrate_bps) / 1000000
                return bitrate_mbps
    except Exception as e:
        print(f"[VideoMaker] Warning: Could not get bitrate from source: {e}")
    
    # Fallback: возвращаем None, будет использован CRF
    return None

def get_random_background():
    if not os.path.exists(ASSETS_DIR): return None
    videos = [f for f in os.listdir(ASSETS_DIR) if f.endswith(('.mp4', '.webm', '.mov')) and os.path.isfile(os.path.join(ASSETS_DIR, f))]
    if not videos: return None
    return os.path.join(ASSETS_DIR, random.choice(videos))

def create_video(audio_path, background_path, output_path):
    duration = get_audio_duration(audio_path)
    if duration == 0: raise Exception("Audio duration is 0")
    
    print(f"[VideoMaker] Target duration: {duration:.2f}s")
    
    # Получаем битрейт исходного видео
    source_bitrate_mbps = get_video_bitrate(background_path)
    if source_bitrate_mbps:
        source_bitrate_str = f"{int(source_bitrate_mbps)}M"
        print(f"[VideoMaker] Source video bitrate: {source_bitrate_mbps:.2f} Mbps")
    else:
        source_bitrate_str = None
        print(f"[VideoMaker] Could not detect source bitrate, using CRF only")
    
    # Настройки для высокого качества:
    # 1. Аппаратное ускорение (hwaccel auto)
    # 2. Кодек NVIDIA (h264_nvenc)
    # 3. Пресет p4 (высокое качество)
    # 4. CRF для контроля качества
    # 5. Битрейт из исходного видео
    # 6. Пропорциональное масштабирование
    
    cmd = [
        "ffmpeg",
        "-hwaccel", "auto",       # Включаем GPU декодирование
        "-i", background_path,
        "-i", audio_path,
        "-filter_complex", 
        # Mirror Loop фильтр с пропорциональным масштабированием
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[vscaled]; [vscaled]split[original][copy]; [copy]reverse[reversed]; [original][reversed]concat=n=2:v=1:a=0[pingpong]; [pingpong]loop=-1:size=32767:start=0[outv]",
        "-map", "[outv]",
        "-map", "1:a:0",
        "-t", str(duration),
        "-c:v", "h264_nvenc",     # Используем GPU кодек
        "-preset", "p4",          # Пресет p4 = высокое качество
        "-rc", "vbr",             # Variable bitrate для лучшего качества
        "-cq", str(VIDEO_QUALITY_CRF),  # Constant Quality (CRF) = 23
    ]
    
    # Добавляем битрейт если удалось определить
    if source_bitrate_str:
        cmd.extend([
            "-b:v", source_bitrate_str,    # Битрейт из исходного видео
            "-maxrate", f"{int(source_bitrate_mbps * 1.5)}M",  # Максимальный битрейт +50%
            "-bufsize", f"{int(source_bitrate_mbps * 2)}M",    # Буфер для VBR
        ])
    
    cmd.extend([
        "-c:a", "aac",
        "-b:a", "192k",
        "-y",
        output_path
    ])
    
    print(f"[VideoMaker] Creating Mirror Loop video (GPU Optimized) using background: {os.path.basename(background_path)}")
    print(f"[VideoMaker] Target duration: {duration:.2f}s")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    import re
    last_progress = 0
    
    for line in process.stdout:
        line = line.strip()
        
        # Парсим прогресс из FFmpeg вывода
        # Формат: time=00:00:05.23 или frame=  123 fps= 25
        if "time=" in line:
            # Извлекаем время
            time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
            if time_match:
                hours, minutes, seconds = time_match.groups()
                current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
                progress = (current_time / duration) * 100 if duration > 0 else 0
                progress = min(100, max(0, progress))
                
                # Выводим только если прогресс изменился на 5% или больше
                if abs(progress - last_progress) >= 5:
                    print(f"\r[VideoMaker] Progress: {progress:.1f}% ({current_time:.1f}s / {duration:.1f}s)", end="", flush=True)
                    last_progress = progress
        elif "frame=" in line:
            # Показываем информацию о кадрах
            frame_match = re.search(r'frame=\s*(\d+)', line)
            if frame_match:
                frame_num = int(frame_match.group(1))
                # Примерно 30 fps, можно вычислить время
                estimated_time = frame_num / 30.0
                if duration > 0:
                    progress = (estimated_time / duration) * 100
                    progress = min(100, max(0, progress))
                    if abs(progress - last_progress) >= 5:
                        print(f"\r[VideoMaker] Progress: {progress:.1f}% (frame {frame_num})", end="", flush=True)
                        last_progress = progress
        elif "Error" in line or "failed" in line:
            print(f"\n[FFMPEG Error] {line}")
            
    process.wait()
    print(f"\n[VideoMaker] ✅ Video creation completed!")

    if process.returncode != 0:
        raise subprocess.CalledProcessError(process.returncode, cmd)

def run_video_maker_worker():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not os.path.exists(USED_ASSETS_DIR): os.makedirs(USED_ASSETS_DIR, exist_ok=True)

    print("VideoMaker worker started (waiting for activation)...")

    last_inactive_message = 0

    while True:
        try:
            db: Session = SessionLocal()
            settings = db.query(Settings).first()

            if not settings or not settings.video_maker_active:
                current_time = time.time()
                if current_time - last_inactive_message >= 60:  # Раз в минуту
                    print("[VideoMaker] Inactive (waiting for activation)...")
                    last_inactive_message = current_time
                db.close()
                time.sleep(2)
                continue

            task = db.query(Task).filter(Task.status == "pending_merge").first()
            
            if task:
                # СНАЧАЛА проверяем наличие ассетов, ПОТОМ меняем статус
                bg_path = get_random_background()
                
                if not bg_path:
                    print(f"[VideoMaker] No background videos found in {ASSETS_DIR}. Waiting...")
                    db.close()
                    time.sleep(5)
                    continue
                
                # Только после проверки меняем статус
                print(f"[VideoMaker] Processing task: {task.filename}")
                task.status = "merging"
                db.commit()

                try:
                    video_filename = f"{task.filename.replace('.txt', '')}.mp4"
                    final_video_path = os.path.join(OUTPUT_DIR, video_filename)
                    
                    create_video(task.audio_path, bg_path, final_video_path)
                    
                    try:
                        shutil.move(bg_path, os.path.join(USED_ASSETS_DIR, os.path.basename(bg_path)))
                        print(f"[VideoMaker] Moved used asset to: {USED_ASSETS_DIR}")
                    except Exception as e:
                        print(f"[VideoMaker] Warning: could not move used asset: {e}")

                    task.final_video_path = final_video_path
                    task.status = "pending_metadata" # Теперь передаем эстафету MetadataWorker
                    db.commit()
                    print(f"[VideoMaker] ✅ Completed task: {task.filename}")
                    
                except subprocess.CalledProcessError as e:
                    print(f"\n[VideoMaker] FFMPEG Error (Code {e.returncode})")
                    task.status = "ERROR"
                    task.error_message = "FFMPEG Error"
                    db.commit()
                except Exception as e:
                    print(f"\n[VideoMaker] Error processing {task.filename}: {e}")
                    task.status = "ERROR"
                    task.error_message = str(e)
                    db.commit()
            
            db.close()
            time.sleep(2)

        except Exception as e:
            print(f"[VideoMaker] Critical error: {e}")
            time.sleep(5)
