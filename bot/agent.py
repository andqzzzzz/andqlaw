import os
import re
import json
import requests
import logging
from typing import Dict, Optional, Any
from .tools import Tools

logger = logging.getLogger(__name__)


def load_system_prompt() -> str:
    """Загружает системный промт из файла"""
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths_to_try = [
        os.path.join(script_dir, "system_prompt.txt"),
        os.path.join(script_dir, "conversations", "system_prompt.txt"),
        "system_prompt.txt",
    ]
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    logger.info(f"✅ Системный промт загружен из {path}")
                    return f.read()
            except Exception as e:
                logger.warning(f"Не удалось прочитать {path}: {e}")
                continue
    logger.error("❌ Файл system_prompt.txt не найден!")
    return """Ты — ANDQ Bot, корпоративный ИИ-ассистент.

## ТВОЯ РОЛЬ:
Ты помогаешь сотрудникам отдела зарплаты и кадров. Ты вежливый, дружелюбный и отвечаешь кратко.

## ФОРМАТ ОТВЕТА:
1. Если пользователь просит выполнить действие — отвечай ТОЛЬКО JSON:
   {"tool": "имя_инструмента", "params": {"параметр": "значение"}}

2. Если пользователь просто общается — отвечай обычным текстом (без JSON)

## ДОСТУПНЫЕ ИНСТРУМЕНТЫ:
- list_files: показать файлы в песочнице (params: {})
- read_file: прочитать файл (params: {"filename": "имя"})
- write_file: создать/перезаписать файл (params: {"filename": "имя", "content": "текст"})
- delete_file: удалить файл (params: {"filename": "имя", "confirm": "no"})
- create_folder: создать папку (params: {"folder_name": "имя"})
- get_disk_usage: показать место на диске (params: {})
- list_processes: показать запущенные процессы (params: {})
- read_log_file: показать логи (params: {})
- run_sql_query: выполнить SQL запрос (params: {"query": "SELECT..."})

## ПРИМЕРЫ:
Пользователь: привет
Ты: Привет! Я ANDQ Bot. Чем могу помочь?

Пользователь: покажи файлы
Ты: {"tool": "list_files", "params": {}}

Пользователь: создай файл test.txt с текстом привет
Ты: {"tool": "write_file", "params": {"filename": "test.txt", "content": "привет"}}

Пользователь: сколько места на диске?
Ты: {"tool": "get_disk_usage", "params": {}}

Пользователь: удали файл test.txt
Ты: {"tool": "delete_file", "params": {"filename": "test.txt", "confirm": "no"}}

## ВАЖНО:
- Для list_files, get_disk_usage, list_processes, read_log_file параметры ВСЕГДА {}
- Для delete_file ВСЕГДА используй confirm: "no"
- Отвечай ТОЛЬКО JSON или ТОЛЬКО текстом. Без смешивания.
"""


class AndqBotAgent(Tools):
    """Агент, который всегда использует LLM для принятия решений"""
    
    def __init__(self, model_name: str = "qwen2.5-coder-7b-instruct-128k", 
                 lm_studio_url: str = "http://localhost:1234/v1"):
        super().__init__()
        self.model_name = model_name
        self.lm_studio_url = lm_studio_url
        self.system_prompt = load_system_prompt()
        self.pending_delete = None
        
        try:
            response = requests.get(f"{self.lm_studio_url}/models", timeout=2)
            if response.status_code == 200:
                logger.info(f"✅ LM Studio доступна")
            else:
                logger.warning(f"⚠️ LM Studio ответила с кодом {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ LM Studio не отвечает: {e}")
    
    def _call_lm_studio(self, prompt: str, temperature: float = 0.3, max_tokens: int = 300) -> str:
        """Вызов модели через LM Studio с системным промтом"""
        try:
            response = requests.post(
                f"{self.lm_studio_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return content.strip()
        except Exception as e:
            logger.error(f"❌ Ошибка вызова LM Studio: {e}")
            return ""
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """Извлекает JSON из текста"""
        if not text:
            return None
        
        # Очищаем от маркеров кода
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
        
        # Ищем JSON с учетом вложенности
        brace_count = 0
        start = -1
        
        for i, ch in enumerate(clean):
            if ch == '{':
                if brace_count == 0:
                    start = i
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0 and start != -1:
                    try:
                        json_str = clean[start:i+1]
                        result = json.loads(json_str)
                        if isinstance(result, dict) and "tool" in result:
                            return result
                    except json.JSONDecodeError:
                        continue
        
        # Если не нашли, пробуем простой поиск
        match = re.search(r'\{[^{}]*\}', clean)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, dict) and "tool" in result:
                    return result
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _is_confirmation(self, text: str) -> bool:
        """Проверяет, является ли текст подтверждением"""
        if not text:
            return False
        confirm_words = ['да', 'yes', 'confirm', 'подтверждаю', 'конечно', 'ок', 'ok']
        return text.lower().strip() in confirm_words
    
    def _is_cancellation(self, text: str) -> bool:
        """Проверяет, является ли текст отменой"""
        if not text:
            return False
        cancel_words = ['нет', 'no', 'cancel', 'отмена', 'не надо']
        return text.lower().strip() in cancel_words
    
    def think_and_act(self, user_prompt: str, context: str = "") -> str:
        """
        Основная логика: ВСЕГДА отправляем запрос в LLM
        """
        logger.info(f"📝 Запрос: {user_prompt}")
        
        # Проверка подтверждения удаления
        if self.pending_delete:
            if self._is_confirmation(user_prompt):
                filename = self.pending_delete
                self.pending_delete = None
                logger.info(f"✅ Подтверждено удаление: {filename}")
                try:
                    result = self.delete_file(filename, confirm="yes")
                    return result
                except Exception as e:
                    return f"❌ Ошибка при удалении: {str(e)}"
            elif self._is_cancellation(user_prompt):
                filename = self.pending_delete
                self.pending_delete = None
                return f"✅ Удаление файла '{filename}' отменено."
        
        # Формируем промт
        prompt = f"""
        {f'Контекст диалога:\n{context}' if context else ''}
        
        Запрос пользователя: "{user_prompt}"
        
        ОТВЕТЬ ТОЛЬКО:
        - JSON если нужно действие
        - Текст если это разговор
        """
        
        logger.info(f"📤 Промт к LLM (первые 300 символов):\n{prompt[:300]}...")
        
        # ВСЕГДА вызываем LLM
        response = self._call_lm_studio(prompt, temperature=0.3, max_tokens=300)
        
        if not response:
            return "Извините, произошла ошибка при обращении к модели."
        
        logger.info(f"📥 Сырой ответ LLM: {response[:200]}...")
        
        # Пробуем извлечь JSON
        json_data = self._extract_json(response)
        
        if json_data and "tool" in json_data:
            tool_name = json_data.get("tool")
            params = json_data.get("params", {})
            
            logger.info(f"🔧 LLM выбрала инструмент: {tool_name} с параметрами: {params}")
            
            # Проверяем существование инструмента
            if not hasattr(self, tool_name):
                return f"❌ Инструмент '{tool_name}' не найден."
            
            # Очищаем params для инструментов без параметров
            no_params_tools = ['list_files', 'get_disk_usage', 'list_processes', 'read_log_file']
            if tool_name in no_params_tools:
                params = {}
                logger.info(f"🧹 Очищены параметры для {tool_name}")
            
            # Обработка удаления
            if tool_name == "delete_file":
                filename = params.get("filename")
                if not filename:
                    return "❌ Не указано имя файла для удаления"
                
                if params.get("confirm") != "yes":
                    self.pending_delete = filename
                    return f"⚠️ Для удаления файла '{filename}' введите 'да' для подтверждения или 'нет' для отмены."
            
            # Выполняем инструмент
            try:
                logger.info(f"⚙️ Выполняю {tool_name} с параметрами: {params}")
                result = getattr(self, tool_name)(**params)
                
                if isinstance(result, str) and len(result) > 500:
                    result = result[:500] + "..."
                
                return result
            except TypeError as e:
                logger.error(f"❌ Ошибка параметров: {e}")
                return f"⚠️ Ошибка: неверные параметры для {tool_name}"
            except Exception as e:
                logger.error(f"❌ Ошибка выполнения {tool_name}: {e}")
                return f"❌ Ошибка: {str(e)}"
        
        # Если это не JSON - возвращаем как текстовый ответ
        logger.info(f"💬 Текстовый ответ от LLM")
        return response
    
    def clear_pending_delete(self) -> None:
        """Очищает состояние ожидающего удаления"""
        self.pending_delete = None
    
    def get_pending_delete(self) -> Optional[str]:
        """Возвращает имя файла, ожидающего подтверждения удаления"""
        return self.pending_delete