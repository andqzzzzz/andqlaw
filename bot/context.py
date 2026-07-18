import os
import json
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)


class ContextManager:
    """
    Управление контекстом диалога.
    Теперь просто хранит сырые данные, а структурирует их LLM.
    """
    
    def __init__(self, context_dir: str = "conversations", max_messages: int = 20):
        self.context_dir = context_dir
        self.max_messages = max_messages
        self.state_file = os.path.join(context_dir, "current_state.json")
        self.history_dir = os.path.join(context_dir, "history")
        
        os.makedirs(context_dir, exist_ok=True)
        os.makedirs(self.history_dir, exist_ok=True)
        
        self.state = self._load_state()
    
    def _clean_text(self, text: str) -> str:
        """Базовая очистка текста"""
        if not text:
            return ""
        text = text.encode('utf-8', errors='ignore').decode('utf-8')
        return text.strip()
    
    def _load_state(self) -> dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "messages" not in data:
                        data["messages"] = []
                    return data
            except Exception as e:
                logger.warning(f"Не удалось загрузить состояние: {e}")
        
        return {"messages": [], "last_updated": datetime.now().isoformat()}
    
    def _save_state(self) -> None:
        try:
            self.state["last_updated"] = datetime.now().isoformat()
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Не удалось сохранить состояние: {e}")
    
    def _save_history(self) -> None:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            history_file = os.path.join(self.history_dir, f"{timestamp}.json")
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Не удалось сохранить историю: {e}")
    
    def get_context(self, user_prompt: str) -> str:
        """
        Возвращает СЫРУЮ историю диалога.
        Вся структуризация будет делаться LLM.
        """
        messages = self.state.get("messages", [])
        
        if not messages:
            return "Диалог только начинается."
        
        history_lines = []
        for msg in messages[-self.max_messages:]:
            role = "Пользователь" if msg["role"] == "user" else "Ассистент"
            content = self._clean_text(msg["content"])
            if content:
                history_lines.append(f"{role}: {content}")
        
        return "\n".join(history_lines)
    
    def save_response(self, user_prompt: str, response: str) -> None:
        """Сохраняет диалог"""
        self._save_history()
        
        messages = self.state.get("messages", [])
        
        messages.append({"role": "user", "content": user_prompt})
        messages.append({"role": "assistant", "content": response[:1000]})
        
        if len(messages) > self.max_messages * 2:
            messages = messages[-self.max_messages * 2:]
        
        self.state["messages"] = messages
        self._save_state()
        
        logger.info(f"📊 Сообщений в истории: {len(messages)}")