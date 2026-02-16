import logging
import os
import wikipedia
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Check credentials
if not TELEGRAM_TOKEN:
    logging.error("Error: TELEGRAM_BOT_TOKEN not found in .env file.")
    exit(1)

# Language settings
LANGUAGES = {
    "🇺🇿 O'zbek": "uz",
    "🇷🇺 Русский": "ru",
    "🇬🇧 English": "en"
}

# User language preference storage (in-memory)
user_languages = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command."""
    user_id = update.effective_user.id
    user_languages[user_id] = "uz" # Default to Uzbek
    
    keyboard = [
        ["🇺🇿 O'zbek", "🇷🇺 Русский", "🇬🇧 English"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    welcome_message = (
        "Salom! Men Wikipedia qidiruv botiman.\n"
        "Tilni tanlang va mavzuni yuboring.\n\n"
        "Привет! Я бот для поиска в Википедии.\n"
        "Выберите язык и отправьте запрос.\n\n"
        "Hello! I am a Wikipedia search bot.\n"
        "Choose a language and send a topic."
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_message, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for user messages."""
    text = update.message.text
    user_id = update.effective_user.id
    
    if not text:
        return

    # Handle language change
    if text in LANGUAGES:
        user_languages[user_id] = LANGUAGES[text]
        lang_code = LANGUAGES[text]
        
        response_map = {
            "uz": "Til O'zbekchaga o'zgartirildi. Mavzu yuboring:",
            "ru": "Язык изменен на Русский. Отправьте тему:",
            "en": "Language changed to English. Send a topic:"
        }
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_map[lang_code])
        return

    # Set Wikipedia language based on user preference
    lang_code = user_languages.get(user_id, "uz")
    wikipedia.set_lang(lang_code)

    # Indicate typing status
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    try:
        # Search and get page
        page = wikipedia.page(text)
        
        # Store page title for image retrieval
        context.user_data['last_wiki_topic'] = page.title
        
        # Get full content and split into chunks
        full_text = page.content
        max_length = 4000
        
        while full_text:
            if len(full_text) <= max_length:
                # Add button to the last message
                keyboard = [
                    [InlineKeyboardButton("Rasm yaratish", callback_data="get_wiki_image")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.send_message(chat_id=update.effective_chat.id, text=full_text, reply_markup=reply_markup)
                break
            else:
                # Find the nearest space to break cleanly
                split_index = full_text.rfind(' ', 0, max_length)
                if split_index == -1:
                    split_index = max_length
                
                await context.bot.send_message(chat_id=update.effective_chat.id, text=full_text[:split_index])
                full_text = full_text[split_index:].lstrip()

    except wikipedia.exceptions.DisambiguationError as e:
        options = "\n".join(e.options[:5]) # Show top 5 options
        
        msg_map = {
            "uz": "Bir nechta maqola topildi. Aniqroq yozing:",
            "ru": "Найдено несколько статей. Уточните запрос:",
            "en": "Multiple results found. Please be more specific:"
        }
        error_message = f"{msg_map.get(lang_code, msg_map['uz'])}\n\n{options}"
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text=error_message)

    except wikipedia.exceptions.PageError:
        msg_map = {
            "uz": "Ma'lumot topilmadi.",
            "ru": "Информация не найдена.",
            "en": "No information found."
        }
        error_message = msg_map.get(lang_code, msg_map['uz'])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=error_message)

    except Exception as e:
        logging.error(f"Error fetching Wikipedia data: {e}")
        msg_map = {
            "uz": "Xatolik yuz berdi.",
            "ru": "Произошла ошибка.",
            "en": "An error occurred."
        }
        error_message = msg_map.get(lang_code, msg_map['uz'])
        await context.bot.send_message(chat_id=update.effective_chat.id, text=error_message)

async def send_wiki_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback query handler to send an image from Wikipedia."""
    query = update.callback_query
    await query.answer()
    
    topic = context.user_data.get('last_wiki_topic')
    if not topic:
        await query.edit_message_text(text="Mavzu topilmadi. Qaytadan qidiring.")
        return

    try:
        # Set language again just in case (though page.images usually works fine)
        user_id = update.effective_user.id
        lang_code = user_languages.get(user_id, "uz")
        wikipedia.set_lang(lang_code)
        
        page = wikipedia.page(topic)
        if page.images:
            # Filter for valid image types (simple check)
            valid_images = [img for img in page.images if img.endswith(('.jpg', '.jpeg', '.png'))]
            if valid_images:
                image_url = valid_images[0] # Get the first valid image
                await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image_url, caption=f"Rasm: {topic}")
            else:
                 await context.bot.send_message(chat_id=update.effective_chat.id, text="Maqolada mos rasm topilmadi.")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Ushbu maqolada rasm yo'q.")
            
    except Exception as e:
        logging.error(f"Error sending image: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Rasmni yuklashda xatolik yuz berdi.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    start_handler = CommandHandler('start', start)
    message_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)
    image_callback_handler = CallbackQueryHandler(send_wiki_image, pattern="get_wiki_image")

    application.add_handler(start_handler)
    application.add_handler(message_handler)
    application.add_handler(image_callback_handler)
    
    print("Bot ishga tushdi...")
    application.run_polling()
