"""
Translation Module
Translates news to Arabic
"""

from deep_translator import GoogleTranslator
import config
import concurrent.futures

class Translator:
    def __init__(self):
        if config.TRANSLATION_ENABLED:
            try:
                self.translator = GoogleTranslator(
                    source=config.TRANSLATION_SOURCE_LANG,
                    target=config.TRANSLATION_TARGET_LANG
                )
            except:
                self.translator = None
        else:
            self.translator = None
    
    def translate(self, text: str) -> str:
        """Translate text to Arabic"""
        if not text or len(text.strip()) == 0:
            return ""
        
        if not self.translator:
            return text  # Return original if translator not available
        
        try:
            # Limit length
            text_to_translate = text[:config.TRANSLATION_MAX_LENGTH]

            # Hard time budget (translation providers can hang on network I/O)
            def _do_translate():
                return self.translator.translate(text_to_translate)

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_do_translate)
                translated = fut.result(timeout=float(getattr(config, 'TRANSLATION_TIMEOUT_SECONDS', 8)))
            return translated
            
        except Exception as e:
            print(f"Translation error: {e}")
            return text  # Return original on error
    
    def translate_news(self, news_item: dict) -> dict:
        """Translate news title and body"""
        news_item['title_ar'] = self.translate(news_item.get('title_en', ''))
        
        body_en = news_item.get('body_en', '')
        if body_en:
            news_item['body_ar'] = self.translate(body_en)
        else:
            news_item['body_ar'] = ''
        
        return news_item


# Singleton
_translator = None

def get_translator() -> Translator:
    """Get translator instance"""
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator
