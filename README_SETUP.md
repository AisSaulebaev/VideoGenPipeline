# Установка и запуск VideoGenPipeline

## Быстрый старт

### Windows:

1. **Создание виртуального окружения и установка зависимостей:**
   ```cmd
   setup_venv.bat
   ```

2. **Запуск приложения:**
   ```cmd
   run.bat
   ```

### Linux/macOS:

1. **Сделать скрипты исполняемыми:**
   ```bash
   chmod +x setup_venv.sh run.sh
   ```

2. **Создание виртуального окружения и установка зависимостей:**
   ```bash
   ./setup_venv.sh
   ```

3. **Запуск приложения:**
   ```bash
   ./run.sh
   ```

## Ручная установка

Если скрипты не работают, можно установить вручную:

### Windows:
```cmd
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

### Linux/macOS:
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python main.py
```

## Требования

- Python 3.10 или выше
- FFmpeg (должен быть в PATH)
- Google Chrome (для работы с аккаунтами)

## Структура папок

После первого запуска будут созданы следующие папки:
- `venv/` - виртуальное окружение Python
- `video_gen.db` - база данных SQLite
- `tokens/` - токены OAuth для YouTube API
- `profiles/` - профили браузера для аккаунтов
- `scenarios/` - папка для сценариев (.txt файлы)
- `scenarios_processed/` - обработанные сценарии
- `temp_audio/` - временные аудио файлы
- `temp_chunks/` - временные чанки озвучки
- `assets/` - фоновые видео для роликов
- `output/` - готовые видео
- `uploaded_videos/` - загруженные на YouTube видео
- `thumbnails/` - превью для видео

## Настройка

Все настройки находятся в файле `config.py`:
- API ключи (OpenAI, ElevenLabs, Pixabay)
- Пути к файлам
- Параметры воркеров
- Настройки YouTube загрузки

## Веб-интерфейс

После запуска приложение будет доступно по адресу:
http://127.0.0.1:8000

## Примечания

- Виртуальное окружение создается внутри папки `VideoGenPipeline`
- Все зависимости устанавливаются только в виртуальное окружение
- Проект полностью автономен и может быть перенесен в любое место

