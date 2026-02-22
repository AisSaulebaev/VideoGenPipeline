import os
from PIL import Image, ImageDraw, ImageFont

# Конфигурация
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THUMBNAILS_DIR = os.path.join(BASE_DIR, "thumbnails")

# Параметры
TEXT_COLOR = "white"
STROKE_COLOR = "black"
MAX_WIDTH_RATIO = 0.65 
PADDING = 40           

def get_font_path():
    for file in os.listdir(BASE_DIR):
        if file.lower() in ["font.ttf", "font.otf"]:
            return os.path.join(BASE_DIR, file)
    return None

def get_font(path, size):
    try:
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

def process_thumbnail(image_path, text, font_path):
    try:
        img = Image.open(image_path).convert("RGBA")
        width, height = img.size
        
        draw = ImageDraw.Draw(img)
        
        box_width = int(width * MAX_WIDTH_RATIO) - (PADDING * 2)
        box_height = height - (PADDING * 2)
        
        font, lines, line_height, final_size = fit_text_to_box(text, font_path, box_width, box_height)
        
        if not font:
            print(f"Не удалось подобрать шрифт для {image_path}")
            return

        print(f"Шрифт: {final_size}px")

        total_text_height = line_height * len(lines)
        start_y = (height - total_text_height) // 2
        
        # Обводка: уменьшил толщину
        stroke_width = max(3, int(final_size * 0.04))

        for i, line in enumerate(lines):
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

        base, ext = os.path.splitext(image_path)
        if "_preview" in base:
            output_path = image_path
        else:
            output_path = f"{base}_preview{ext}"
            
        img.save(output_path)
        print(f"Сохранено: {output_path}")
            
    except Exception as e:
        print(f"Ошибка: {e}")

def main():
    font_path = get_font_path()
    if not font_path:
        print(f"!!! ОШИБКА !!! Не найден шрифт в {BASE_DIR}")
        return
    
    test_title = "УСТРОИВШИСЬ СИДЕЛКОЙ К МИЛЛИОНЕРУ, Я УЗНАЛА СТРАШНУЮ ТАЙНУ ЕГО НАСЛЕДСТВА!"
    
    files = [f for f in os.listdir(THUMBNAILS_DIR) if f.endswith(('.png', '.jpg')) and '_preview' not in f]
    
    if not files:
        print("Нет картинок.")
        return
        
    for filename in files:
        process_thumbnail(os.path.join(THUMBNAILS_DIR, filename), test_title, font_path)

if __name__ == "__main__":
    main()
