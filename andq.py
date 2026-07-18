#!/usr/bin/env python3
"""
ANDQ Bot - Корпоративный ИИ-ассистент
Точка входа в приложение
"""

import os
import sys
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Добавляем путь к боту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.memory import AndqBotWithMemory


def clear_screen():
    """Очищает экран"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Печатает заголовок"""
    print("=" * 60)
    print("ANDQ Bot Agent with Memory".center(60))
    print("=" * 60)


def print_commands():
    """Печатает список доступных команд"""
    print("\nДоступные команды:")
    print("  - покажи процессы")
    print("  - сколько места на диске")
    print("  - покажи логи")
    print("  - выполни SQL запрос")
    print("  - покажи файлы")
    print("  - создай файл test.txt content='привет'")
    print("  - прочитай файл test.txt")
    print("  - создай папку my_folder")
    print("  - удали файл test.txt")
    print("\n  - привет (для общения)")
    print("  - как дела? (для общения)")
    print("  - кто ты? (для общения)")
    print("\nДля выхода введи 'exit' или 'quit'")
    print("=" * 60)


def main():
    """Главная функция"""
    try:
        # Очищаем экран
        clear_screen()
        print_header()
        
        # Создаем бота
        bot = AndqBotWithMemory()
        
        # Проверяем, что бот инициализирован
        if not bot:
            logger.error("❌ Не удалось инициализировать бота")
            return
        
        # Показываем информацию о модели
        print(f"\n🤖 Модель: {bot.model_name if hasattr(bot, 'model_name') else 'неизвестна'}")
        
        print_commands()
        
        # Основной цикл
        while True:
            try:
                # Получаем ввод пользователя
                user_input = input("\n👤 > ").strip()
                
                # Проверка на выход
                if user_input.lower() in ['exit', 'quit', 'выход', 'q']:
                    print("🤖 До свидания!")
                    break
                
                # Пропускаем пустые запросы
                if not user_input:
                    continue
                
                # Показываем индикатор обработки
                print("⏳ Обработка...")
                
                # Получаем ответ от бота
                response = bot.think_and_act_with_memory(user_input)
                
                # Выводим ответ
                print(f"\n🤖 {response}")
                
            except KeyboardInterrupt:
                print("\n🤖 До свидания!")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле: {e}")
                print(f"❌ Произошла ошибка: {str(e)}")
                continue
    
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print(f"❌ Критическая ошибка: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())