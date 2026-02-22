import os
from config import CHROME_EXECUTABLE_PATH, CHROME_VERSION_MAIN, DISABLE_CHROME_VERSION_CHECK

def get_chrome_executable_path() -> str:
    if not os.path.exists(CHROME_EXECUTABLE_PATH):
        raise FileNotFoundError(f"Chrome not found at: {CHROME_EXECUTABLE_PATH}")
    return CHROME_EXECUTABLE_PATH

def should_disable_chrome_version_check() -> bool:
    return DISABLE_CHROME_VERSION_CHECK

def get_chrome_version_main() -> int:
    return CHROME_VERSION_MAIN

