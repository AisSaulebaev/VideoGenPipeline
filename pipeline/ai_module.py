import os
import json
import logging
import requests
import random
from openai import OpenAI
from config import OPENAI_API_KEY, THUMBNAILS_DIR

logger = logging.getLogger("AIModule")

class AIModule:
    # 20 вариантов внешности (девушки 20-35 лет)
    APPEARANCE_OPTIONS = [
        "Beautiful young woman age 25-30 with long dark wavy hair",
        "Stunning blonde woman age 20-25 with straight hair",
        "Elegant woman age 28-35 with shoulder-length chestnut hair",
        "Attractive redhead woman age 24-29 with natural look",
        "Young woman age 22-27 with messy bun hairstyle",
        "Serious woman age 30 with sharp features and dark eyes",
        "Cute woman age 23 with curly brown hair",
        "Sophisticated woman age 32 with a platinum blonde bob cut",
        "Mysterious woman age 26 with long black hair and bangs",
        "Friendly woman age 24 with light brown hair in a high ponytail",
        "Stylish woman age 27 with dark brown hair and caramel highlights",
        "Gentle woman age 25 with ash blonde wavy hair",
        "Bold woman age 21 with a short dark pixie cut",
        "Charming woman age 29 with long red hair and loose curls",
        "Focused woman age 31 with honey blonde hair tied back",
        "Traditional woman age 28 with long black hair in a braid",
        "Modern woman age 26 with brown hair and a side part",
        "Natural beauty age 22 with dirty blonde windblown hair",
        "Smart woman age 33 with dark hair and glasses",
        "Soft woman age 25 with fair hair and gentle waves"
    ]

    # 20 вариантов одежды (верхняя одежда, кэжуал)
    CLOTHING_OPTIONS = [
        "wears elegant beige coat and black turtleneck",
        "wearing a stylish black leather jacket",
        "dressed in a cozy white knitted sweater",
        "wearing a formal dark blue business blazer",
        "dressed in a casual grey hoodie",
        "wearing a modern brown trench coat",
        "in a simple black dress",
        "wearing a denim jacket over a white t-shirt",
        "dressed in a warm burgundy oversized sweater",
        "wearing a classic grey wool coat",
        "in a crisp white shirt and a black vest",
        "wearing a practical green parka jacket",
        "wrapped in a red scarf over a black coat",
        "wearing a casual blue denim shirt",
        "dressed in a soft cream cardigan",
        "wearing a black zip-up hoodie",
        "in a comfortable plaid flannel shirt",
        "wearing a navy blue peacoat",
        "dressed in a delicate white blouse with a collar",
        "wearing a sleek dark grey turtleneck"
    ]

    def __init__(self):
        if not OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not found!")
            
        self.client = OpenAI(api_key=OPENAI_API_KEY)
            
        if not os.path.exists(THUMBNAILS_DIR):
            os.makedirs(THUMBNAILS_DIR, exist_ok=True)

    def generate_metadata(self, text: str):
        """
        Генерирует только описание.
        """
        prompt = """
        You are an expert YouTube strategist for a channel like "Historii Navsegda" (Stories Forever).
        
        Task:
        Create a SEO-optimized Description (Russian language). Include a short summary and tags.
        
        Return JSON format:
        {
            "description": "..."
        }
        """
        
        try:
            context_text = text[:8000]
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Story text:\n{context_text}"}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error generating metadata: {e}")
            return None

    def generate_thumbnail(self, title: str, task_id: int) -> str:
        """
        Генерирует превью через Selenium (AI Studio App).
        """
        final_filename = f"thumb_{task_id}.png"
        final_path = os.path.join(THUMBNAILS_DIR, final_filename)
            
        try:
            # Выбираем случайную внешность и одежду
            appearance = random.choice(self.APPEARANCE_OPTIONS)
            clothing = random.choice(self.CLOTHING_OPTIONS)
            
            logger.info(f"[AIModule] Selected style: {appearance}, {clothing}")

            # Формируем промпт
            image_prompt = f"""YouTube thumbnail: {appearance} positioned on the FAR RIGHT side of the frame, standing in blurred urban evening background with bokeh lights. Woman is closer to the right edge, upper body visible, looking directly at camera with emotional serious expression. She {clothing}. Background is blurred city street with warm golden bokeh lights. LEFT 60% of image has burgundy to dark red gradient overlay that GRADUALLY FADES and blends into the photo towards the right. Smooth transparent transition from solid burgundy color on far left to fully visible photo on right side. Soft gradient mask creating natural blend. Woman should be positioned more to the right to leave maximum space on left for text. Professional cinematic lighting. 16:9 YouTube thumbnail format. No text."""
            
            logger.info(f"[AIModule] Generating thumbnail via Selenium (AI Studio App)...")
            
            # Импортируем и используем Selenium генератор
            from pipeline.selenium_generator import SeleniumImageGenerator
            sel_gen = SeleniumImageGenerator()
            
            # Запускает браузер и ждет ввода пользователя в консоли (или авто если уже открыт)
            success = sel_gen.generate_image(image_prompt, final_path)
            
            if success:
                logger.info(f"[AIModule] ✅ Background saved: {final_path}")
                
                # Добавляем текст (название видео)
                if title:
                    logger.info(f"[AIModule] Adding text: {title}...")
                    try:
                        from pipeline.thumbnail_text import add_text_to_image
                        if add_text_to_image(final_path, title):
                            logger.info("[AIModule] ✅ Text added successfully.")
                        else:
                            logger.warning("[AIModule] ⚠️ Failed to add text.")
                    except Exception as e:
                        logger.error(f"[AIModule] Error adding text: {e}")
                else:
                    logger.warning("[AIModule] No title provided for text overlay.")
                
                return final_path
            else:
                logger.error("[AIModule] Selenium generation failed.")
                return None
            
        except Exception as e:
            logger.error(f"Error generating thumbnail: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
