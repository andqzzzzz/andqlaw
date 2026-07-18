import os
import subprocess
from datetime import datetime


class Tools:
    """Все инструменты бота с системой прав"""
    
    def __init__(self):
        self.log_dir = "C:/ai/andq/logs"
        self.sandbox_root = "C:/ai/andq/sandbox"
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.sandbox_root, exist_ok=True)
    
    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========
    
    def _is_inside_sandbox(self, path: str) -> bool:
        """Проверяет, находится ли путь внутри песочницы"""
        sandbox_norm = os.path.normpath(self.sandbox_root)
        path_norm = os.path.normpath(path)
        return path_norm.startswith(sandbox_norm)
    
    def _get_sandbox_path(self, subpath: str = "") -> str:
        """Возвращает безопасный путь внутри песочницы"""
        if not subpath:
            return self.sandbox_root
        subpath = subpath.strip()
        safe_path = os.path.normpath(os.path.join(self.sandbox_root, subpath))
        if not safe_path.startswith(os.path.normpath(self.sandbox_root)):
            return self.sandbox_root
        return safe_path
    
    def _read_file_content(self, filepath: str) -> str:
        """Читает содержимое файла (безопасно)"""
        try:
            ext = os.path.splitext(filepath)[1].lower()
            text_extensions = ['.txt', '.log', '.json', '.xml', '.html', '.css', '.js', '.py', '.md', '.csv']
            if ext in text_extensions:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                if len(content) > 5000:
                    content = content[:5000] + f"\n\n... (всего {len(content)} символов, показано 5000)"
                return content
            else:
                size = os.path.getsize(filepath)
                if size < 1024:
                    size_str = f"{size} Б"
                elif size < 1024 * 1024:
                    size_str = f"{size // 1024} КБ"
                else:
                    size_str = f"{size // (1024 * 1024)} МБ"
                return f"(бинарный файл, размер {size_str})"
        except Exception as e:
            return f"Ошибка чтения: {e}"
    
    # ========== ЛОГИ (только чтение в logs/) ==========
    
    def write_log(self, message: str) -> str:
        """Записать сообщение в лог (разрешено только внутри logs/)"""
        filepath = os.path.join(self.log_dir, "app.log")
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
            return "OK"
        except Exception as e:
            return f"Ошибка записи лога: {e}"
    
    def read_log_file(self, filename: str = "app.log") -> str:
        """Прочитать лог-файл (только чтение внутри logs/)"""
        if ".." in filename or "/" in filename or "\\" in filename:
            filename = "app.log"
        filepath = os.path.join(self.log_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()[-50:]
                content = "".join(lines) if lines else "Файл пуст."
            return f"📄 Лог-файл {filename} (последние 50 строк):\n{content}"
        except FileNotFoundError:
            return f"❌ Файл {filename} не найден в {self.log_dir}"
        except Exception as e:
            return f"Ошибка: {e}"
    
    # ========== ПРОЦЕССЫ (только чтение) ==========
    
    def list_processes(self, filter_str: str = "") -> str:
        """Показать запущенные процессы (только чтение)"""
        try:
            if os.name == 'nt':
                cmd = ["tasklist"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=True)
            else:
                cmd = ["ps", "aux"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            lines = result.stdout.split('\n')
            if filter_str:
                lines = [l for l in lines if filter_str.lower() in l.lower()]
            output = "\n".join(lines[:30]) if lines else "Процессы не найдены."
            self.write_log(f"Запрошен список процессов, фильтр: {filter_str}")
            return f"📋 Список процессов:\n{output}"
        except Exception as e:
            return f"Ошибка: {e}"
    
    # ========== ДИСК (только чтение) ==========
    
    def get_disk_usage(self, drive: str = "C:") -> str:  # <-- ВАЖНО: правильный отступ!
        """Показать использование диска"""
        try:
            if os.name == 'nt':
                cmd = f"wmic logicaldisk where caption='{drive}' get caption,size,freespace /format:list"
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5, shell=True)
                if not result.stdout.strip():
                    cmd2 = "wmic logicaldisk get caption,size,freespace"
                    result = subprocess.run(cmd2, capture_output=True, text=True, timeout=5, shell=True)
                
                self.write_log(f"Запрошено использование диска {drive}")
                
                # Парсим вывод wmic
                lines = result.stdout.strip().split('\n')
                data = {}
                for line in lines:
                    if '=' in line:
                        key, value = line.split('=', 1)
                        data[key.strip()] = value.strip()
                
                if data:
                    caption = data.get('Caption', drive)
                    size = int(data.get('Size', 0))
                    freespace = int(data.get('FreeSpace', 0))
                    if size > 0:
                        used = size - freespace
                        used_gb = used / (1024**3)
                        total_gb = size / (1024**3)
                        free_gb = freespace / (1024**3)
                        percent = (used / size) * 100
                        return f"📊 Диск {caption}: Всего {total_gb:.1f} ГБ, Занято {used_gb:.1f} ГБ ({percent:.1f}%), Свободно {free_gb:.1f} ГБ"
                
                return f"💾 Использование диска:\n{result.stdout}"
            else:
                result = subprocess.run(["df", "-h"], capture_output=True, text=True, timeout=5)
                self.write_log("Запрошено использование диска")
                return f"💾 Использование диска:\n{result.stdout}"
        except Exception as e:
            return f"Ошибка: {e}"
    
    # ========== SQL (только SELECT) ==========
    
    def run_sql_query(self, query: str) -> str:
        """Выполнить SELECT-запрос (только чтение)"""
        if not query.strip().upper().startswith("SELECT"):
            self.write_log(f"Попытка выполнить не-SELECT запрос: {query}")
            return "⚠️ Разрешены только SELECT запросы."
        self.write_log(f"Выполнен SQL запрос: {query}")
        return f"🔍 Выполняю запрос: {query}\n(Подставь свою логику работы с БД)"
    
    # ========== ПЕСОЧНИЦА (полный доступ) ==========
    
    def list_files(self, path: str = "") -> str:
        """Показать содержимое папки в песочнице (чтение)"""
        target_path = self._get_sandbox_path(path)
        try:
            if not os.path.exists(target_path):
                return f"❌ Путь не найден: {target_path}"
            items = os.listdir(target_path)
            if not items:
                return f"📁 Папка пуста: {target_path}"
            files, folders = [], []
            for item in items:
                full_path = os.path.join(target_path, item)
                if os.path.isdir(full_path):
                    folders.append(f"📁 {item}/")
                else:
                    size = os.path.getsize(full_path)
                    if size < 1024:
                        size_str = f"{size} Б"
                    elif size < 1024 * 1024:
                        size_str = f"{size // 1024} КБ"
                    else:
                        size_str = f"{size // (1024 * 1024)} МБ"
                    files.append(f"📄 {item} ({size_str})")
            result = f"📂 Содержимое папки: {target_path}\n\n"
            if folders:
                result += "Папки:\n" + "\n".join(folders) + "\n\n"
            if files:
                result += "Файлы:\n" + "\n".join(files)
            self.write_log(f"Просмотр папки: {target_path}")
            return result
        except Exception as e:
            return f"Ошибка: {e}"
    
    def read_file(self, filename: str) -> str:
        """Прочитать содержимое файла (только из песочницы)"""
        if not filename:
            return "❌ Укажите имя файла"
        filename = filename.strip()
        filepath = self._get_sandbox_path(filename)
        
        # Проверяем, что файл внутри песочницы
        if not self._is_inside_sandbox(filepath):
            return f"❌ Чтение файлов вне песочницы запрещено: {filename}"
        
        try:
            if not os.path.exists(filepath):
                return f"❌ Файл не найден: {filepath}"
            if os.path.isdir(filepath):
                return f"❌ Это папка, а не файл: {filepath}"
            
            content = self._read_file_content(filepath)
            self.write_log(f"Прочитан файл: {filepath}")
            return f"📄 Содержимое файла {filename}:\n\n{content}"
        except Exception as e:
            return f"Ошибка чтения файла: {e}"
    
    def write_file(self, filename: str = "", content: str = "") -> str:
        """Создать или перезаписать файл (только в песочнице)"""
        if not filename:
            return "❌ Укажите имя файла. Пример: создай файл test.txt content='текст'"
        
        filename = filename.strip()
        filepath = self._get_sandbox_path(filename)
        
        # Проверяем, что файл внутри песочницы
        if not self._is_inside_sandbox(filepath):
            return f"❌ Создание файлов вне песочницы запрещено: {filename}"
        
        # Проверяем, не пытается ли пользователь создать папку
        if filename.endswith('/') or filename.endswith('\\'):
            return f"❌ '{filename}' похоже на папку. Для создания папки используйте: создай папку {filename}"
        
        # Защита от опасных расширений
        dangerous_ext = ['.exe', '.bat', '.cmd', '.sh', '.pyc', '.dll', '.sys']
        ext = os.path.splitext(filename)[1].lower()
        if ext in dangerous_ext:
            return f"❌ Создание файлов с расширением {ext} запрещено"
        
        # Проверяем, не содержит ли имя опасные символы
        if '..' in filename or '/' in filename or '\\' in filename:
            return f"❌ Имя файла содержит запрещённые символы: {filename}"
        
        # Проверяем, не является ли путь папкой
        if os.path.isdir(filepath):
            return f"❌ '{filename}' — это папка. Для создания папки используйте: создай папку {filename}"
        
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self.write_log(f"Создан файл: {filepath} (размер: {len(content)} символов)")
            return f"✅ Файл создан: {filepath}\nРазмер: {len(content)} символов"
        except PermissionError:
            return f"❌ Нет прав на запись в {filepath}. Проверьте права доступа."
        except Exception as e:
            return f"Ошибка записи файла: {e}"
    
    def delete_file(self, filename: str = "", confirm: str = "no") -> str:
        """Удалить файл (только в песочнице, с подтверждением)"""
        if not filename:
            return "❌ Укажите имя файла. Пример: удали файл test.txt confirm=yes"
        filename = filename.strip()
        filepath = self._get_sandbox_path(filename)
        
        # Проверяем, что файл внутри песочницы
        if not self._is_inside_sandbox(filepath):
            return f"❌ Удаление файлов вне песочницы запрещено: {filename}"
        
        if os.path.basename(filename) in ['sandbox', 'logs', 'conversations']:
            return f"❌ Запрещено удалять системные папки: {filename}"
        
        try:
            if not os.path.exists(filepath):
                return f"❌ Файл не найден: {filepath}"
            if os.path.isdir(filepath):
                return f"❌ Это папка, а не файл. Для удаления папки используйте: удали папку {filename}"
            if confirm != "yes":
                return f"⚠️ Для удаления файла {filename} введите: удали файл {filename} confirm=yes"
            os.remove(filepath)
            self.write_log(f"Удалён файл: {filepath}")
            return f"✅ Файл удалён: {filepath}"
        except Exception as e:
            return f"Ошибка удаления: {e}"
    
    def create_folder(self, folder_name: str = "") -> str:
        """Создать папку (только в песочнице)"""
        if not folder_name:
            return "❌ Укажите имя папки. Пример: создай папку my_folder"
        
        folder_name = folder_name.strip()
        folder_path = self._get_sandbox_path(folder_name)
        
        # Проверяем, что папка внутри песочницы
        if not self._is_inside_sandbox(folder_path):
            return f"❌ Создание папок вне песочницы запрещено: {folder_name}"
        
        # Защита от создания системных папок
        if folder_name in ['sandbox', 'logs', 'conversations']:
            return f"❌ Запрещено создавать папку с именем {folder_name}"
        
        # Проверяем, не содержит ли имя опасные символы
        if '..' in folder_name or '/' in folder_name or '\\' in folder_name:
            return f"❌ Имя папки содержит запрещённые символы: {folder_name}"
        
        # Проверяем, не является ли путь файлом
        if os.path.exists(folder_path) and not os.path.isdir(folder_path):
            return f"❌ По этому пути уже существует файл: {folder_path}"
        
        try:
            if os.path.exists(folder_path):
                return f"⚠️ Папка уже существует: {folder_path}"
            os.makedirs(folder_path)
            self.write_log(f"Создана папка: {folder_path}")
            return f"✅ Папка создана: {folder_path}"
        except Exception as e:
            return f"Ошибка создания папки: {e}"