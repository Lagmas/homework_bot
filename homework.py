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
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

PERIOD_TIME = 10
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
        raise telegram.TelegramError('Ошибка отправки сообщения в телеграм: '
                                     f'{error}')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': current_timestamp}
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
    if not isinstance(response, dict):
        raise TypeError('Ответ получен не в виде словаря')
    key = 'homeworks'
    if key not in response:
        raise KeyError(f'В response нет ключа {key}')
    if not isinstance(response[key], list):
        raise TypeError('Домашняя работа получена не в виде списка')
    return response[key]


def parse_status(homework):
    """Извлекает информацию о статусе домашней работы."""
    if not isinstance(homework, dict):
        raise TypeError('Формат ответа API отличается от ожидаемого')
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
    tokens = {
        'practicum_token': PRACTICUM_TOKEN,
        'telegram_token': TELEGRAM_TOKEN,
        'telegram_chat_id': TELEGRAM_CHAT_ID,
    }
    result = True
    for key, value in tokens.items():
        if value is None:
            logging.error(f'{key} не обнаружен')
            result = False
            continue
    return result


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные окружения!')
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time() - PERIOD_TIME)
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
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
        finally:
            time.sleep(RETRY_TIME - PERIOD_TIME)


if __name__ == '__main__':
    main()
