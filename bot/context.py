import json
import os
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class ContextManager:
    """Управление контекстом с защитой от битых файлов"""
    
    def __init__(self, conv_dir="conversations", max_chars=2000):
        self.conv_dir = conv_dir
        self.history_dir = os.path.join(conv_dir, "history")
        self.state_file = os.path.join(conv_dir, "current_state.json")
        self.max_chars = max_chars
        
        os.makedirs(self.history_dir, exist_ok=True)
        os.makedirs(conv_dir, exist_ok=True)
        
        # Создаём файл, если его нет
        if not os.path.exists(self.state_file):
            self._save_state({"context": "", "last_response": "", "timestamp": ""})
    
    def _load_state(self) -> Dict:
        """Загружает состояние, создаёт новое, если файл битый или пустой"""
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    raise ValueError("Файл пустой")
                return json.loads(content)
        except (json.JSONDecodeError, ValueError, FileNotFoundError) as e:
            logger.warning(f"⚠️ Ошибка загрузки контекста: {e}. Создаю новый.")
            default_state = {"context": "", "last_response": "", "timestamp": ""}
            self._save_state(default_state)
            return default_state
    
    def _save_state(self, data: Dict):
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _save_history(self, state: Dict):
        filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
        path = os.path.join(self.history_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    
    def _summarize_response(self, response: str, max_len: int = 150) -> str:
        """Сжимает ответ до краткого резюме"""
        if not response:
            return ""
        
        # Убираем эмодзи и лишние переносы
        clean = response.replace('\n', ' ').strip()
        
        # Если ответ короче лимита — возвращаем как есть
        if len(clean) <= max_len:
            return clean
        
        # Ищем ключевую информацию
        lines = response.split('\n')
        summary_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Пропускаем строки с большими блоками данных
            if len(line) > 80:
                continue
            # Пропускаем строки, похожие на данные процессов или таблиц
            if any(x in line for x in ['ЉЃ', 'КБ', 'МБ', '.exe', '.txt', 'PID', 'Total']):
                continue
            if len(summary_lines) < 3:
                summary_lines.append(line)
        
        if summary_lines:
            result = ' '.join(summary_lines)
            if len(result) <= max_len:
                return result
            return result[:max_len] + "..."
        
        # Если не удалось извлечь ключевую информацию — просто обрезаем
        return clean[:max_len] + "..."
    
    def get_context(self, user_query: str) -> str:
        """Возвращает сжатый контекст для LLM"""
        state = self._load_state()
        old_context = state.get("context", "")
        last_response = state.get("last_response", "")
        
        # Собираем контекст
        full_context = f"{old_context}\n\nПоследний ответ: {last_response}\n\nНовый запрос: {user_query}"
        
        # Ограничиваем размер
        if len(full_context) > self.max_chars:
            # Берём последнюю половину
            compressed = old_context[-(self.max_chars // 2):] if len(old_context) > self.max_chars // 2 else old_context
            full_context = f"{compressed}\n\nПоследний ответ: {last_response}\n\nНовый запрос: {user_query}"
        
        logger.info(f"📊 Размер контекста: {len(full_context)} символов")
        return full_context
    
    def save_response(self, user_query: str, bot_response: str, raw_result: str = ""):
        """
        Сохраняет ответ в контекст с сжатием
        
        Аргументы:
            user_query: запрос пользователя
            bot_response: финальный ответ бота (уже человекочитаемый)
            raw_result: сырой результат от инструмента (для сжатия)
        """
        old_state = self._load_state()
        self._save_history(old_state)
        
        # Если есть сырой результат — сжимаем его
        if raw_result:
            summary = self._summarize_response(raw_result)
            context_entry = f"Пользователь: {user_query} → {summary}"
        else:
            # Если нет сырого результата — сжимаем сам ответ
            summary = self._summarize_response(bot_response)
            context_entry = f"Пользователь: {user_query} → {summary}"
        
        # Добавляем к существующему контексту
        new_context = f"{old_state.get('context', '')}\n{context_entry}".strip()
        
        # Ограничиваем размер
        if len(new_context) > self.max_chars:
            # Берём последние self.max_chars символов
            new_context = new_context[-self.max_chars:]
        
        self._save_state({
            "context": new_context,
            "last_response": self._summarize_response(bot_response, max_len=100),
            "last_query": user_query,
            "timestamp": datetime.now().isoformat()
        })