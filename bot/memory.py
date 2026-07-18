from .agent import AndqBotAgent
from .context import ContextManager


class AndqBotWithMemory(AndqBotAgent):
    """Бот с памятью через файлы"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.memory = ContextManager(max_chars=4000)
    
    def think_and_act_with_memory(self, user_prompt: str) -> str:
        context = self.memory.get_context(user_prompt)
        response = self.think_and_act(user_prompt, context)
        self.memory.save_response(user_prompt, response)
        return response