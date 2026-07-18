from .agent import AndqBotAgent
from .context import ContextManager
import logging

logger = logging.getLogger(__name__)


class AndqBotWithMemory(AndqBotAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.memory = ContextManager(max_chars=2000)
    
    def think_and_act_with_memory(self, user_prompt: str) -> str:
        try:
            context = self.memory.get_context(user_prompt)
            response = self.think_and_act(user_prompt, context)
            
            # Сохраняем в контекст
            self.memory.save_response(user_prompt, response)
            
            return response
        except Exception as e:
            logger.error(f"Ошибка в think_and_act_with_memory: {e}")
            return f"Извините, произошла ошибка: {e}"