========================================
БЫСТРЫЙ СТАРТ
========================================

Windows:
1. Запустите: setup_venv.bat (создаст виртуальное окружение и установит зависимости)
2. Запустите: run.bat (запустит приложение)

Linux/macOS:
1. chmod +x setup_venv.sh run.sh
2. ./setup_venv.sh
3. ./run.sh

========================================
РУЧНАЯ УСТАНОВКА
========================================

Windows:
  python -m venv venv
  venv\Scripts\activate
  pip install -r requirements.txt
  python main.py

Linux/macOS:
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  python main.py

========================================
ИНФОРМАЦИЯ
========================================

Веб-интерфейс: http://127.0.0.1:8000

Папки:
- scenarios/ - сценарии (.txt файлы)
- output/ - готовые видео
- assets/ - фоновые видео (скачиваются автоматически)
- uploaded_videos/ - загруженные на YouTube
- thumbnails/ - превью для видео
- tokens/ - токены OAuth
- profiles/ - профили браузера

Настройки: config.py

Подробная документация: README_SETUP.md
