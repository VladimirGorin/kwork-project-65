import json
import os
import random
import logging
import asyncio
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

SESSIONS_DIR = './sessions/'
LOG_FILE = './log/main.log'
MESSAGES_FILE = './data/messages.txt'
SYNONYMS_FILE = './data/synonyms.txt'


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_session_config(phone):
    session_path = os.path.join(SESSIONS_DIR, f'{phone}.json')
    if os.path.exists(session_path):
        with open(session_path, 'r') as file:
            return json.load(file)
    else:
        logger.error(f"Файл конфигурации {session_path} не найден!")
        return None

def load_messages(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file.readlines()]

def generate_random_message(messages, synonyms):
    random_message = random.choice(messages)
    random_word = random.choice(synonyms)
    return f"{random_message}, {random_word}!"

def generate_text_keyboard(keyboard):
    buttons = keyboard.rows
    result = []

    for row in buttons:
        for button in row.buttons:
            result.append(button.text)

    return result


async def like_people(phone, client):
    buttons_not_found = 0

    generated_message = load_messages(MESSAGES_FILE)
    generated_synonym = load_messages(SYNONYMS_FILE)

    while True:
        try:
            bot = await client.get_entity('leomatchbot')
            messages = await client.get_messages(bot, limit=1)
            reply_markup = messages[0].reply_markup

            if buttons_not_found >= 3:
                buttons_not_found = 0
                await client.send_message(bot, "/myprofile")
                messages = await client.get_messages(bot, limit=1)
                await messages[0].click()

            if not reply_markup:
                buttons_not_found += 1
                logger.error(f"({phone}) Под последним сообщением не найдена клавиатура, делаем поиск по старым сообщениям")
                i = 1
                while True:
                    await asyncio.sleep(5)
                    messages = await client.get_messages(bot, limit=i)
                    reply_markup = messages[-1].reply_markup
                    if not reply_markup:
                        i += 1
                    else:
                        break

            keyboard_text = generate_text_keyboard(reply_markup)
            if reply_markup:
                logger.info(f"({phone}) ({keyboard_text}) Клавиатура найдена!")

            found = False
            buttons = reply_markup.rows

            for row in buttons:
                for button in row.buttons:

                    if "💌" in button.text:
                        await client.send_message(bot, button.text)
                        found = True
                        logger.info("Нажата кнопка 💌")
                        random_message = generate_random_message(generated_message, generated_synonym)
                        await client.send_message(bot, random_message)
                        logger.info(f"Отправлено сообщение: {random_message}")
                        break

                if not found:
                    for button in row.buttons:
                        if button.text == "❤️":
                            await client.send_message(bot, button.text)
                            found = True
                            logger.info("Нажата кнопка ❤️")
                            break

                if found:
                    buttons_not_found = 0
                    break

            if not found:
                logger.info(f"({phone})({keyboard_text}) Не удалось нажать ни на одну кнопку, нажимаем на первую")
                await messages[0].click()

            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"({phone}) Ошибка при нажатии на конвертик, продолжаем попытки: {e}")

async def process_session(phone):
    config = load_session_config(phone)
    if not config:
        return

    print(config)

    api_id = config.get('app_id')
    api_hash = config.get('app_hash')
    session_file = os.path.join(SESSIONS_DIR, f'{phone}.session')

    client = TelegramClient(session_file, api_id, api_hash)

    try:
        await client.start(phone=phone)
        if await client.is_user_authorized():
            logger.info(f"Успешная авторизация для {phone}")
        else:
            logger.error(f"Не удалось авторизоваться для {phone}")

        @client.on(events.NewMessage(pattern='Отлично! Надеюсь хорошо проведете время'))
        async def handle_favorite_message(event):
            await client.forward_messages('me', event.message)
            logger.info(f"Сообщение переслано в избранное для {phone}: {event.raw_text}")

        @client.on(events.NewMessage(pattern='Есть взаимная симпатия! Начинай общаться'))
        async def handle_favorite_message(event):
            await client.forward_messages('me', event.message)
            logger.info(f"Сообщение переслано в избранное для {phone}: {event.raw_text}")

        await like_people(phone, client)

    except SessionPasswordNeededError:
        logger.error(f"Необходим пароль для двухфакторной аутентификации для {phone}")
    except Exception as e:
        logger.error(f"Ошибка для {phone}: {e}")
    finally:
        await client.disconnect()

async def main():
    phones = [f.split('.')[0] for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
    if not phones:
        logger.error("Не найдено ни одной сессии в папке.")
        return

    tasks = [asyncio.create_task(process_session(phone)) for phone in phones]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("bye :)")
