import os
import json
import logging
from datetime import datetime
from .agent import AndqBotAgent

logger = logging.getLogger(__name__)


class ContextManager:
    """Управление контекстом диалога"""
    
    def __init__(self, context_dir: str = "conversations"):
        self.context_dir = context_dir
        self.state_file = os.path.join(context_dir, "current_state.json")
        self.history_dir = os.path.join(context_dir, "history")
        
        # Создаем директории
        os.makedirs(context_dir, exist_ok=True)
        os.makedirs(self.history_dir, exist_ok=True)
        
        # Загружаем состояние
        self.state = self._load_state()
    
    def _load_state(self) -> dict:
        """Загружает состояние из файла"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Не удалось загрузить состояние: {e}")
        
        return {
            "context": "",
            "last_response": "",
            "last_query": "",
            "timestamp": ""
        }
    
    def _save_state(self) -> None:
        """Сохраняет состояние в файл"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Не удалось сохранить состояние: {e}")
    
    def _save_history(self) -> None:
        """Сохраняет копию состояния в историю"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            history_file = os.path.join(self.history_dir, f"{timestamp}.json")
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Не удалось сохранить историю: {e}")
    
    def _summarize_response(self, response: str, max_length: int = 200) -> str:
        """Сжимает ответ до максимальной длины"""
        if len(response) <= max_length:
            return response
        return response[:max_length] + "..."
    
    def get_context(self, user_prompt: str) -> str:
        """
        Возвращает контекст для LLM
        
        Args:
            user_prompt: Текущий запрос пользователя
        
        Returns:
            Строка с контекстом
        """
        # Обновляем состояние
        self.state["last_query"] = user_prompt
        self.state["timestamp"] = datetime.now().isoformat()
        
        # Формируем контекст
        context_parts = []
        
        if self.state.get("context"):
            context_parts.append(self.state["context"])
        
        if self.state.get("last_response"):
            context_parts.append(f"Предыдущий ответ: {self.state['last_response']}")
        
        return "\n".join(context_parts)
    
    def save_response(self, user_prompt: str, response: str) -> None:
        """
        Сохраняет ответ в контекст
        
        Args:
            user_prompt: Запрос пользователя
            response: Ответ бота
        """
        # Сохраняем в историю перед обновлением
        self._save_history()
        
        # Обновляем состояние
        self.state["last_response"] = self._summarize_response(response)
        self.state["last_query"] = user_prompt
        self.state["timestamp"] = datetime.now().isoformat()
        
        # Обновляем контекст
        new_entry = f"Пользователь: {user_prompt} → {self.state['last_response']}"
        old_context = self.state.get("context", "")
        
        # Ограничиваем размер контекста (последние 10 сообщений)
        lines = old_context.split("\n") if old_context else []
        lines.append(new_entry)
        if len(lines) > 10:
            lines = lines[-10:]
        
        self.state["context"] = "\n".join(lines)
        
        # Сохраняем состояние
        self._save_state()
        
        logger.info(f"📊 Размер контекста: {len(self.state['context'])} символов")


class AndqBotWithMemory(AndqBotAgent):
    """Бот с памятью"""
    
    def __init__(self, model_name: str = "qwen2.5-coder-7b-instruct-128k", 
                 lm_studio_url: str = "http://localhost:1234/v1"):
        super().__init__(model_name, lm_studio_url)
        self.memory = ContextManager()
        logger.info("🧠 Менеджер памяти инициализирован")
    
    def think_and_act_with_memory(self, user_prompt: str) -> str:
        """
        Основной метод для взаимодействия с ботом
        
        Args:
            user_prompt: Запрос пользователя
        
        Returns:
            Ответ бота
        """
        # Получаем контекст
        context = self.memory.get_context(user_prompt)
        
        # Получаем ответ от агента
        response = self.think_and_act(user_prompt, context)
        
        # Сохраняем диалог в память
        self.memory.save_response(user_prompt, response)
        
        return response