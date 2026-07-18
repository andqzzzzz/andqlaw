import os
import requests
import logging
from .tools import Tools

logger = logging.getLogger(__name__)


def load_system_prompt() -> str:
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
Ты вежливый и отвечаешь кратко.
Ты помнишь предыдущие сообщения пользователя."""


class AndqBotAgent(Tools):
    def __init__(self, model_name="qwen2.5-coder-7b-instruct-128k", lm_studio_url="http://localhost:1234/v1"):
        super().__init__()
        self.model_name = model_name
        self.lm_studio_url = lm_studio_url
        self.system_prompt = load_system_prompt()
        
        # ===== КЛЮЧЕВЫЕ СЛОВА ДЛЯ ОПРЕДЕЛЕНИЯ ИНСТРУМЕНТОВ =====
        self.tool_keywords = {
            "создай папку": "create_folder",
            "новую папку": "create_folder",
            "создай файл": "write_file",
            "запиши в файл": "write_file",
            "сохрани в файл": "write_file",
            "прочитай файл": "read_file",
            "открой файл": "read_file",
            "удали файл": "delete_file",
            "покажи файлы": "list_files",
            "содержимое": "read_file",
            "файл": "list_files",
            "файлы": "list_files",
            "папк": "list_files",
            "каталог": "list_files",
            "процесс": "list_processes",
            "задача": "list_processes",
            "tasklist": "list_processes",
            "ps": "list_processes",
            "диск": "get_disk_usage",
            "место": "get_disk_usage",
            "space": "get_disk_usage",
            "логи": "read_log_file",
            "log": "read_log_file",
            "sql": "run_sql_query",
            "зарплат": "run_sql_query",
            "select": "run_sql_query"
        }
        
        try:
            requests.get(f"{self.lm_studio_url}/models", timeout=2)
            logger.info(f"✅ LM Studio доступна по адресу {self.lm_studio_url}")
        except:
            logger.warning("⚠️ LM Studio не отвечает!")
    
    def _call_lm_studio(self, prompt: str, temperature: float = 0.7) -> str:
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
                    "max_tokens": 300,
                    "stream": False
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Ошибка вызова LM Studio: {e}")
            return "Извините, произошла ошибка при обращении к модели."
    
    # ========== ОПРЕДЕЛЕНИЕ ИНТЕНТА С ИЗВЛЕЧЕНИЕМ ПАРАМЕТРОВ ==========
    def detect_tool(self, user_prompt: str) -> tuple:
        """Определяет инструмент и извлекает параметры из текста"""
        prompt_lower = user_prompt.lower()
        
        # Проверяем все ключевые слова
        for keyword, tool_name in self.tool_keywords.items():
            if keyword in prompt_lower:
                params = {}
                
                # ===== ДЛЯ СОЗДАНИЯ ПАПКИ =====
                if tool_name == "create_folder":
                    # Ищем имя папки в кавычках или после слова "папку"
                    import re
                    match = re.search(r'["\']([^"\']+)["\']', user_prompt)
                    if match:
                        params["folder_name"] = match.group(1)
                    else:
                        # Берём последнее слово после "папку"
                        words = user_prompt.split()
                        for i, word in enumerate(words):
                            if word.lower() in ["папку", "папка", "folder"] and i + 1 < len(words):
                                params["folder_name"] = words[i + 1].strip('"\'')
                                break
                        if "folder_name" not in params:
                            params["folder_name"] = ""
                
                # ===== ДЛЯ СОЗДАНИЯ ФАЙЛА =====
                elif tool_name == "write_file":
                    import re
                    # Ищем имя файла в кавычках
                    match = re.search(r'["\']([^"\']+)["\']', user_prompt)
                    if match:
                        params["filename"] = match.group(1)
                    else:
                        # Берём слово после "файл"
                        words = user_prompt.split()
                        for i, word in enumerate(words):
                            if word.lower() in ["файл", "file"] and i + 1 < len(words):
                                params["filename"] = words[i + 1].strip('"\'').strip()
                                break
                        if "filename" not in params:
                            params["filename"] = ""
                    
                    # Ищем content
                    if "content=" in user_prompt:
                        content_match = re.search(r'content=[\'"]([^\'"]*)[\'"]', user_prompt)
                        if content_match:
                            params["content"] = content_match.group(1)
                        else:
                            content_match = re.search(r'content=([^\s]+)', user_prompt)
                            if content_match:
                                params["content"] = content_match.group(1)
                    else:
                        params["content"] = ""
                
                # ===== ДЛЯ УДАЛЕНИЯ ФАЙЛА =====
                elif tool_name == "delete_file":
                    import re
                    match = re.search(r'["\']([^"\']+)["\']', user_prompt)
                    if match:
                        params["filename"] = match.group(1)
                    else:
                        words = user_prompt.split()
                        for i, word in enumerate(words):
                            if word.lower() in ["файл", "file"] and i + 1 < len(words):
                                params["filename"] = words[i + 1].strip('"\'').strip()
                                break
                        if "filename" not in params:
                            params["filename"] = ""
                    
                    # Проверяем подтверждение
                    if "confirm=yes" in user_prompt.lower():
                        params["confirm"] = "yes"
                    else:
                        params["confirm"] = "no"
                
                # ===== ДЛЯ ЧТЕНИЯ ФАЙЛА =====
                elif tool_name == "read_file":
                    import re
                    match = re.search(r'["\']([^"\']+)["\']', user_prompt)
                    if match:
                        params["filename"] = match.group(1)
                    else:
                        words = user_prompt.split()
                        for i, word in enumerate(words):
                            if word.lower() in ["файл", "file"] and i + 1 < len(words):
                                params["filename"] = words[i + 1].strip('"\'').strip()
                                break
                        if "filename" not in params:
                            params["filename"] = ""
                
                # ===== ДЛЯ ПРОЦЕССОВ =====
                elif tool_name == "list_processes":
                    # Ищем фильтр
                    words = user_prompt.split()
                    if len(words) > 2:
                        params["filter_str"] = words[-1]
                    else:
                        params["filter_str"] = ""
                
                # ===== ДЛЯ ДИСКА =====
                elif tool_name == "get_disk_usage":
                    # Ищем букву диска
                    import re
                    match = re.search(r'([A-Za-z]):', user_prompt)
                    if match:
                        params["drive"] = match.group(1) + ":"
                    else:
                        params["drive"] = "C:"
                
                # ===== ДЛЯ SQL =====
                elif tool_name == "run_sql_query":
                    import re
                    # Ищем текст после "запрос" или "sql"
                    match = re.search(r'(?:запрос|sql)\s*[:=]\s*["\']?([^"\']+)["\']?', user_prompt, re.IGNORECASE)
                    if match:
                        params["query"] = match.group(1).strip()
                    else:
                        params["query"] = user_prompt
                
                return tool_name, params
        
        return None, {}
    
    # ========== ОСНОВНАЯ ЛОГИКА ==========
    def think_and_act(self, user_prompt: str, context: str = "") -> str:
        logger.info(f"Новый запрос: {user_prompt}")
        tool_name, params = self.detect_tool(user_prompt)
        
        if tool_name:
            logger.info(f"🔧 Определён инструмент: {tool_name} с параметрами: {params}")
            if hasattr(self, tool_name):
                try:
                    result = getattr(self, tool_name)(**params)
                    self.write_log(f"Пользователь: {user_prompt}")
                    self.write_log(f"Бот: {result[:100]}...")
                    return result
                except TypeError as e:
                    logger.error(f"Ошибка параметров: {e}")
                    return f"⚠️ Ошибка: не хватает параметров. Попробуй: создай папку имя_папки"
        
        prompt = f"""
        Контекст предыдущих сообщений:
        {context}
        
        Пользователь спросил: "{user_prompt}"
        
        Ответь вежливо и кратко, учитывая контекст.
        Если это приветствие — поприветствуй.
        Если вопрос требует уточнения — попроси уточнить.
        """
        response = self._call_lm_studio(prompt)
        self.write_log(f"Пользователь: {user_prompt}")
        self.write_log(f"Бот: {response[:100]}...")
        return response