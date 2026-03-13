import asyncio
import os
import logging
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
from telegram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "250132923"))
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "-5127201182"))
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1fMFkFChJrs7JZ2BZZolF4ytXKSJihHwcoatNLuzyEYM")

# Congratulation text — edit this!
CONGRATS_TEXT = """🎉 Сегодня день рождения у {name}!

Присоединяйтесь к поздравлениям — пусть этот день будет особенным! 🎂"""

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
    return client.open_by_key(SPREADSHEET_ID).sheet1

def get_all_users():
    sheet = get_sheet()
    return sheet.get_all_records()

def reset_donations():
    """Reset donated column to 0 for all users after birthday"""
    sheet = get_sheet()
    users = sheet.get_all_records()
    for i, user in enumerate(users, start=2):
        sheet.update_cell(i, 6, 0)

def days_until_birthday(birthdate_str):
    """Calculate days until birthday this year"""
    today = datetime.today()
    try:
        bday = datetime.strptime(birthdate_str, "%d.%m")
    except ValueError:
        return None

    bday_this_year = bday.replace(year=today.year)
    if bday_this_year.date() < today.date():
        bday_this_year = bday_this_year.replace(year=today.year + 1)

    delta = (bday_this_year.date() - today.date()).days
    return delta

async def run_scheduler():
    bot = Bot(token=BOT_TOKEN)
    users = get_all_users()
    today = datetime.today()

    for user in users:
        name = user.get("name", "")
        birthdate = user.get("birthdate", "")
        telegram_id = user.get("telegram_id", "")
        wishlist = user.get("wishlist", "нет вишлиста")
        donated = int(user.get("donated", 0))

        if not birthdate or not telegram_id:
            continue

        days = days_until_birthday(birthdate)
        if days is None:
            continue

        logger.info(f"{name}: {days} дней до ДР")

        # За 30 дней — пишем имениннику
        if days == 30:
            try:
                await bot.send_message(
                    chat_id=int(telegram_id),
                    text=f"Привет, {name}! 👋\n\n"
                         f"Через месяц у тебя день рождения 🎂\n"
                         f"Обнови свой вишлист, чтобы команда знала что подарить!\n\n"
                         f"Напиши /wishlist чтобы обновить список."
                )
                logger.info(f"Sent 30-day reminder to {name}")
            except Exception as e:
                logger.error(f"Error sending to {name}: {e}")

        # За 21 день — пишем команде (всем кроме именинника)
        if days == 21:
            other_users = [u for u in users if str(u.get("telegram_id")) != str(telegram_id)]
            for teammate in other_users:
                try:
                    await bot.send_message(
                        chat_id=int(teammate["telegram_id"]),
                        text=f"🎁 Привет! Через 3 недели день рождения у {name}.\n\n"
                             f"Собираем на подарок! Скидываемся кто сколько может.\n"
                             f"Реквизиты для перевода уточни у организатора.\n\n"
                             f"Когда скинешь — напиши боту /skidal ✅"
                    )
                except Exception as e:
                    logger.error(f"Error sending to teammate {teammate.get('name')}: {e}")
            logger.info(f"Sent collection reminder to team for {name}")

        # За 14 дней — пишем админу с вишлистом и статистикой сбора
        if days == 14:
            total_team = len([u for u in users if str(u.get("telegram_id")) != str(telegram_id)])
            donated_count = sum(1 for u in users
                                if str(u.get("telegram_id")) != str(telegram_id)
                                and int(u.get("donated", 0)) > 0)
            try:
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🛍 Через 2 недели день рождения у {name}!\n\n"
                         f"Вишлист:\n{wishlist}\n\n"
                         f"Статус сбора: {donated_count} из {total_team} скинули\n\n"
                         f"Пора покупать подарок! 🎁"
                )
                logger.info(f"Sent admin reminder with wishlist for {name}")
            except Exception as e:
                logger.error(f"Error sending admin reminder: {e}")

        # За 7 дней — напоминаем админу купить подарок
        if days == 7:
            total_team = len([u for u in users if str(u.get("telegram_id")) != str(telegram_id)])
            donated_count = sum(1 for u in users
                                if str(u.get("telegram_id")) != str(telegram_id)
                                and int(u.get("donated", 0)) > 0)
            try:
                await bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"⏰ Напоминание! Через неделю ДР у {name}.\n\n"
                         f"Финальный статус сбора: {donated_count} из {total_team} скинули\n\n"
                         f"Не забудь купить подарок! 🛍"
                )
                logger.info(f"Sent 7-day reminder to admin for {name}")
            except Exception as e:
                logger.error(f"Error sending 7-day reminder: {e}")

        # В день ДР — постим поздравление в чат и сбрасываем счётчик
        if days == 0:
            try:
                await bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=CONGRATS_TEXT.format(name=name)
                )
                logger.info(f"Sent birthday congrats for {name}")
                # Reset donations counter for next year
                reset_donations()
            except Exception as e:
                logger.error(f"Error sending congrats: {e}")

if __name__ == "__main__":
    asyncio.run(run_scheduler())
