import os
import re
import json
import requests
import logging
import inspect
from typing import Dict, List, Optional, Any, Union
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
Ты помогаешь сотрудникам отдела зарплаты и кадров.

## ОСНОВНЫЕ ПРАВИЛА:
1. Будь вежливым и дружелюбным
2. Отвечай кратко и по делу (2-3 предложения)
3. Если пользователь просто общается (приветствие, вопрос, благодарность) — отвечай текстом
4. Если пользователь просит выполнить действие — используй JSON-формат

## КОГДА ИСПОЛЬЗОВАТЬ JSON:
- "покажи файлы" → list_files
- "прочитай файл X" → read_file
- "создай файл X" → write_file
- "удали файл X" → delete_file
- "создай папку X" → create_folder
- "сколько места на диске?" → get_disk_usage
- "покажи процессы" → list_processes
- "покажи логи" → read_log_file
- "выполни SQL запрос" → run_sql_query

## КОГДА ОТВЕЧАТЬ ТЕКСТОМ:
- Приветствия: "привет", "здравствуй"
- Вопросы о боте: "кто ты?", "что ты умеешь?"
- Благодарности: "спасибо"
- Ответы на вопросы пользователя

## ФОРМАТ JSON:
{"tool": "имя_инструмента", "params": {"параметр": "значение"}}

## ВАЖНО:
- Если пользователь просто здоровается — не используй JSON, ответь текстом!
- Не придумывай действия, если пользователь их не просил
- Для удаления всегда используй confirm: "no" и запроси подтверждение

## ПРИМЕРЫ:

Пользователь: привет
Ты: Привет! Чем я могу помочь?

Пользователь: покажи файлы
Ты: {"tool": "list_files", "params": {}}

Пользователь: создай папку docs
Ты: {"tool": "create_folder", "params": {"folder_name": "docs"}}

Пользователь: спасибо
Ты: Пожалуйста! Обращайтесь ещё.

Пользователь: удали файл test.txt
Ты: {"tool": "delete_file", "params": {"filename": "test.txt", "confirm": "no"}}
"""


class AndqBotAgent(Tools):
    """Базовый класс агента с LLM-first логикой"""
    
    def __init__(self, model_name: str = "qwen2.5-coder-7b-instruct-128k", 
                 lm_studio_url: str = "http://localhost:1234/v1"):
        """
        Инициализация агента
        
        Args:
            model_name: Имя модели в LM Studio
            lm_studio_url: URL для подключения к LM Studio
        """
        super().__init__()
        self.model_name = model_name
        self.lm_studio_url = lm_studio_url
        self.system_prompt = load_system_prompt()
        
        # Храним состояние для подтверждений
        self.pending_delete = None
        self.max_context_length = 1500  # Максимальная длина контекста
        self.max_response_length = 150  # Максимальная длина для сжатия
        
        # Проверяем доступность LM Studio
        try:
            response = requests.get(f"{self.lm_studio_url}/models", timeout=2)
            if response.status_code == 200:
                logger.info(f"✅ LM Studio доступна по адресу {self.lm_studio_url}")
            else:
                logger.warning(f"⚠️ LM Studio ответила с кодом {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ LM Studio не отвечает: {e}")
    
    def _call_lm_studio(self, prompt: str, temperature: float = 0.3, 
                        max_tokens: int = 400) -> str:
        """
        Вызов модели через LM Studio с системным промтом
        
        Args:
            prompt: Пользовательский запрос
            temperature: Температура генерации (0.0-1.0)
            max_tokens: Максимальное количество токенов в ответе
        
        Returns:
            Ответ модели или пустая строка при ошибке
        """
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
            return result["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            logger.error("⏱️ Таймаут при вызове LM Studio")
            return ""
        except requests.exceptions.ConnectionError:
            logger.error("🔌 Ошибка подключения к LM Studio")
            return ""
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP ошибка: {e}")
            return ""
        except Exception as e:
            logger.error(f"❌ Ошибка вызова LM Studio: {e}")
            return ""
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """
        Извлекает JSON из текста ответа (один объект)
        
        Args:
            text: Текст с JSON
        
        Returns:
            Словарь с данными или None
        """
        if not text:
            return None
        
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        if clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()
        
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None
    
    def _extract_multiple_json(self, text: str) -> List[Dict]:
        """
        Извлекает все JSON-объекты из текста ответа (включая вложенные)
        
        Args:
            text: Текст с JSON-объектами
        
        Returns:
            Список словарей с данными
        """
        if not text:
            return []
        
        # Очистка от маркеров кода
        clean = text.strip()
        for marker in ["```json", "```", "`"]:
            if clean.startswith(marker):
                clean = clean[len(marker):]
            if clean.endswith(marker):
                clean = clean[:-len(marker)]
        clean = clean.strip()
        
        json_objects = []
        brace_count = 0
        start_idx = -1
        
        for i, char in enumerate(clean):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    try:
                        json_obj = json.loads(clean[start_idx:i+1])
                        json_objects.append(json_obj)
                        start_idx = -1
                    except json.JSONDecodeError:
                        continue
        
        # Если не нашли вложенные, пробуем простой поиск
        if not json_objects:
            matches = re.findall(r'\{[^{}]*\}', clean, re.DOTALL)
            for match in matches:
                try:
                    json_objects.append(json.loads(match))
                except json.JSONDecodeError:
                    continue
        
        return json_objects
    
    def _is_confirmation(self, text: str) -> bool:
        """
        Проверяет, является ли текст подтверждением
        
        Args:
            text: Текст пользователя
        
        Returns:
            True если это подтверждение
        """
        if not text:
            return False
        confirm_words = ['yes', 'да', 'confirm', 'yes!', 'да!', 
                        'удалить', 'подтверждаю', 'да.', 'yes.', 
                        'конечно', 'ок', 'ok', 'ага']
        return text.lower().strip() in confirm_words
    
    def _is_cancellation(self, text: str) -> bool:
        """
        Проверяет, является ли текст отменой
        
        Args:
            text: Текст пользователя
        
        Returns:
            True если это отмена
        """
        if not text:
            return False
        cancel_words = ['нет', 'no', 'отмена', 'cancel', 'не надо', 
                       'нет.', 'no.', 'не', 'не подтверждаю']
        return text.lower().strip() in cancel_words
    
    def _is_conversational(self, text: str) -> bool:
        """
        Проверяет, является ли запрос разговорным (не требующим инструментов)
        
        Args:
            text: Текст запроса
        
        Returns:
            True если это разговорный запрос
        """
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        # Паттерны разговорных запросов
        conversational_patterns = [
            r'^(привет|здравствуй|добрый день|доброе утро|добрый вечер|hi|hello|hey|здарова)',
            r'(кто ты|как тебя зовут|расскажи о себе|что ты умеешь|какие у тебя функции)',
            r'(спасибо|благодарю|thank you|thanks|мерси|спс)',
            r'(как дела|как настроение|как жизнь|how are you|как сам)',
            r'(пока|до свидания|goodbye|bye|всего хорошего|удачи)',
            r'(что ты|ты кто|кто такой|что за бот)',
            r'(помоги|поможешь|help)',
            r'(отлично|хорошо|супер|класс|ok|окей)',
        ]
        
        for pattern in conversational_patterns:
            if re.search(pattern, text_lower):
                return True
        
        # Если текст короткий (1-3 слова) и не содержит глаголов действия
        if len(text.split()) <= 3:
            action_words = ['покажи', 'создай', 'удали', 'прочитай', 'запиши', 'найди', 
                           'выполни', 'скачай', 'загрузи', 'открой', 'закрой', 'очисти']
            if not any(word in text_lower for word in action_words):
                return True
        
        return False
    
    def _validate_tool_call(self, tool_name: str, params: Dict) -> bool:
        """
        Проверяет, что инструмент существует и параметры корректны
        
        Args:
            tool_name: Имя инструмента
            params: Параметры для вызова
        
        Returns:
            True если валидация пройдена
        """
        if not hasattr(self, tool_name):
            logger.error(f"❌ Инструмент '{tool_name}' не найден")
            return False
        
        # Проверка обязательных параметров для некоторых инструментов
        tool_method = getattr(self, tool_name)
        sig = inspect.signature(tool_method)
        
        for param_name, param in sig.parameters.items():
            # Пропускаем self, kwargs и параметры со значениями по умолчанию
            if param_name == 'self' or param_name == 'kwargs':
                continue
            if param.default != inspect.Parameter.empty:
                continue
            if param_name not in params:
                logger.error(f"❌ Отсутствует обязательный параметр: {param_name} для {tool_name}")
                return False
        
        return True
    
    def _humanize_response(self, user_prompt: str, raw_result: str, 
                           max_length: Optional[int] = None) -> str:
        """
        Отправляет сырой результат в LLM для «очеловечивания»
        
        Args:
            user_prompt: Исходный запрос пользователя
            raw_result: Сырой результат от инструмента
            max_length: Максимальная длина ответа (опционально)
        
        Returns:
            Человеко-читаемый ответ
        """
        if not raw_result:
            return "Результат отсутствует."
        
        # Если результат уже краткий и понятный, возвращаем как есть
        if len(raw_result) < 150 and not raw_result.startswith("📊") and not raw_result.startswith("💾"):
            return raw_result
        
        # Для длинных результатов используем LLM
        max_len = max_length or self.max_response_length
        
        prompt = f"""
        Пользователь спросил: "{user_prompt}"
        
        Система вернула данные:
        {raw_result[:1500]}
        
        Перепиши это в понятный, краткий ответ для пользователя (максимум {max_len} символов).
        Если это список — оформи читаемо.
        Если ошибка — объясни понятно.
        Если это успешная операция — сообщи об этом кратко.
        """
        
        try:
            response = self._call_lm_studio(prompt, temperature=0.3, max_tokens=150)
            if response and len(response) < max_len * 2:
                return response
        except Exception as e:
            logger.warning(f"⚠️ Ошибка очеловечивания: {e}")
        
        # Если LLM не справилась, возвращаем сырой результат
        return raw_result
    
    def _get_conversational_response(self, user_prompt: str) -> str:
        """
        Возвращает ответ на разговорный запрос без использования JSON
        
        Args:
            user_prompt: Запрос пользователя
        
        Returns:
            Ответ на разговорный запрос
        """
        text_lower = user_prompt.lower().strip()
        
        # Шаблонные ответы для часто встречающихся запросов
        if re.search(r'^(привет|здравствуй|добрый день|hi|hello|hey)', text_lower):
            return "Привет! Я ANDQ Bot, ваш ИИ-ассистент. Чем могу помочь?"
        
        elif re.search(r'(кто ты|как тебя зовут|что за бот)', text_lower):
            return "Я ANDQ Bot — корпоративный ИИ-ассистент для отдела зарплаты и кадров. Могу работать с файлами, показывать информацию о системе и выполнять SQL-запросы."
        
        elif re.search(r'(что ты умеешь|какие у тебя функции|помоги)', text_lower):
            return "Я умею:\n" \
                   "📂 Работать с файлами (просмотр, чтение, создание, удаление)\n" \
                   "💾 Показывать информацию о диске\n" \
                   "📊 Показывать запущенные процессы\n" \
                   "📝 Читать логи\n" \
                   "🗄️ Выполнять SQL-запросы\n\n" \
                   "Просто скажите, что нужно сделать!"
        
        elif re.search(r'(спасибо|благодарю|thank you|thanks|спс)', text_lower):
            return "Пожалуйста! Обращайтесь ещё, всегда рад помочь!"
        
        elif re.search(r'(пока|до свидания|goodbye|bye|всего хорошего)', text_lower):
            return "До свидания! Всегда на связи, если понадоблюсь."
        
        elif re.search(r'(как дела|как настроение|как жизнь|как сам)', text_lower):
            return "Всё отлично! Готов помочь вам с задачами. Что нужно сделать?"
        
        elif re.search(r'(отлично|хорошо|супер|класс|ok|окей)', text_lower):
            return "Рад, что вам нравится! Если что-то нужно — обращайтесь."
        
        # Если не подошло под шаблоны, но это разговорный запрос
        prompt = f"""
        Пользователь сказал: "{user_prompt}"
        
        Это разговорный запрос. Ответь вежливо и кратко (2-3 предложения).
        НЕ ИСПОЛЬЗУЙ JSON.
        """
        try:
            response = self._call_lm_studio(prompt, temperature=0.5, max_tokens=100)
            if response:
                # Убираем возможные JSON-маркеры
                if response.startswith("```"):
                    lines = response.split('\n')
                    response = '\n'.join(lines[1:-1]) if len(lines) > 2 else response
                return response.strip()
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при генерации разговорного ответа: {e}")
        
        return "Чем могу помочь?"
    
    def _format_context(self, context: Optional[Union[str, Dict]]) -> str:
        """
        Форматирует контекст для отправки в LLM
        
        Args:
            context: Контекст (строка или словарь)
        
        Returns:
            Отформатированная строка контекста
        """
        if not context:
            return ""
        
        if isinstance(context, str):
            return context[:self.max_context_length]
        
        if isinstance(context, dict):
            context_parts = []
            
            if context.get("context"):
                context_parts.append(context.get("context"))
            
            if context.get("last_response"):
                context_parts.append(f"Предыдущий ответ: {context.get('last_response')}")
            
            if context.get("last_query"):
                context_parts.append(f"Последний запрос: {context.get('last_query')}")
            
            combined = "\n".join(context_parts)
            return combined[:self.max_context_length]
        
        return str(context)[:self.max_context_length]
    
    def think_and_act(self, user_prompt: str, context: Optional[Union[str, Dict]] = None) -> str:
        """
        Основная логика: LLM анализирует запрос, выполняет инструмент, очеловечивает результат
        
        Args:
            user_prompt: Запрос пользователя
            context: Контекст диалога (строка или словарь от ContextManager)
        
        Returns:
            Ответ для пользователя
        """
        logger.info(f"📝 Новый запрос: {user_prompt}")
        
        # Проверяем, не является ли это подтверждением или отменой удаления
        if self.pending_delete:
            if self._is_confirmation(user_prompt):
                filename = self.pending_delete
                self.pending_delete = None
                raw_result = self.delete_file(filename, confirm="yes")
                return self._humanize_response(user_prompt, raw_result)
            elif self._is_cancellation(user_prompt):
                filename = self.pending_delete
                self.pending_delete = None
                return f"✅ Удаление файла '{filename}' отменено."
        
        # Проверяем, является ли запрос разговорным
        if self._is_conversational(user_prompt):
            logger.info(f"💬 Разговорный запрос: {user_prompt}")
            return self._get_conversational_response(user_prompt)
        
        # Форматируем контекст
        context_str = self._format_context(context)
        
        # Формируем промт для LLM
        prompt = f"""
        {'Контекст диалога:\n' + context_str if context_str else ''}
        
        Запрос пользователя: "{user_prompt}"
        
        Если запрос требует инструмента — верни JSON строго по формату.
        Если это просто разговор — ответь текстом.
        Если запрос на удаление — верни JSON с confirm="no", я запрошу подтверждение.
        """
        
        logger.info(f"📤 Промт к LLM (первые 200 символов):\n{prompt[:200]}...")
        
        # Вызываем LLM
        response = self._call_lm_studio(prompt, temperature=0.3, max_tokens=400)
        
        if not response:
            return "Извините, произошла ошибка при обращении к модели. Проверьте, запущена ли LM Studio."
        
        logger.info(f"📥 Сырой ответ LLM:\n{response[:200]}...")
        
        # Пробуем извлечь ВСЕ JSON-объекты
        json_objects = self._extract_multiple_json(response)
        
        if json_objects:
            results = []
            
            for json_data in json_objects:
                # Пропускаем, если это не инструмент
                if "tool" not in json_data:
                    continue
                
                tool_name = json_data.get("tool")
                params = json_data.get("params", {})
                
                logger.info(f"🔧 LLM выбрала инструмент: {tool_name} с параметрами: {params}")
                
                # Валидируем вызов
                if not self._validate_tool_call(tool_name, params):
                    results.append(f"❌ Ошибка: инструмент '{tool_name}' не может быть выполнен с такими параметрами")
                    continue
                
                # Для удаления без подтверждения
                if tool_name == "delete_file" and params.get("confirm") != "yes":
                    filename = params.get("filename")
                    if filename:
                        self.pending_delete = filename
                        results.append(f"⚠️ Для удаления файла '{filename}' введите 'да' для подтверждения или 'нет' для отмены.")
                    else:
                        results.append("❌ Ошибка: не указано имя файла для удаления")
                    continue
                
                # Выполняем инструмент
                try:
                    raw_result = getattr(self, tool_name)(**params)
                    final_response = self._humanize_response(user_prompt, raw_result)
                    results.append(final_response)
                    
                except TypeError as e:
                    logger.error(f"❌ Ошибка параметров: {e}")
                    results.append(f"⚠️ Ошибка: не хватает параметров для {tool_name}")
                except Exception as e:
                    logger.error(f"❌ Ошибка выполнения {tool_name}: {e}")
                    results.append(f"❌ Ошибка при выполнении: {str(e)}")
            
            if results:
                return "\n\n".join(results)
        
        # Если JSON не найден или не содержит инструментов — проверяем, не текст ли это
        if response:
            # Убираем возможные JSON-маркеры
            clean_response = response.strip()
            if clean_response.startswith("```") or clean_response.startswith("{"):
                # Если это был JSON, но не удалось распарсить, используем как текст
                if clean_response.startswith("```json"):
                    clean_response = clean_response[7:]
                if clean_response.startswith("```"):
                    clean_response = clean_response[3:]
                if clean_response.endswith("```"):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()
            
            if clean_response:
                logger.info(f"💬 LLM ответила текстом: {clean_response[:100]}...")
                return clean_response
        
        return "Извините, я не смог обработать ваш запрос."
    
    def clear_pending_delete(self) -> None:
        """Очищает состояние ожидающего удаления"""
        self.pending_delete = None
    
    def get_pending_delete(self) -> Optional[str]:
        """
        Возвращает имя файла, ожидающего подтверждения удаления
        
        Returns:
            Имя файла или None
        """
        return self.pending_delete
    
    def set_model(self, model_name: str) -> None:
        """
        Устанавливает новую модель
        
        Args:
            model_name: Имя модели
        """
        self.model_name = model_name
        logger.info(f"🔄 Модель изменена на: {model_name}")
    
    def set_lm_studio_url(self, url: str) -> None:
        """
        Устанавливает новый URL для LM Studio
        
        Args:
            url: Новый URL
        """
        self.lm_studio_url = url
        logger.info(f"🔄 URL LM Studio изменен на: {url}")
        
        # Проверяем доступность
        try:
            requests.get(f"{self.lm_studio_url}/models", timeout=2)
            logger.info(f"✅ LM Studio доступна по новому адресу")
        except:
            logger.warning(f"⚠️ LM Studio не отвечает по новому адресу")