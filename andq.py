import logging
from bot import AndqBotWithMemory

# ========== НАСТРОЙКА ЛОГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ========== ТОЧКА ВХОДА ==========
if __name__ == "__main__":
    print("=" * 60)
    print("ANDQ Bot Agent with Memory")
    print("=" * 60)
    
    bot = AndqBotWithMemory(
        model_name="qwen2.5-coder-7b-instruct-128k"
    )
    
    print(f"\n🤖 Модель: {bot.model_name}")
    print("\nДоступные команды:")
    print("  - покажи процессы")
    print("  - сколько места на диске C:")
    print("  - покажи логи")
    print("  - выполни SQL запрос")
    print("  - покажи файлы")
    print("  - создай файл test.txt content='привет'")
    print("  - прочитай файл test.txt")
    print("  - создай папку my_folder")
    print("  - удали файл test.txt confirm=yes")
    print("\nДля выхода введи 'exit' или 'quit'")
    print("=" * 60)
    
    while True:
        user_input = input("\n👤 > ")
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("👋 До свидания!")
            break
        
        if not user_input.strip():
            continue
        
        print("⏳ Обработка...")
        response = bot.think_and_act_with_memory(user_input)
        print(f"\n🤖 {response}")