import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "250132923"))
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "-5127201182"))
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1fMFkFChJrs7JZ2BZZolF4ytXKSJihHwcoatNLuzyEYM")

# Google Sheets
def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    import json
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    return sheet

def get_all_users():
    sheet = get_sheet()
    return sheet.get_all_records()

def find_user(telegram_id):
    users = get_all_users()
    for i, user in enumerate(users, start=2):
        if str(user.get("telegram_id")) == str(telegram_id):
            return user, i
    return None, None

def add_user(name, birthdate, telegram_id, username, wishlist):
    sheet = get_sheet()
    sheet.append_row([name, birthdate, str(telegram_id), username, wishlist, "0", ""])

def update_user_wishlist(row_index, wishlist):
    sheet = get_sheet()
    sheet.update_cell(row_index, 5, wishlist)
    sheet.update_cell(row_index, 7, datetime.now().strftime("%d.%m.%Y"))

def mark_donated(telegram_id):
    user, row_index = find_user(telegram_id)
    if user and row_index:
        current = int(user.get("donated", 0))
        sheet = get_sheet()
        sheet.update_cell(row_index, 6, current + 1)
        return True
    return False

def get_donation_stats(birthday_person_id):
    users = get_all_users()
    total = len([u for u in users if str(u.get("telegram_id")) != str(birthday_person_id)])
    donated = sum(1 for u in users 
                  if str(u.get("telegram_id")) != str(birthday_person_id) 
                  and int(u.get("donated", 0)) > 0)
    return donated, total

# Conversation states
NAME, BIRTHDATE, WISHLIST = range(3)
UPDATE_WISHLIST = 10

# /start — registration
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user, _ = find_user(telegram_id)

    if user:
        await update.message.reply_text(
            f"Привет, {user['name']}! Ты уже зарегистрирован(а) 🎉\n\n"
            f"Твой вишлист: {user['wishlist'] or 'пока пустой'}\n\n"
            "Чтобы обновить вишлист — напиши /wishlist"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "Привет! 🎂 Я бот для поздравлений команды.\n\n"
        "Давай зарегистрирую тебя. Как тебя зовут?"
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "Отлично! Теперь напиши дату рождения в формате ДД.ММ\n"
        "Например: 15.03"
    )
    return BIRTHDATE

async def get_birthdate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        datetime.strptime(text, "%d.%m")
    except ValueError:
        await update.message.reply_text(
            "Не понял формат 😅 Напиши дату так: ДД.ММ\nНапример: 15.03"
        )
        return BIRTHDATE

    context.user_data["birthdate"] = text
    await update.message.reply_text(
        "Почти готово! Напиши свой вишлист — что хочешь получить в подарок?\n\n"
        "Можно написать несколько вещей, ссылки, категории — всё что угодно 🎁"
    )
    return WISHLIST

async def get_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wishlist = update.message.text.strip()
    user = update.effective_user
    name = context.user_data["name"]
    birthdate = context.user_data["birthdate"]
    username = user.username or ""

    add_user(name, birthdate, user.id, username, wishlist)

    await update.message.reply_text(
        f"Готово, {name}! 🎉\n\n"
        f"День рождения: {birthdate}\n"
        f"Вишлист: {wishlist}\n\n"
        "Всё сохранил. Можешь обновить вишлист в любой момент через /wishlist"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, отменил 👍")
    return ConversationHandler.END

# /wishlist — update wishlist
async def wishlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user, _ = find_user(telegram_id)

    if not user:
        await update.message.reply_text(
            "Ты ещё не зарегистрирован(а). Напиши /start"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"Текущий вишлист:\n{user['wishlist'] or 'пустой'}\n\n"
        "Напиши новый вишлист 👇"
    )
    return UPDATE_WISHLIST

async def save_wishlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    _, row_index = find_user(telegram_id)
    update_user_wishlist(row_index, update.message.text.strip())
    await update.message.reply_text("Вишлист обновлён! 🎁")
    return ConversationHandler.END

# /skidal — mark as donated
async def skidal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    success = mark_donated(telegram_id)
    if success:
        await update.message.reply_text("Записал, спасибо! 🙌")
    else:
        await update.message.reply_text(
            "Не нашёл тебя в базе. Сначала зарегистрируйся через /start"
        )

# /status — donation status (admin only)
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    users = get_all_users()
    if not users:
        await update.message.reply_text("База пустая пока 🤷")
        return

    lines = ["📊 *Статус регистраций:*\n"]
    for u in users:
        donated = "✅" if int(u.get("donated", 0)) > 0 else "⬜️"
        lines.append(f"{donated} {u['name']} — {u['birthdate']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# /team — list all registered users (admin only)
async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    users = get_all_users()
    if not users:
        await update.message.reply_text("Никто ещё не зарегистрировался 🤷")
        return

    lines = ["👥 *Команда:*\n"]
    for u in users:
        lines.append(f"• {u['name']} — {u['birthdate']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Registration conversation
    reg_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            BIRTHDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_birthdate)],
            WISHLIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_wishlist)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Wishlist update conversation
    wishlist_handler = ConversationHandler(
        entry_points=[CommandHandler("wishlist", wishlist_command)],
        states={
            UPDATE_WISHLIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_wishlist)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(reg_handler)
    app.add_handler(wishlist_handler)
    app.add_handler(CommandHandler("skidal", skidal))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("team", team))

    logger.info("Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
