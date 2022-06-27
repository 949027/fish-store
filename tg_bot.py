import os
import logging
from datetime import datetime, timedelta
import redis
import requests.exceptions
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler

from moltin_api import *

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

_database = None
_moltin_token = {}

moltin_client_id = os.getenv('MOLTIN_CLIENT_ID')
moltin_client_secret = os.getenv('MOLTIN_CLIENT_SECRET')
token_expiration = os.getenv('TOKEN_EXPIRATION')


def send_catalog(bot, update):
    products = get_all_products(get_moltin_token(
        moltin_client_id,
        moltin_client_secret,
        token_expiration,
    ))
    keyboard = [
        [InlineKeyboardButton(product['name'], callback_data=product['id'])]
        for product in products
    ]
    keyboard.append([InlineKeyboardButton('Корзина', callback_data='Корзина')])
    reply_markup =InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        update.callback_query.message.reply_text(
            text='Сегодня в продаже:',
            reply_markup=reply_markup,
        )
        return
    elif update.message:
        update.message.reply_text(text='Сегодня в продаже:', reply_markup=reply_markup)
        return


def send_cart(bot, update):
    query = update.callback_query
    chat_id = query.message.chat_id

    cart = get_cart(moltin_bearer_token, chat_id)
    items = cart['data']
    cart_keyboard = []
    if items:
        cart_keyboard.append([InlineKeyboardButton('Оплатить', callback_data='Оплатить')])
        text = ''
        for item in items:
            text = text + '{}\n{}\n{} за кг\nВ корзине {} кг на {}\n\n'.format(
                item['name'],
                item['description'],
                item['meta']['display_price']['with_tax']['unit']['formatted'],
                item['quantity'],
                item['meta']['display_price']['with_tax']['value']['formatted']
            )
            cart_keyboard.append([InlineKeyboardButton(f'Убрать {item["name"]}', callback_data=item['id'])])

        text = text + 'Итого: ' + cart['meta']['display_price']['with_tax']['formatted']
    else:
        text = 'Корзина пуста'
    cart_keyboard.append([InlineKeyboardButton('В меню', callback_data='В меню')])
    reply_markup = InlineKeyboardMarkup(cart_keyboard)
    bot.send_message(chat_id, text, reply_markup=reply_markup)


def start(bot, update):
    send_catalog(bot, update)
    return "HANDLE_MENU"


def handle_menu(bot, update):
    query = update.callback_query
    chat_id = query.message.chat_id
    if query.data == 'Корзина':
        send_cart(bot, update)
        bot.delete_message(
            chat_id=chat_id,
            message_id=query.message.message_id,
        )
        return 'HANDLE_CART'
    product_id = query.data
    product = get_product(moltin_bearer_token, product_id)
    image_id = product['relationships']['main_image']['data']['id']
    image_url = get_image_url(moltin_bearer_token, image_id)
    text = '{}\n{}'.format(
        product['name'],
        product['description'],
        #product['without_tax'] #TODO добавить описание
    )
    weight_options = [1, 3, 5]
    weight_keyboard = [
        InlineKeyboardButton(
            f'{weight} кг',
            callback_data='{}\n{}'.format(weight, product_id))
        for weight in weight_options
    ]
    keyboard = [
        [InlineKeyboardButton('Назад', callback_data='Назад')],
        weight_keyboard,
        [InlineKeyboardButton('Корзина', callback_data='Корзина')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_photo(chat_id, image_url, caption=text, reply_markup=reply_markup)
    bot.delete_message(
        chat_id=chat_id,
        message_id=query.message.message_id,
    )
    return 'HANDLE_DESCRIPTION'


def handle_description(bot, update):
    query = update.callback_query
    chat_id = query.message.chat_id
    if query.data == 'Корзина':
        send_cart(bot, update)
        bot.delete_message(
            chat_id=chat_id,
            message_id=query.message.message_id,
        )
        return 'HANDLE_CART'
    if query.data == 'Назад':
        bot.delete_message(
            chat_id=chat_id,
            message_id=query.message.message_id,
        )
        send_catalog(bot, update)
        return 'HANDLE_MENU'
    quantity, product_id = query.data.split('\n')
    add_product_to_cart(moltin_bearer_token, str(chat_id), product_id, int(quantity))
    return 'HANDLE_DESCRIPTION'


def handle_cart(bot, update):
    query = update.callback_query
    chat_id = query.message.chat_id
    bot.delete_message(
            chat_id=chat_id,
            message_id=query.message.message_id,
        )
    if query.data == 'Оплатить':
        text = 'Напишите свой e-mail и наш менеджер свяжется с Вами'
        bot.send_message(chat_id=chat_id, text=text)
        return 'WAIT_EMAIL'
    if query.data == 'В меню':
        send_catalog(bot, update)
        return 'HANDLE_MENU'
    delete_cart_item(moltin_bearer_token, chat_id, query.data)
    send_cart(bot, update)
    bot.delete_message(
        chat_id=chat_id,
        message_id=query.message.message_id,
    )
    return 'HANDLE_CART'


def wait_email(bot, update):
    email = update.message.text
    username = update.message.chat.username
    chat_id = update.message.chat_id
    try:
        create_customer(moltin_bearer_token, username, email)
    except requests.exceptions.HTTPError as error:
        if error.response.status_code == 422:
            text = 'E-mail введен некорректно. Повторите ввод'
            bot.send_message(chat_id=chat_id, text=text)
        else:
            logger.warning('Update "%s" caused error "%s"', update, error)
        return 'WAIT_EMAIL'

    send_catalog(bot, update)
    return 'HANDLE_MENU'

def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)


def handle_users_reply(bot, update):
    db = get_database_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'WAIT_EMAIL': wait_email,
    }
    state_handler = states_functions[user_state]
    next_state = state_handler(bot, update)
    db.set(chat_id, next_state)


def get_database_connection():
    """
    Возвращает конекшн с базой данных Redis, либо создаёт новый, если он ещё не создан.
    """
    global _database
    if _database is None:
        database_username = os.getenv('DATABASE_USERNAME')
        database_password = os.getenv("DATABASE_PASSWORD")
        database_host = os.getenv("DATABASE_HOST")
        database_port = os.getenv("DATABASE_PORT")
        _database = redis.Redis(host=database_host, port=database_port, password=database_password, username=database_username)
    return _database


def get_moltin_token(client_id, client_secret, token_expiration):
    global _moltin_token
    if not _moltin_token or datetime.now() > _moltin_token['expires at']:
        _moltin_token = {
            'token': create_moltin_token(client_id, client_secret),
            'expires at': datetime.now() + timedelta(seconds=int(token_expiration)),
        }
    print(_moltin_token)
    return _moltin_token['token']


def main():
    token = os.getenv('TELEGRAM_TOKEN')
    updater = Updater(token)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    dispatcher.add_error_handler(error)
    updater.start_polling()


if __name__ == '__main__':
    main()
