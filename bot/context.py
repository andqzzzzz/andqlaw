import json
import os
from datetime import datetime
from typing import Dict


class ContextManager:
    """Управление контекстом через файлы (сжатие при переполнении)"""
    
    def __init__(self, conv_dir="conversations", max_chars=4000):
        self.conv_dir = conv_dir
        self.history_dir = os.path.join(conv_dir, "history")
        self.state_file = os.path.join(conv_dir, "current_state.json")
        self.max_chars = max_chars
        
        os.makedirs(self.history_dir, exist_ok=True)
        os.makedirs(conv_dir, exist_ok=True)
        
        if not os.path.exists(self.state_file):
            self._save_state({"context": "", "last_response": "", "timestamp": ""})
    
    def _load_state(self) -> Dict:
        with open(self.state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_state(self, data: Dict):
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _save_history(self, state: Dict):
        filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
        path = os.path.join(self.history_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def get_context(self, user_query: str) -> str:
        state = self._load_state()
        old_context = state.get("context", "")
        last_response = state.get("last_response", "")
        
        full_context = f"{old_context}\n\nПоследний ответ: {last_response}\n\nНовый запрос: {user_query}"
        
        if len(full_context) > self.max_chars:
            compressed = old_context[-(self.max_chars // 2):] if len(old_context) > self.max_chars // 2 else old_context
            full_context = f"{compressed}\n\nПоследний ответ: {last_response}\n\nНовый запрос: {user_query}"
        
        return full_context
    
    def save_response(self, user_query: str, bot_response: str):
        old_state = self._load_state()
        self._save_history(old_state)
        
        new_context = f"{old_state.get('context', '')}\n\nПользователь: {user_query}\nБот: {bot_response}"
        
        if len(new_context) > self.max_chars:
            new_context = new_context[-self.max_chars:]
        
        self._save_state({
            "context": new_context,
            "last_response": bot_response,
            "timestamp": datetime.now().isoformat()
        })