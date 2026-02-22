@echo off
REM Скрипт для создания виртуального окружения и установки зависимостей

echo ========================================
echo Создание виртуального окружения...
echo ========================================

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ОШИБКА: Python не найден! Установите Python 3.10+ и добавьте в PATH.
    pause
    exit /b 1
)

REM Создаем виртуальное окружение
if exist "venv" (
    echo Виртуальное окружение уже существует. Удаляю старое...
    rmdir /s /q venv
)

python -m venv venv
if errorlevel 1 (
    echo ОШИБКА: Не удалось создать виртуальное окружение!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Активация окружения и установка зависимостей...
echo ========================================

call venv\Scripts\activate.bat

echo Обновление pip...
python -m pip install --upgrade pip

echo.
echo Установка зависимостей из requirements.txt...
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ОШИБКА: Не удалось установить зависимости!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Готово! Виртуальное окружение создано.
echo ========================================
echo.
echo Для запуска используйте: run.bat
echo.
pause

