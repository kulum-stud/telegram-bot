import logging
import re
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from openai import AsyncOpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("")
if not OPENAI_API_KEY:
    raise ValueError("")

# Настройки для OpenRouter
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY,
    default_headers={
        "HTTP-Referer": "https://github.com",  #Мой Github
        "X-Title": "Telegram AI Assistant"
    }
)

bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

user_context = {}
HISTORY_LIMIT = 10

# Доступные модели
CURRENT_MODEL = "deepseek/deepseek-chat"  # Основная модель

@dp.message(Command('start'))
async def start(message: types.Message):
    user_id = message.from_user.id
    user_context[user_id] = []
    await message.answer(
        "🤖 **Здравствуйте, Господин!**\n\n"
        "Вы можете задать мне любой вопрос!Я постараюсь ответить на него.\n\n"
        "📝 **Полезные команды:**\n"
        "/clear - Очистить историю чата\n"
        "/models - Выбрать модель\n"
        "/help - помощь"
    )

@dp.message(Command('help'))
async def help_command(message: types.Message):
    help_text = """
 **Помощь**

Я — помощник на основе искусственного интеллекта, работающий на основе API OpenRouter.

**Buyruqlar:**
/start - Запустить бота
/clear - Очистить историю чата.
/models - Выбрать модель.
/help - Помощь.

**Как работает:**
- Задайте мне любой интересующий вопрос.
- Я помню последниие 10 сообщений.
- Каждый новый разговор начинается с новой истории.
    """
    await message.answer(help_text)

@dp.message(Command('models'))
async def show_models(message: types.Message):
    models_text = """
**Доступные модели:**

 **DeepSeek:**
- `deepseek/deepseek-chat` - Основная модель
- `deepseek/deepseek-coder` - Для программирования

 **Meta:**
- `meta-llama/llama-3.1-8b-instruct` - Llama 3.1
- `meta-llama/llama-3-8b-instruct` - Llama 3

 **Google:**
- `google/gemma-2-9b-it` - Gemma 2
- `google/gemma-7b-it` - Gemma

 **Microsoft:**
- `microsoft/wizardlm-2-8x22b` - WizardLM

 **OpenAI:**
- `openai/gpt-3.5-turbo` - GPT-3.5 Turbo

 Используйте команду /change_model чтобы изменить модель
    """
    await message.answer(models_text)

@dp.message(Command('change_model'))
async def change_model(message: types.Message):
   
    models_keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="deepseek/deepseek-chat")],
            [types.KeyboardButton(text="meta-llama/llama-3.1-8b-instruct")],
            [types.KeyboardButton(text="google/gemma-2-9b-it")],
            [types.KeyboardButton(text="openai/gpt-3.5-turbo")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "🔄 Выберите модель:",
        reply_markup=models_keyboard
    )

@dp.message(Command('clear'))
async def clear_history(message: types.Message):
    user_id = message.from_user.id
    user_context[user_id] = []
    await message.answer("✅ Чат очищен.")

@dp.message(lambda message: message.text and any(model in message.text for model in [
    "deepseek/deepseek-chat", 
    "meta-llama/llama-3.1-8b-instruct",
    "google/gemma-2-9b-it",
    "openai/gpt-3.5-turbo"
]))
async def handle_model_selection(message: types.Message):
    global CURRENT_MODEL
    user_id = message.from_user.id
    new_model = message.text
    
    CURRENT_MODEL = new_model
    user_context[user_id] = []  # ОЧистить историю для новой модели
    
    await message.answer(
        f"✅ Модель изменён: `{new_model}`\n"
        f"История чата обновлена.",
        reply_markup=types.ReplyKeyboardRemove()
    )

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    user_message = message.text
    
    if not user_message or not user_message.strip():
        await message.answer("Господин,задайте мне вопрос в текстовом виде..")
        return
        
    logger.info(f"Пользователь {user_id}: {user_message}")

    if user_id not in user_context:
        user_context[user_id] = []

    user_context[user_id].append({"role": "user", "content": user_message})

    if len(user_context[user_id]) > HISTORY_LIMIT:
        user_context[user_id] = user_context[user_id][-HISTORY_LIMIT:]

    try:
        # Запрос отправлен
        completion = await client.chat.completions.create(
            model=CURRENT_MODEL,
            messages=user_context[user_id],
            max_tokens=2000,
            temperature=0.7,
            stream=False
        )

        if completion and completion.choices:
            choice = completion.choices[0]
            content = choice.message.content
            
            if content:
                # HTML очистка тегов
                cleaned_content = re.sub(r'<.*?>', '', content).strip()

                if cleaned_content:
                    #  Лимит Telegram сообщений (4096 слов)
                    if len(cleaned_content) > 4000:
                        chunks = [cleaned_content[i:i+4000] for i in range(0, len(cleaned_content), 4000)]
                        for i, chunk in enumerate(chunks):
                            if i == 0:
                                await message.answer(f"**Ответ:**\n\n{chunk}")
                            else:
                                await message.answer(chunk)
                    else:
                        await message.answer(f"**Ответ:**\n\n{cleaned_content}")
                    
                    # Добавить в историю
                    user_context[user_id].append({"role": "assistant", "content": cleaned_content})
                    
                    logger.info(f"Пользователю {user_id} отправлен сообщение")
                else:
                    await message.answer("❌ Нейронка вернула пустой ответ.")
            else:
                await message.answer("❌  Нет ответа от нейронки.")
        else:
            await message.answer("❌ Ошибка подключения к нейронке.")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Xato: {error_msg}")
        
        # При различных ошибках
        if "404" in error_msg or "No endpoints" in error_msg:
            await message.answer(
                f"❌ Модель не найден: `{CURRENT_MODEL}`\n\n"
                f"Выберите другую модель с помощью команды /change_model."
            )
        elif "401" in error_msg or "auth" in error_msg.lower():
            await message.answer("❌ Ключ API недействителен или просрочен.")
        elif "429" in error_msg:
            await message.answer("⏳ Достигнут лимит запросов. Пожалуйста, подождите немного.")
        else:
            await message.answer(f"❌ Произошла ошибка: {error_msg}")

async def main():
    logger.info("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())