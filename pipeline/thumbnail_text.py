import os
from PIL import Image, ImageDraw, ImageFont
from config import BASE_DIR

# Конфигурация стиля
TEXT_COLOR = "white"
STROKE_COLOR = "black"
MAX_WIDTH_RATIO = 0.65 
PADDING = 40           

def get_font_path():
    """Ищет файл font.ttf или font.otf в корне проекта"""
    for file in os.listdir(BASE_DIR):
        if file.lower() in ["font.ttf", "font.otf"]:
            return os.path.join(BASE_DIR, file)
    return None

def get_font(path, size):
    try:
        # Пробуем с базовым движком (помогает от квадратиков)
        return ImageFont.truetype(path, size, layout_engine=ImageFont.LAYOUT_BASIC)
    except Exception:
        return ImageFont.truetype(path, size)

def get_wrapped_text(text, font, max_width):
    lines = []
    words = text.split()
    if not words: return []
    current_line = words[0]
    for word in words[1:]:
        test_line = current_line + " " + word
        bbox = font.getbbox(test_line)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines

def fit_text_to_box(text, font_path, max_width, max_height):
    font_size = 300 
    min_font_size = 40
    
    while font_size >= min_font_size:
        font = get_font(font_path, font_size)
        if not font: return None, [], 0, 0
        
        lines = get_wrapped_text(text, font, max_width)
        
        ascent, descent = font.getmetrics()
        line_height = ascent + descent + 10
        total_height = line_height * len(lines)
        
        if total_height <= max_height:
            is_wide_ok = True
            for line in lines:
                bbox = font.getbbox(line)
                if (bbox[2] - bbox[0]) > max_width:
                    is_wide_ok = False
                    break
            
            if is_wide_ok:
                return font, lines, line_height, font_size
                
        font_size -= 5 
        
    return None, [], 0, 0

def add_text_to_image(image_path: str, text: str) -> bool:
    """
    Добавляет текст на изображение и перезаписывает его.
    Возвращает True, если успешно.
    """
    font_path = get_font_path()
    if not font_path:
        print(f"[ThumbnailText] ⚠️ Шрифт не найден в папке {BASE_DIR}")
        return False
        
    try:
        img = Image.open(image_path).convert("RGBA")
        width, height = img.size
        
        draw = ImageDraw.Draw(img)
        
        box_width = int(width * MAX_WIDTH_RATIO) - (PADDING * 2)
        box_height = height - (PADDING * 2)
        
        font, lines, line_height, final_size = fit_text_to_box(text, font_path, box_width, box_height)
        
        if not font:
            print(f"[ThumbnailText] ⚠️ Не удалось подобрать размер шрифта")
            return False

        total_text_height = line_height * len(lines)
        start_y = (height - total_text_height) // 2
        
        # Обводка: 4% от размера
        stroke_width = max(3, int(final_size * 0.04))

        for i, line in enumerate(lines):
            # Центрирование
            bbox = font.getbbox(line)
            line_w = bbox[2] - bbox[0]
            center_x = PADDING + (box_width // 2)
            x = center_x - (line_w // 2)
            y = start_y + (i * line_height)
            
            draw.text(
                (x, y), 
                line, 
                font=font, 
                fill=TEXT_COLOR, 
                stroke_width=stroke_width, 
                stroke_fill=STROKE_COLOR
            )

        # Конвертируем обратно в RGB для сохранения (если был PNG, станет JPG или останется PNG)
        # Если исходник PNG, то RGBA ок. Если JPG, то надо RGB.
        if image_path.lower().endswith(".jpg") or image_path.lower().endswith(".jpeg"):
            img = img.convert("RGB")
            
        img.save(image_path)
        print(f"[ThumbnailText] ✅ Текст добавлен на {os.path.basename(image_path)}")
        return True
            
    except Exception as e:
        print(f"[ThumbnailText] ❌ Ошибка добавления текста: {e}")
        return False


