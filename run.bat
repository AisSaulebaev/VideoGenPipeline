@echo off
REM Скрипт для запуска приложения из виртуального окружения

echo ========================================
echo Запуск VideoGenPipeline...
echo ========================================

REM Проверяем наличие виртуального окружения
if not exist "venv\Scripts\python.exe" (
    echo ОШИБКА: Виртуальное окружение не найдено!
    echo Запустите сначала: setup_venv.bat
    pause
    exit /b 1
)

REM Запускаем приложение напрямую через python из venv
venv\Scripts\python.exe main.py

REM Если произошла ошибка, пауза для просмотра
if errorlevel 1 (
    echo.
    echo Произошла ошибка при запуске!
    pause
)

