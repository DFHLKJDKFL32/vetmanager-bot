from flask import Flask, jsonify, request
import requests
from datetime import datetime, timedelta
import logging

app = Flask(__name__)

# ============ КОНФИГУРАЦИЯ ============
TELEGRAM_TOKEN = '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI'
VETMANAGER_API_KEY = '29607ccc63c684fa672be9694f7f09ec'
VETMANAGER_BASE_URL = 'https://drug14.vetmanager2.ru/index.php'
ADMIN_ID = 921853682  # Твой Telegram ID

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# =======================================

def vetmanager_request(endpoint, params=None, method='GET'):
    """
    Универсальная функция для запросов к VetManager API
    """
    base_params = {
        'module': 'ApiRest',
        'key': VETMANAGER_API_KEY
    }
    
    if params:
        base_params.update(params)
    
    try:
        if method == 'GET':
            response = requests.get(
                VETMANAGER_BASE_URL,
                params=base_params,
                timeout=10
            )
        elif method == 'POST':
            response = requests.post(
                VETMANAGER_BASE_URL,
                data=base_params,
                timeout=10
            )
        else:
            return {'success': False, 'error': 'Метод не поддерживается'}
        
        if response.status_code == 200:
            return {'success': True, 'data': response.json()}
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}: {response.text}'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============ ОСНОВНЫЕ ФУНКЦИИ API ============

def get_clients(limit=10, offset=0):
    """Получить список клиентов"""
    params = {
        'object': 'Client',
        'action': 'get',
        'limit': limit,
        'offset': offset
    }
    return vetmanager_request('', params)

def get_client_by_id(client_id):
    """Получить клиента по ID"""
    params = {
        'object': 'Client',
        'action': 'getById',
        'id': client_id
    }
    return vetmanager_request('', params)

def get_appointments(date_from=None, date_to=None):
    """Получить записи на прием"""
    if not date_from:
        date_from = datetime.now().strftime('%Y-%m-%d')
    if not date_to:
        date_to = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    
    params = {
        'object': 'Admission',
        'action': 'get',
        'date_from': date_from,
        'date_to': date_to
    }
    return vetmanager_request('', params)

def get_pets(client_id=None):
    """Получить питомцев"""
    params = {
        'object': 'Pet',
        'action': 'get'
    }
    if client_id:
        params['client_id'] = client_id
    return vetmanager_request('', params)

def create_appointment(client_id, pet_id, date, time, doctor_id, description=""):
    """Создать запись на прием"""
    params = {
        'object': 'Admission',
        'action': 'create',
        'client_id': client_id,
        'pet_id': pet_id,
        'date': date,
        'time': time,
        'doctor_id': doctor_id,
        'description': description
    }
    return vetmanager_request('', params, method='POST')

# ============ WEB INTERFACE ============

@app.route('/')
def home():
    """Главная страница"""
    return '''
    <h1>🤖 VetManager Bot API</h1>
    <h3>Доступные эндпоинты:</h3>
    <ul>
        <li><a href="/test">/test</a> - Проверка API</li>
        <li><a href="/clients">/clients</a> - Список клиентов (10 штук)</li>
        <li><a href="/appointments/today">/appointments/today</a> - Записи на сегодня</li>
        <li><a href="/appointments/week">/appointments/week</a> - Записи на неделю</li>
    </ul>
    <p>API ключ: 29607ccc63c684fa672be9694f7f09ec</p>
    '''

@app.route('/test')
def test_api():
    """Тест подключения к VetManager"""
    result = get_clients(limit=1)
    
    if result['success']:
        return jsonify({
            'status': 'success',
            'message': '✅ VetManager API работает отлично!',
            'data': result['data']
        })
    else:
        return jsonify({
            'status': 'error',
            'message': '❌ Ошибка подключения',
            'error': result['error']
        })

@app.route('/clients')
def show_clients():
    """Показать клиентов"""
    result = get_clients(limit=10)
    
    if result['success']:
        clients = result['data'].get('data', [])
        
        html = '<h1>👥 Клиенты VetManager</h1>'
        html += f'<p>Найдено: {len(clients)} клиентов</p>'
        
        for client in clients:
            html += f'''
            <div style="border:1px solid #ccc; padding:10px; margin:10px;">
                <h3>{client.get('first_name', '')} {client.get('last_name', '')}</h3>
                <p>ID: {client.get('id', '')}</p>
                <p>Телефон: {client.get('phone', '')}</p>
                <p>Email: {client.get('email', '')}</p>
            </div>
            '''
        
        return html
    else:
        return f'<h1>❌ Ошибка</h1><p>{result["error"]}</p>'

@app.route('/appointments/today')
def appointments_today():
    """Записи на сегодня"""
    today = datetime.now().strftime('%Y-%m-%d')
    result = get_appointments(date_from=today, date_to=today)
    
    if result['success']:
        appointments = result['data'].get('data', [])
        
        html = f'<h1>📅 Записи на сегодня ({today})</h1>'
        html += f'<p>Найдено: {len(appointments)} записей</p>'
        
        for appt in appointments:
            html += f'''
            <div style="border:1px solid #ccc; padding:10px; margin:10px;">
                <h3>ID: {appt.get('id', '')}</h3>
                <p>Время: {appt.get('time', '')}</p>
                <p>Клиент ID: {appt.get('client_id', '')}</p>
                <p>Питомец ID: {appt.get('pet_id', '')}</p>
                <p>Врач ID: {appt.get('doctor_id', '')}</p>
            </div>
            '''
        
        return html
    else:
        return f'<h1>❌ Ошибка</h1><p>{result["error"]}</p>'

@app.route('/appointments/week')
def appointments_week():
    """Записи на неделю"""
    result = get_appointments()
    
    if result['success']:
        appointments = result['data'].get('data', [])
        
        html = '<h1>📅 Записи на неделю</h1>'
        html += f'<p>Найдено: {len(appointments)} записей</p>'
        
        for appt in appointments:
            html += f'''
            <div style="border:1px solid #ccc; padding:10px; margin:10px;">
                <h3>Дата: {appt.get('date', '')} {appt.get('time', '')}</h3>
                <p>ID: {appt.get('id', '')}</p>
                <p>Клиент ID: {appt.get('client_id', '')}</p>
                <p>Питомец ID: {appt.get('pet_id', '')}</p>
            </div>
            '''
        
        return html
    else:
        return f'<h1>❌ Ошибка</h1><p>{result["error"]}</p>'

# ============ TELEGRAM BOT (ПРОСТОЙ ВАРИАНТ) ============

@app.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    """Webhook для Telegram"""
    update = request.json
    
    if 'message' in update:
        chat_id = update['message']['chat']['id']
        text = update['message'].get('text', '')
        
        if text == '/start':
            message = 'Привет! Я бот для VetManager. Используй /clients чтобы увидеть клиентов'
        elif text == '/clients':
            result = get_clients(limit=5)
            if result['success']:
                clients = result['data'].get('data', [])
                message = f'Найдено {len(clients)} клиентов:\n\n'
                for client in clients:
                    message += f"👤 {client.get('first_name', '')} {client.get('last_name', '')}\n📞 {client.get('phone', '')}\n\n"
            else:
                message = '❌ Ошибка при получении клиентов'
        elif text == '/today':
            today = datetime.now().strftime('%Y-%m-%d')
            result = get_appointments(date_from=today, date_to=today)
            if result['success']:
                appointments = result['data'].get('data', [])
                message = f'📅 Записи на сегодня: {len(appointments)}\n\n'
                for appt in appointments:
                    message += f"🕒 {appt.get('time', '')}\n"
            else:
                message = '❌ Ошибка при получении записей'
        else:
            message = 'Доступные команды:\n/clients - список клиентов\n/today - записи на сегодня'
        
        # Отправляем ответ в Telegram
        send_telegram_message(chat_id, message)
    
    return jsonify({'ok': True})

def send_telegram_message(chat_id, text):
    """Отправить сообщение в Telegram"""
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    data = {
        'chat_id': chat_id,
        'text': text
    }
    requests.post(url, json=data)

# ============ ЗАПУСК ============

if __name__ == '__main__':
    print("🚀 VetManager Bot запущен!")
    print(f"📊 Проверь API: http://localhost:5000/test")
    print(f"👥 Клиенты: http://localhost:5000/clients")
    print(f"📅 Записи: http://localhost:5000/appointments/today")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
