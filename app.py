from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime, timedelta
import logging
import json
from threading import Thread
import time
import sqlite3

app = Flask(__name__)

# ============ КОНФИГУРАЦИЯ ============
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI')
VETMANAGER_API_KEY = os.environ.get('VETMANAGER_KEY', '29607ccc63c684fa672be9694f7f09ec')
VETMANAGER_DOMAIN = os.environ.get('VETMANAGER_DOMAIN', 'drug14.vetmanager2.ru')
ADMIN_ID = os.environ.get('ADMIN_ID', '921853682')

# Основной URL API (ДОБАВЛЯЕМ https://!)
CLINIC_URL = f"https://{VETMANAGER_DOMAIN}"
API_BASE_URL = f"{CLINIC_URL}/rest/api"
HEADERS = {
    'X-REST-API-KEY': VETMANAGER_API_KEY,
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# База данных для хранения связей client_id ↔ telegram_chat_id
DB_FILE = 'vetmanager_bot.db'

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    
    # Таблица для связи клиентов с Telegram
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS client_telegram (
            client_id INTEGER PRIMARY KEY,
            telegram_chat_id INTEGER,
            phone TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица для отправленных напоминаний
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_reminders (
            admission_id INTEGER,
            client_id INTEGER,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (admission_id, client_id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ============ РАБОЧИЕ API ФУНКЦИИ ============

def make_vetmanager_request(endpoint, params=None, method='GET'):
    """Универсальная функция для запросов к VetManager REST API"""
    try:
        url = f"{API_BASE_URL}/{endpoint}"
        
        logger.info(f"🔍 Запрос: {method} {url}")
        if params:
            logger.info(f"📋 Параметры: {params}")
        
        if method == 'GET':
            response = requests.get(
                url,
                headers=HEADERS,
                params=params,
                timeout=10
            )
        elif method == 'POST':
            response = requests.post(
                url,
                headers=HEADERS,
                json=params,
                timeout=10
            )
        else:
            return {'success': False, 'error': 'Метод не поддерживается'}
        
        logger.info(f"📥 Ответ: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            return {'success': True, 'data': data}
        else:
            error_text = response.text[:200] if response.text else 'Нет текста ошибки'
            return {'success': False, 'error': f'HTTP {response.status_code}: {error_text}'}
            
    except Exception as e:
        logger.error(f"🔥 Исключение: {str(e)}")
        return {'success': False, 'error': str(e)}

def test_api_connection():
    """Тестируем подключение к API"""
    logger.info(f"🏥 Клиника: {CLINIC_URL}")
    logger.info(f"🔑 API ключ: {VETMANAGER_API_KEY[:8]}...")
    
    # Тест: Получить список пользователей
    result = make_vetmanager_request('user', {'limit': 2})
    
    if result['success']:
        data = result['data']
        if data.get('success'):
            user_count = data.get('data', {}).get('totalCount', 0)
            logger.info(f"✅ API работает! Пользователей в системе: {user_count}")
            return {
                'success': True,
                'clinic_url': CLINIC_URL,
                'user_count': user_count,
                'message': 'API подключено успешно'
            }
    
    return {
        'success': False,
        'clinic_url': CLINIC_URL,
        'error': result.get('error', 'Неизвестная ошибка'),
        'message': 'API не отвечает'
    }

def get_clients(limit=10, offset=0):
    """Получить список клиентов"""
    params = {'limit': limit, 'offset': offset}
    result = make_vetmanager_request('client', params)
    
    if result['success'] and result['data'].get('success'):
        clients = result['data'].get('data', {}).get('client', [])
        return {'success': True, 'clients': clients, 'total': len(clients)}
    
    return result

def get_client_by_id(client_id):
    """Получить клиента по ID"""
    result = make_vetmanager_request(f'client/{client_id}')
    
    if result['success'] and result['data'].get('success'):
        client = result['data'].get('data', {})
        return {'success': True, 'client': client}
    
    return result

def get_tomorrow_appointments():
    """Получить записи на завтра"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    params = {
        'date_from': tomorrow,
        'date_to': tomorrow,
        'limit': 50,
        'sort': '[{"property":"time", "direction":"ASC"}]'
    }
    
    result = make_vetmanager_request('admission', params)
    
    if result['success'] and result['data'].get('success'):
        appointments = result['data'].get('data', {}).get('admission', [])
        return {'success': True, 'appointments': appointments, 'date': tomorrow}
    
    return result

def get_pet_by_id(pet_id):
    """Получить питомца по ID"""
    result = make_vetmanager_request(f'pet/{pet_id}')
    
    if result['success'] and result['data'].get('success'):
        pet = result['data'].get('data', {})
        return {'success': True, 'pet': pet}
    
    return result

# ============ БАЗА ДАННЫХ ============

def save_client_telegram_link(client_id, telegram_chat_id, phone=None, first_name=None, last_name=None):
    """Сохранить связь client_id ↔ telegram_chat_id"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO client_telegram 
        (client_id, telegram_chat_id, phone, first_name, last_name)
        VALUES (?, ?, ?, ?, ?)
    ''', (client_id, telegram_chat_id, phone, first_name, last_name))
    
    conn.commit()
    conn.close()
    return True

def get_telegram_chat_id(client_id):
    """Получить telegram_chat_id по client_id"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT telegram_chat_id FROM client_telegram WHERE client_id = ?', (client_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else None

def mark_reminder_sent(admission_id, client_id):
    """Пометить напоминание как отправленное"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR IGNORE INTO sent_reminders (admission_id, client_id)
        VALUES (?, ?)
    ''', (admission_id, client_id))
    
    conn.commit()
    conn.close()
    return True

def is_reminder_sent(admission_id, client_id):
    """Проверить, было ли уже отправлено напоминание"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 1 FROM sent_reminders 
        WHERE admission_id = ? AND client_id = ?
    ''', (admission_id, client_id))
    
    result = cursor.fetchone()
    conn.close()
    return result is not None

# ============ TELEGRAM ФУНКЦИИ ============

def send_telegram_message(chat_id, text):
    """Отправить сообщение в Telegram"""
    try:
        url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Ошибка отправки в Telegram: {str(e)}")
        return False

# ============ ОСНОВНАЯ ЛОГИКА ============

def send_appointment_reminders():
    """Основная функция: отправка напоминаний о завтрашних приемах"""
    logger.info("🔔 Проверяем завтрашние записи...")
    
    # 1. Получаем завтрашние записи
    appointments_result = get_tomorrow_appointments()
    
    if not appointments_result['success']:
        logger.error(f"❌ Не удалось получить записи: {appointments_result.get('error')}")
        return
    
    appointments = appointments_result.get('appointments', [])
    
    if not appointments:
        logger.info("📭 Нет записей на завтра")
        send_telegram_message(ADMIN_ID, "📭 На завтра нет записей на прием")
        return
    
    logger.info(f"📅 Найдено записей на завтра: {len(appointments)}")
    
    sent_count = 0
    skipped_count = 0
    
    # 2. Для каждой записи отправляем напоминание
    for appointment in appointments:
        appointment_id = appointment.get('id')
        client_id = appointment.get('client_id')
        pet_id = appointment.get('pet_id')
        appt_time = appointment.get('time', '')
        doctor_id = appointment.get('user_id')
        
        # Проверяем, не отправляли ли уже напоминание
        if is_reminder_sent(appointment_id, client_id):
            logger.info(f"⏭️ Напоминание для записи {appointment_id} уже отправлено")
            skipped_count += 1
            continue
        
        # Получаем Telegram chat_id клиента
        telegram_chat_id = get_telegram_chat_id(client_id)
        
        if not telegram_chat_id:
            logger.warning(f"⚠️ У клиента {client_id} нет привязанного Telegram")
            skipped_count += 1
            continue
        
        # Получаем информацию о клиенте
        client_result = get_client_by_id(client_id)
        client_name = "Клиент"
        pet_name = "питомец"
        
        if client_result['success']:
            client = client_result.get('client', {})
            client_name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
            if not client_name:
                client_name = "Клиент"
        
        # Получаем информацию о питомце
        if pet_id:
            pet_result = get_pet_by_id(pet_id)
            if pet_result['success']:
                pet = pet_result.get('pet', {})
                pet_name = pet.get('alias', 'питомец')
        
        # Формируем сообщение
        message = f"""
🩺 <b>Напоминание о записи</b>

👤 <b>Клиент:</b> {client_name}
🐾 <b>Питомец:</b> {pet_name}
🕒 <b>Время:</b> {appt_time}
🏥 <b>Клиника:</b> ЗооВетЦентр "Друг"

Пожалуйста, приходите за 10-15 минут до назначенного времени.
        """.strip()
        
        # Отправляем сообщение
        if send_telegram_message(telegram_chat_id, message):
            logger.info(f"✅ Отправлено напоминание клиенту {client_id}")
            mark_reminder_sent(appointment_id, client_id)
            sent_count += 1
        else:
            logger.error(f"❌ Ошибка отправки клиенту {client_id}")
    
    # Отчет админу
    report = f"""
📊 <b>Отчет по напоминаниям</b>
📅 Дата: {appointments_result['date']}
✅ Отправлено: {sent_count}
⏭️ Пропущено: {skipped_count}
📝 Всего записей: {len(appointments)}
    """.strip()
    
    send_telegram_message(ADMIN_ID, report)

# ============ WEB РОУТЫ ============

@app.route('/')
def home():
    test_result = test_api_connection()
    
    if test_result['success']:
        return f'''
        <h1>🤖 VetManager Reminder Bot</h1>
        <p>✅ <b>Статус:</b> API работает</p>
        <p>🏥 <b>Клиника:</b> {CLINIC_URL}</p>
        <p>👥 <b>Пользователей:</b> {test_result.get('user_count', 'N/A')}</p>
        
        <h3>Доступные эндпоинты:</h3>
        <ul>
            <li><a href="/test">/test</a> - Проверка API</li>
            <li><a href="/clients">/clients</a> - Список клиентов</li>
            <li><a href="/appointments">/appointments</a> - Записи на завтра</li>
            <li><a href="/send-reminders">/send-reminders</a> - Отправить напоминания (вручную)</li>
        </ul>
        
        <h3>Telegram бот:</h3>
        <p>Бот: <a href="https://t.me/Fulsim_bot">@Fulsim_bot</a></p>
        <p>Для привязки Telegram напишите боту: <code>/start ваш_номер_телефона</code></p>
        '''
    else:
        return f'''
        <h1>🤖 VetManager Reminder Bot</h1>
        <p>❌ <b>Статус:</b> API не работает</p>
        <p>🏥 <b>Клиника:</b> {CLINIC_URL}</p>
        <p>📝 <b>Ошибка:</b> {test_result.get('error', 'Неизвестно')}</p>
        
        <h3>Проверьте:</h3>
        <ol>
            <li>API ключ в настройках VetManager</li>
            <li>Права доступа API ключа</li>
            <li>URL клиники: {CLINIC_URL}</li>
        </ol>
        '''

@app.route('/test')
def test():
    result = test_api_connection()
    return jsonify(result)

@app.route('/clients')
def clients():
    result = get_clients(limit=20)
    if result['success']:
        clients_data = result.get('clients', [])
        html = f'<h1>👥 Клиенты ({len(clients_data)})</h1>'
        
        for client in clients_data:
            html += f'''
            <div style="border:1px solid #ccc; padding:10px; margin:10px;">
                <h3>ID: {client.get('id')} - {client.get('first_name', '')} {client.get('last_name', '')}</h3>
                <p>📞 Телефон: {client.get('phone', '')}</p>
                <p>✉️ Email: {client.get('email', '')}</p>
            </div>
            '''
        return html
    else:
        return f'<h1>❌ Ошибка</h1><p>{result.get("error")}</p>'

@app.route('/appointments')
def appointments():
    result = get_tomorrow_appointments()
    if result['success']:
        appointments_data = result.get('appointments', [])
        html = f'<h1>📅 Записи на завтра ({result["date"]})</h1>'
        html += f'<p>Найдено: {len(appointments_data)} записей</p>'
        
        for appt in appointments_data:
            html += f'''
            <div style="border:1px solid #ccc; padding:10px; margin:10px;">
                <h3>🕒 {appt.get('time', '')}</h3>
                <p>👤 Клиент ID: {appt.get('client_id')}</p>
                <p>🐾 Питомец ID: {appt.get('pet_id')}</p>
                <p>👨‍⚕️ Врач ID: {appt.get('user_id')}</p>
            </div>
            '''
        return html
    else:
        return f'<h1>❌ Ошибка</h1><p>{result.get("error")}</p>'

@app.route('/send-reminders')
def send_reminders():
    """Ручной запуск отправки напоминаний"""
    send_appointment_reminders()
    return jsonify({'success': True, 'message': 'Напоминания отправлены'})

# ============ TELEGRAM WEBHOOK ============

@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """Webhook для Telegram бота"""
    update = request.json
    
    if 'message' in update:
        message = update['message']
        chat_id = message['chat']['id']
        text = message.get('text', '')
        
        # Команда /start
        if text.startswith('/start'):
            if len(text.split()) > 1:
                # /start + номер телефона
                phone = text.split()[1]
                
                # Ищем клиента по номеру телефона
                clients_result = get_clients(limit=100)
                if clients_result['success']:
                    found_client = None
                    for client in clients_result.get('clients', []):
                        if client.get('phone', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '') == phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', ''):
                            found_client = client
                            break
                    
                    if found_client:
                        # Сохраняем связь
                        save_client_telegram_link(
                            found_client['id'],
                            chat_id,
                            phone,
                            found_client.get('first_name'),
                            found_client.get('last_name')
                        )
                        
                        response_text = f"""
✅ <b>Привязка успешна!</b>

👤 <b>Клиент:</b> {found_client.get('first_name', '')} {found_client.get('last_name', '')}
📞 <b>Телефон:</b> {phone}
🏥 <b>Клиника:</b> ЗооВетЦентр "Друг"

Теперь вы будете получать напоминания о записях на прием за день до визита.
                        """.strip()
                    else:
                        response_text = f"❌ Клиент с номером {phone} не найден в базе VetManager."
                else:
                    response_text = "❌ Ошибка доступа к базе клиентов."
            else:
                response_text = """
🤖 <b>Добро пожаловать в VetManager Reminder Bot!</b>

Для привязки вашего аккаунта отправьте:
<code>/start ваш_номер_телефона</code>

Например: <code>/start 79283190225</code>

После привязки вы будете получать напоминания о записях на прием за день до визита.
                """.strip()
            
            send_telegram_message(chat_id, response_text)
        
        # Команда /help
        elif text == '/help':
            help_text = """
📋 <b>Доступные команды:</b>

/start - Начать работу с ботом
/help - Показать это сообщение
/mydata - Показать мои привязанные данные
/unlink - Отвязать Telegram от VetManager

Для привязки отправьте:
<code>/start ваш_номер_телефона</code>
            """.strip()
            send_telegram_message(chat_id, help_text)
        
        # Команда /mydata
        elif text == '/mydata':
            # Найти client_id по telegram_chat_id
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM client_telegram WHERE telegram_chat_id = ?', (chat_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                client_id, _, phone, first_name, last_name, registered_at = result
                data_text = f"""
📋 <b>Ваши данные:</b>

👤 <b>Клиент ID:</b> {client_id}
📞 <b>Телефон:</b> {phone}
👤 <b>Имя:</b> {first_name or 'Не указано'} {last_name or ''}
📅 <b>Привязано:</b> {registered_at}
                """.strip()
            else:
                data_text = "❌ Ваш Telegram не привязан к клиенту VetManager."
            
            send_telegram_message(chat_id, data_text)
        
        # Команда /unlink
        elif text == '/unlink':
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM client_telegram WHERE telegram_chat_id = ?', (chat_id,))
            conn.commit()
            conn.close()
            
            send_telegram_message(chat_id, "✅ Ваш Telegram успешно отвязан от VetManager.")
    
    return jsonify({'ok': True})

# ============ ЗАПУСК ============

def schedule_reminders():
    """Запуск отправки напоминаний по расписанию"""
    while True:
        now = datetime.now()
        
        # Проверяем каждый день в 18:00
        if now.hour == 18 and now.minute == 0:
            logger.info("🕕 18:00 - отправляем напоминания на завтра")
            send_appointment_reminders()
        
        time.sleep(60)  # Проверяем каждую минуту

if __name__ == '__main__':
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = Thread(target=schedule_reminders, daemon=True)
    scheduler_thread.start()
    
    # Тестируем подключение
    test_result = test_api_connection()
    if test_result['success']:
        print(f"🚀 VetManager Bot запущен!")
        print(f"🏥 Клиника: {CLINIC_URL}")
        print(f"👥 Пользователей: {test_result.get('user_count')}")
        print(f"🤖 Telegram бот: @Fulsim_bot")
        print(f"🌐 Web интерфейс: http://localhost:5000")
    else:
        print(f"❌ Ошибка: {test_result.get('error')}")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
