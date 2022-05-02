from http import HTTPStatus
import json
import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram


load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Функция отвечающая за отрпавку сообщений в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError as error:
        raise telegram.TelegramError(('Ошибка отправки сообщения в телеграм: '
                                      f'{error}'))


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise requests.HTTPError(response)
        return response.json()
    except requests.exceptions.RequestException as error:
        raise Exception(f'Ошибка при запросе к эндпойнту: {error}')
    except json.decoder.JSONDecodeError as error:
        raise Exception((f'Ответ {response.text} получен не в виде JSON: '
                         f'{error}'))


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) is not dict:
        raise TypeError('Ответ получен не в виде словаря')
    key = 'homeworks'
    if key not in response:
        raise KeyError(f'В response нет ключа {key}')
    if type(response[key]) is not list:
        raise TypeError('Домашняя работа получена не в виде списка')
    return response[key]


def parse_status(homework):
    """Извлекает информацию о статусе домашней работы."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError as e:
        raise KeyError(f'В словаре домашней работы нет ключа {e}')

    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError(('Недокументированный статус домашней '
                        f'работы: {homework_status}'))
    verdict = HOMEWORK_STATUSES[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    if (PRACTICUM_TOKEN is None or TELEGRAM_TOKEN is None
            or TELEGRAM_CHAT_ID is None):
        return False
    else:
        return True


def main():
    """Основная логика работы бота."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные окружения!')
        return

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_error_message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.debug('Нет обновлений в статусах работ')
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)
                logger.info(('Сообщение отправленно в телеграм: '
                             f'{message}'))
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if last_error_message != message:
                try:
                    send_message(bot, message)
                    last_error_message = message
                except Exception as send_error:
                    message = ('Сбой при отправке сообщения об ошибке: '
                               f'{send_error}')
                    logger.error(message)
            time.sleep(RETRY_TIME)
        else:
            logger.error('Сбой в работе программы')


if __name__ == '__main__':
    main()
