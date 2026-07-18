import os
import re
import json
import requests
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime
from .tools import Tools

logger = logging.getLogger(__name__)


class AndqBotAgent(Tools):
    """
    Агент с двухшаговой LLM-логикой:
    1. Шаг: LLM структурирует сырые данные
    2. Шаг: Исполнение решения LLM
    """
    
    def __init__(self, model_name: str = "qwen2.5-coder-7b-instruct-128k", 
                 lm_studio_url: str = "http://localhost:1234/v1"):
        super().__init__()
        self.model_name = model_name
        self.lm_studio_url = lm_studio_url
        self.pending_delete = None
        
        try:
            response = requests.get(f"{self.lm_studio_url}/models", timeout=2)
            if response.status_code == 200:
                logger.info(f"✅ LM Studio доступна")
            else:
                logger.warning(f"⚠️ LM Studio ответила с кодом {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ LM Studio не отвечает: {e}")
    
    def _get_structurator_prompt(self, raw_data: str) -> str:
        """Возвращает промпт для структуратора данных"""
        return f"""Ты — структуратор запросов для ANDQ Bot.

## ТВОЯ ЗАДАЧА:
Проанализировать ТЕКУЩИЙ запрос пользователя и определить, что он хочет.

## ВХОДНЫЕ ДАННЫЕ:
{raw_data}

## ОПРЕДЕЛИ ИНТЕНШН ПО ТЕКУЩЕМУ ЗАПРОСУ:

ВНИМАТЕЛЬНО посмотри на "ЗАПРОС ПОЛЬЗОВАТЕЛЯ"!

### ВОТ ТОЧНЫЕ ПРИЗНАКИ:

1. **greeting** - только если запрос содержит ТОЛЬКО:
   - "привет", "привет!", "здравствуй", "hello", "hi"
   - НЕ содержит слов "покажи", "создай", "удали", "сколько", "какой"

2. **question** - если запрос содержит:
   - Вопросительные слова: "сколько", "какой", "какая", "какие", "кто", "что", "где", "когда", "почему", "зачем", "как"
   - Или знак "?" в конце

3. **action** - если запрос содержит:
   - "покажи", "посмотри", "список", "найди" → list_files
   - "создай", "запиши" → write_file или create_folder
   - "удали", "удалить", "стереть" → delete_file
   - "прочитай", "открой" → read_file
   - "сколько места", "диск" → get_disk_usage
   - "процессы" → list_processes
   - "логи" → read_log_file
   - "sql", "запрос" → run_sql_query

## ПРИМЕРЫ ПРАВИЛЬНОГО ОПРЕДЕЛЕНИЯ:

| Запрос | Intent | Инструмент |
|--------|--------|------------|
| привет | greeting | null |
| здравствуй | greeting | null |
| покажи файлы | action | list_files |
| сколько файлов? | question | null |
| создай папку test | action | create_folder |
| удали test.txt | action | delete_file |
| сколько места на диске? | question | null (это вопрос, а не команда!) |

## ВЫХОДНОЙ JSON:
{{
  "clean_context": "краткая суть диалога",
  "current_intent": "greeting | question | action | confirmation | unknown",
  "action_tool": "имя_инструмента или null",
  "action_params": {{}} или {{"param": "value"}},
  "response_text": "текст для greeting/question, иначе null",
  "needs_confirmation": false,
  "confidence": 0.0-1.0,
  "summary": "1 предложение о запросе"
}}

## ВАЖНО:
1. СНАЧАЛА посмотри на ТЕКУЩИЙ ЗАПРОС!
2. НЕ путай с историей!
3. "сколько" - это ВСЕГДА вопрос, а не действие!
4. Если запрос содержит "покажи" - это action!
5. Отвечай ТОЛЬКО JSON!
"""
    
    def _clean_text(self, text: str) -> str:
        """Очищает текст от битых символов и мусора"""
        if not text:
            return ""
        
        try:
            text = text.encode('utf-8', errors='ignore').decode('utf-8')
        except:
            text = ""
        
        text = re.sub(r'<\|[^>]+\|>', '', text)
        text = re.sub(r'```[a-z]*\n?', '', text)
        text = re.sub(r'[^\x00-\x7F\x80-\xFF\u0400-\u04FF\n.,!?\-:;()"\' ]', '', text)
        
        return text.strip()
    
    def _call_lm_studio(self, prompt: str, temperature: float = 0.1, max_tokens: int = 300) -> str:
        """Вызов модели через LM Studio"""
        try:
            response = requests.post(
                f"{self.lm_studio_url}/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": "Ты — структуратор запросов. Отвечай ТОЛЬКО JSON. Не используй Markdown."},
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
            clean_content = self._clean_text(content)
            return clean_content
        except Exception as e:
            logger.error(f"❌ Ошибка вызова LM Studio: {e}")
            return ""
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """Извлекает JSON из текста"""
        if not text:
            return None
        
        clean = self._clean_text(text)
        
        # Удаляем маркеры кода
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
        
        # Ищем JSON
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
                        return result
                    except json.JSONDecodeError:
                        continue
        
        match = re.search(r'\{[^{}]*\}', clean)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _collect_raw_data(self, user_prompt: str, context: str = "", files_info: str = "") -> Dict:
        """Собирает все сырые данные"""
        return {
            "user_query": user_prompt,
            "context": context if context else "(контекст пуст)",
            "files": files_info if files_info else "(информация о файлах не запрашивалась)",
            "pending_delete": self.pending_delete if self.pending_delete else "нет",
            "timestamp": datetime.now().isoformat()
        }
    
    def _format_raw_data(self, raw_data: Dict) -> str:
        """Форматирует сырые данные"""
        formatted = "=== ТЕКУЩИЙ ЗАПРОС ===\n"
        formatted += f"{raw_data.get('user_query', '')}\n\n"
        
        formatted += "=== ИСТОРИЯ ДИАЛОГА ===\n"
        formatted += f"{raw_data.get('context', '')}\n\n"
        
        if raw_data.get('files') and raw_data.get('files') != "(информация о файлах не запрашивалась)":
            formatted += "=== ФАЙЛЫ ===\n"
            formatted += f"{raw_data.get('files')}\n"
        
        return formatted
    
    def _is_confirmation(self, text: str) -> bool:
        if not text:
            return False
        text = text.lower().strip()
        return text in ['да', 'yes', 'confirm', 'подтверждаю', 'конечно', 'ок', 'ok', 'да.']
    
    def _is_cancellation(self, text: str) -> bool:
        if not text:
            return False
        text = text.lower().strip()
        return text in ['нет', 'no', 'cancel', 'отмена', 'не надо', 'нет.']
    
    def think_and_act(self, user_prompt: str, context: str = "") -> str:
        """
        Основная логика: двухшаговый подход
        """
        logger.info(f"📝 Запрос: {user_prompt}")
        
        # Проверка подтверждения/отмены
        if self.pending_delete:
            if self._is_confirmation(user_prompt):
                filename = self.pending_delete
                self.pending_delete = None
                try:
                    result = self.delete_file(filename, confirm="yes")
                    return result
                except Exception as e:
                    return f"❌ Ошибка при удалении: {str(e)}"
            elif self._is_cancellation(user_prompt):
                filename = self.pending_delete
                self.pending_delete = None
                return f"✅ Удаление файла '{filename}' отменено."
        
        # Сбор данных
        if len(context) > 3000:
            context = context[:3000] + "..."
        
        files_info = ""
        try:
            files_info = self.list_files()
        except:
            files_info = "(ошибка получения списка файлов)"
        
        raw_data = self._collect_raw_data(user_prompt, context, files_info)
        formatted_raw = self._format_raw_data(raw_data)
        
        logger.info(f"📊 Сырых данных: {len(formatted_raw)} символов")
        
        # LLM структурирует
        structurator_prompt = self._get_structurator_prompt(formatted_raw)
        
        logger.info(f"🧠 Отправляем в LLM...")
        response = self._call_lm_studio(structurator_prompt, temperature=0.1, max_tokens=300)
        
        if not response:
            return "Извините, произошла ошибка при анализе запроса."
        
        logger.info(f"📥 Ответ: {response[:200]}...")
        
        # Парсим JSON
        structured_data = self._extract_json(response)
        
        if not structured_data:
            logger.error(f"❌ Не удалось извлечь JSON")
            return "Извините, я не смог обработать запрос."
        
        logger.info(f"📊 Intent: {structured_data.get('current_intent')}, Tool: {structured_data.get('action_tool')}, Confidence: {structured_data.get('confidence')}")
        
        intent = structured_data.get('current_intent', 'unknown')
        confidence = structured_data.get('confidence', 0.0)
        
        if confidence < 0.5:
            return f"⚠️ Я не уверен (уверенность: {confidence:.0%}).\n{structured_data.get('response_text', 'Попробуйте переформулировать.')}"
        
        if intent == 'greeting':
            return structured_data.get('response_text', 'Привет! Чем могу помочь?')
        
        elif intent == 'question':
            return structured_data.get('response_text', 'Я не нашел ответа.')
        
        elif intent == 'action':
            tool_name = structured_data.get('action_tool')
            params = structured_data.get('action_params', {})
            
            if not tool_name:
                return "Извините, не удалось определить действие."
            
            if not hasattr(self, tool_name):
                return f"❌ Инструмент '{tool_name}' не найден."
            
            no_params_tools = ['list_files', 'get_disk_usage', 'list_processes', 'read_log_file']
            if tool_name in no_params_tools:
                params = {}
            
            if tool_name == 'delete_file':
                filename = params.get('filename')
                if not filename:
                    return "❌ Не указано имя файла"
                if structured_data.get('needs_confirmation', True):
                    self.pending_delete = filename
                    return f"⚠️ Удалить '{filename}'? Введите 'да' или 'нет'"
            
            try:
                logger.info(f"⚙️ Выполняю {tool_name} с {params}")
                result = getattr(self, tool_name)(**params)
                if isinstance(result, str) and len(result) > 500:
                    result = result[:500] + "..."
                return result
            except Exception as e:
                return f"❌ Ошибка: {str(e)}"
        
        else:
            return structured_data.get('response_text', 'Не понял запрос.')
    
    def clear_pending_delete(self) -> None:
        self.pending_delete = None
    
    def get_pending_delete(self) -> Optional[str]:
        return self.pending_delete