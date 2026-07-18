import logging
from .agent import AndqBotAgent
from .context import ContextManager

logger = logging.getLogger(__name__)


class AndqBotWithMemory(AndqBotAgent):
    """Бот с памятью - использует двухшаговую логику"""
    
    def __init__(self, model_name: str = "qwen2.5-coder-7b-instruct-128k", 
                 lm_studio_url: str = "http://localhost:1234/v1"):
        super().__init__(model_name, lm_studio_url)
        self.memory = ContextManager(max_messages=20)
        logger.info("🧠 Менеджер памяти инициализирован")
    
    def think_and_act_with_memory(self, user_prompt: str) -> str:
        """
        Основной метод для взаимодействия с ботом
        """
        raw_context = self.memory.get_context(user_prompt)
        logger.info(f"📊 Сырой контекст: {len(raw_context)} символов")
        
        response = self.think_and_act(user_prompt, raw_context)
        
        self.memory.save_response(user_prompt, response)
        
        return response