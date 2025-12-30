import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import logging
import re
import json

app = Flask(__name__)

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI'
VETMANAGER_KEY = '487bc6-4a39ee-be14b6-1ef17a-be257f'  # Ключ от Вазапы
VETMANAGER_DOMAIN = 'drug14.vetmanager2.ru'
VETMANAGER_URL = f'https://{VETMANAGER_DOMAIN}'
ADMIN_ID = 921853682

# Данные клиники
CLINIC_INFO = {
    'name': 'Ветеринарная Клиника Друг',
    'address': 'ул. Апанасенко 15Г, г. Невинномысск',
    'phones': ['+7(928)319-02-25', '+7(962)017-38-24'],
    'working_hours': 'ПН-СБ 09:00-18:00, ВС 10:00-17:00'
}

# Настройки логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

user_sessions = {}

# ========== VETMANAGER API - ИСПРАВЛЕННАЯ ВЕРСИЯ ==========
def test_vetmanager_connection():
    """Тестирует подключение к Vetmanager"""
    logger.info("🔌 Тестирую подключение к Vetmanager API...")
    
    # Пробуем разные варианты заголовков
    headers_variants = [
        {"X-User-Token": VETMANAGER_KEY},
        {"Authorization": f"Bearer {VETMANAGER_KEY}"},
        {"X-API-Key": VETMANAGER_KEY},
        {"X-User-Token": VETMANAGER_KEY, "Accept": "application/json"},
        {"X-User-Token": VETMANAGER_KEY, "Content-Type": "application/json"}
    ]
    
    endpoints = ['clinics', 'clients', 'users', 'pets']
    
    for headers in headers_variants:
        for endpoint in endpoints:
            url = f"{VETMANAGER_URL}/api/{endpoint}"
            
            try:
                logger.info(f"Пробую {endpoint} с заголовками: {headers.keys()}")
                response = requests.get(url, headers=headers, params={"limit": 1}, timeout=10)
                
                logger.info(f"Статус: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if isinstance(data, dict):
                            if 'data' in data:
                                logger.info(f"✅ Успех! Endpoint: {endpoint}, Данных: {len(data['data'])}")
                                
                                # Получаем общее количество клиентов
                                if endpoint == 'clients':
                                    clients_response = requests.get(
                                        f"{VETMANAGER_URL}/api/clients",
                                        headers=headers,
                                        params={"limit": 50},
                                        timeout=10
                                    )
                                    
                                    if clients_response.status_code == 200:
                                        clients_data = clients_response.json()
                                        client_count = len(clients_data.get('data', []))
                                        return True, client_count, headers
                                
                                return True, len(data['data']), headers
                            else:
                                logger.warning(f"Нет поля 'data' в ответе: {data.keys()}")
                        else:
                            logger.warning(f"Ответ не словарь: {type(data)}")
                    except json.JSONDecodeError:
                        logger.error(f"❌ Невалидный JSON от {endpoint}")
                        logger.error(f"Ответ: {response.text[:500]}")
                
                elif response.status_code == 401:
                    logger.error(f"❌ 401 Unauthorized для {endpoint}")
                elif response.status_code == 403:
                    logger.error(f"❌ 403 Forbidden для {endpoint}")
                elif response.status_code == 404:
                    logger.warning(f"⚠️ 404 Not Found для {endpoint}")
                else:
                    logger.warning(f"⚠️ Статус {response.status_code} для {endpoint}")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Ошибка запроса к {endpoint}: {e}")
    
    logger.error("❌ Не удалось подключиться к Vetmanager API")
    return False, 0, None

# Глобальные переменные для хранения рабочей конфигурации
API_HEADERS = None
API_WORKING = False

def init_vetmanager_api():
    """Инициализирует подключение к Vetmanager API"""
    global API_HEADERS, API_WORKING
    
    logger.info("🚀 Инициализация Vetmanager API...")
    
    # Тестируем разные варианты подключения
    working, client_count, headers = test_vetmanager_connection()
    
    if working and headers:
        API_HEADERS = headers
        API_WORKING = True
        logger.info(f"✅ API настроен! Клиентов: {client_count}")
        logger.info(f"✅ Используемые заголовки: {API_HEADERS}")
        
        # Тестовый запрос для проверки
        test_url = f"{VETMANAGER_URL}/api/clients?limit=1"
        response = requests.get(test_url, headers=API_HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data'):
                client = data['data'][0]
                logger.info(f"📋 Пример клиента: ID={client.get('id')}, Имя={client.get('firstName')}, Телефон={client.get('phone')}")
    else:
        logger.error("❌ Не удалось инициализировать API")
        API_WORKING = False
    
    return API_WORKING

def make_api_request(endpoint, params=None):
    """Выполняет запрос к API Vetmanager"""
    if not API_WORKING or not API_HEADERS:
        logger.error("❌ API не инициализирован")
        return None
    
    url = f"{VETMANAGER_URL}/api/{endpoint}"
    
    try:
        logger.info(f"📡 API запрос: {endpoint}, параметры: {params}")
        response = requests.get(url, headers=API_HEADERS, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Успешный запрос к {endpoint}")
            return data
        else:
            logger.error(f"❌ Ошибка API {endpoint}: {response.status_code}")
            logger.error(f"Ответ: {response.text[:200]}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Исключение при запросе к {endpoint}: {e}")
        return None

def find_real_client(phone_number):
    """Ищет реального клиента в Vetmanager"""
    logger.info(f"🔍 Поиск реального клиента по телефону: {phone_number}")
    
    if not API_WORKING:
        logger.warning("⚠️ API не работает, возвращаю None")
        return None
    
    # Очищаем номер
    phone_clean = re.sub(r'\D', '', str(phone_number))
    
    # Пробуем разные форматы для поиска
    search_variants = []
    
    if len(phone_clean) == 11:
        if phone_clean.startswith('7'):
            search_variants = [phone_clean, phone_clean[1:], f"8{phone_clean[1:]}"]
        elif phone_clean.startswith('8'):
            search_variants = [phone_clean, f"7{phone_clean[1:]}", phone_clean[1:]]
    elif len(phone_clean) == 10:
        search_variants = [f"7{phone_clean}", f"8{phone_clean}", phone_clean]
    
    for phone_variant in search_variants:
        params = {"filter[phone]": phone_variant, "limit": 1}
        result = make_api_request('clients', params)
        
        if result and 'data' in result and result['data']:
            client_data = result['data'][0]
            client_id = client_data.get('id')
            
            logger.info(f"✅ Найден реальный клиент ID: {client_id}")
            
            # Получаем полную информацию
            full_info = get_full_client_info(client_id)
            if full_info:
                client_data.update(full_info)
            
            return client_data
    
    logger.warning(f"⚠️ Реальный клиент не найден по номеру: {phone_number}")
    return None

def get_full_client_info(client_id):
    """Получает полную информацию о клиенте"""
    client_info = {}
    
    try:
        # 1. Питомцы клиента
        pets_result = make_api_request('pets', {"filter[client_id]": client_id, "limit": 10})
        if pets_result and 'data' in pets_result:
            client_info['pets'] = pets_result['data']
            logger.info(f"✅ Найдено питомцев: {len(client_info['pets'])}")
        
        # 2. Записи на прием (будущие)
        today = datetime.now().strftime('%Y-%m-%d')
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        
        appointments_result = make_api_request('appointments', {
            "filter[client_id]": client_id,
            "filter[date_from]": today,
            "filter[date_to]": future_date,
            "sort": "date",
            "limit": 5
        })
        
        if appointments_result and 'data' in appointments_result:
            client_info['appointments'] = appointments_result['data']
            logger.info(f"✅ Найдено записей: {len(client_info['appointments'])}")
        
        # 3. Баланс (из счетов)
        invoices_result = make_api_request('invoice', {
            "filter[client_id]": client_id,
            "limit": 20
        })
        
        if invoices_result and 'data' in invoices_result:
            balance = 0
            for invoice in invoices_result['data']:
                status = invoice.get('status', '')
                amount = float(invoice.get('amount', 0))
                
                if status == 'UNPAID':
                    balance += amount
                elif status == 'PAID':
                    balance -= amount
            
            client_info['balance'] = balance
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения полной информации: {e}")
    
    return client_info

# ========== TELEGRAM ФУНКЦИИ ==========
def send_telegram_message(chat_id, text, parse_mode='HTML'):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в Telegram: {e}")
        return None

def format_client_info(client_data, is_real_data=True):
    """Форматирует информацию о клиенте"""
    lines = []
    
    if is_real_data:
        lines.append("✅ <b>ВАША КАРТА КЛИЕНТА (РЕАЛЬНЫЕ ДАННЫЕ)</b>")
        lines.append("<i>Данные загружены из системы Vetmanager</i>")
    else:
        lines.append("⚠️ <b>ВАША КАРТА КЛИЕНТА (ДЕМО-ДАННЫЕ)</b>")
        lines.append("<i>Реальная база временно недоступна</i>")
    
    lines.append("══════════════════════════════════")
    
    # Основная информация
    first_name = client_data.get('firstName', '')
    last_name = client_data.get('lastName', '')
    
    if first_name or last_name:
        full_name = f"{last_name} {first_name}".strip()
        lines.append(f"👤 <b>Клиент:</b> {full_name}")
    
    phone = client_data.get('phone', '')
    if phone:
        lines.append(f"📞 <b>Телефон:</b> {phone}")
    
    email = client_data.get('email', '')
    if email:
        lines.append(f"📧 <b>Email:</b> {email}")
    
    balance = client_data.get('balance', 0)
    if balance != 0:
        lines.append(f"💰 <b>Баланс:</b> {balance:.2f} руб.")
    
    lines.append("")
    
    # Питомцы
    pets = client_data.get('pets', [])
    if pets:
        lines.append("🐾 <b>ВАШИ ПИТОМЦЫ:</b>")
        
        for i, pet in enumerate(pets[:5], 1):
            pet_name = pet.get('alias', 'Без имени')
            pet_type = pet.get('type_title', pet.get('type', ''))
            breed = pet.get('breed_title', pet.get('breed', ''))
            
            pet_info = f"{i}. <b>{pet_name}</b>"
            
            details = []
            if pet_type:
                details.append(pet_type)
            if breed:
                details.append(breed)
            
            if details:
                pet_info += f" ({', '.join(details)})"
            
            lines.append(pet_info)
        
        if len(pets) > 5:
            lines.append(f"... и ещё {len(pets) - 5} питомцев")
    else:
        lines.append("🐾 <b>Питомцы:</b> нет")
    
    lines.append("")
    
    # Записи на прием
    appointments = client_data.get('appointments', [])
    if appointments:
        lines.append("📅 <b>БЛИЖАЙШИЕ ЗАПИСИ:</b>")
        
        for i, app in enumerate(appointments[:3], 1):
            date = app.get('date', '')
            time = app.get('time', '10:00')
            
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                date_str = date_obj.strftime('%d.%m.%Y')
            except:
                date_str = date
            
            lines.append(f"{i}. {date_str} в {time}")
    else:
        lines.append("📅 <b>Ближайшие записи:</b> нет")
    
    # Информация о клинике
    lines.append("")
    lines.append("══════════════════════════════════")
    lines.append(f"🏥 <b>{CLINIC_INFO['name']}</b>")
    lines.append(f"📍 <b>Адрес:</b> {CLINIC_INFO['address']}")
    lines.append(f"📞 <b>Телефон:</b> {CLINIC_INFO['phones'][0]}")
    lines.append(f"⏰ <b>Часы работы:</b> {CLINIC_INFO['working_hours']}")
    
    if not is_real_data:
        lines.append("")
        lines.append("⚠️ <i>Для получения реальных данных обратитесь на ресепшн</i>")
    
    return "\n".join(lines)

# ========== TELEGRAM WEBHOOK ==========
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Обработчик вебхука от Telegram"""
    try:
        data = request.get_json()
        
        if 'message' in data:
            message = data['message']
            chat_id = message['chat']['id']
            text = message.get('text', '').strip()
            
            logger.info(f"📨 Сообщение от {chat_id}: {text}")
            
            if text == '/start':
                handle_start(chat_id)
            elif text == '/testapi':
                handle_test_api(chat_id)
            elif chat_id in user_sessions and user_sessions[chat_id].get('awaiting_phone'):
                handle_phone(chat_id, text)
            elif re.search(r'\d', text) and len(text) >= 5:
                handle_phone(chat_id, text)
            else:
                send_telegram_message(
                    chat_id,
                    "🏥 <b>Ветеринарная Клиника Друг</b>\n\n"
                    "Введите номер телефона, указанный в вашей карте клиента,\n"
                    "чтобы получить информацию о себе и питомцах.\n\n"
                    "Или используйте команду /start"
                )
        
        return jsonify({"status": "ok"})
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)})

def handle_start(chat_id):
    """Обработка команды /start"""
    user_sessions[chat_id] = {'awaiting_phone': True}
    
    welcome_text = f"""
🏥 <b>{CLINIC_INFO['name']}</b>
══════════════════════════════════

Я помогу вам получить информацию из вашей карты клиента.

<b>📱 КАК ПОЛЬЗОВАТЬСЯ:</b>

1️⃣ <b>Введите номер телефона</b>, указанный в вашей карте
2️⃣ <b>Получите информацию</b> о себе и питомцах
3️⃣ <b>Узнайте о записях</b> на прием

<b>👇 ВВЕДИТЕ ВАШ НОМЕР ТЕЛЕФОНА:</b>

💡 <i>Примеры форматов:</i>
• <code>+7(928)319-02-25</code>
• <code>89283190225</code>
• <code>9283190225</code>

<b>Статус системы:</b> {'✅ РЕАЛЬНАЯ БАЗА ДАННЫХ' if API_WORKING else '⚠️ ДЕМО-РЕЖИМ'}
"""
    
    send_telegram_message(chat_id, welcome_text)

def handle_test_api(chat_id):
    """Тестирование API"""
    is_working = init_vetmanager_api()
    
    if is_working:
        # Пробуем получить реального клиента
        result = make_api_request('clients', {"limit": 1})
        
        if result and 'data' in result and result['data']:
            client = result['data'][0]
            message = f"""
✅ <b>API РАБОТАЕТ!</b>

<b>Тест подключения успешен:</b>
• Endpoint: clients
• Статус: Подключено
• Пример клиента: {client.get('firstName', '')} {client.get('lastName', '')}
• Телефон: {client.get('phone', 'N/A')}

<b>Заголовки:</b> {API_HEADERS}

Теперь можно искать реальных клиентов!
"""
        else:
            message = "✅ API подключен, но клиенты не найдены"
    else:
        message = """
❌ <b>API НЕ РАБОТАЕТ</b>

<b>Возможные проблемы:</b>
1. Неправильный API ключ
2. Ограничение доступа по IP
3. Проблемы с сервером Vetmanager
4. Неверный формат запроса

<b>Проверьте:</b>
• API ключ в настройках
• Доступ к https://drug14.vetmanager2.ru
• Настройки безопасности Vetmanager
"""
    
    send_telegram_message(chat_id, message)

def handle_phone(chat_id, phone_input):
    """Обработка номера телефона"""
    user_sessions.pop(chat_id, None)
    
    logger.info(f"Поиск клиента: {phone_input}")
    send_telegram_message(chat_id, "🔍 <b>Ищу вашу карту в базе данных...</b>")
    
    # Пробуем найти реального клиента
    real_client = find_real_client(phone_input)
    
    if real_client:
        # Реальный клиент найден!
        client_info = format_client_info(real_client, is_real_data=True)
        send_telegram_message(chat_id, client_info)
        
        # Логируем
        client_name = f"{real_client.get('lastName', '')} {real_client.get('firstName', '')}".strip()
        logger.info(f"✅ Реальные данные отправлены: {client_name}")
        
        # Уведомление администратору
        admin_msg = f"""
📱 <b>РЕАЛЬНЫЙ КЛИЕНТ НАЙДЕН</b>

👤 Клиент: {client_name}
📞 Телефон: {real_client.get('phone', phone_input)}
🆔 Telegram ID: {chat_id}
📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}

✅ Данные из Vetmanager
🐾 Питомцев: {len(real_client.get('pets', []))}
📅 Записей: {len(real_client.get('appointments', []))}
"""
        send_telegram_message(ADMIN_ID, admin_msg)
        
        return
    
    # Если реального клиента нет, показываем демо-данные
    logger.info("⚠️ Реальный клиент не найден, показываю демо")
    
    # Демо-данные
    demo_client = {
        'firstName': 'Анна',
        'lastName': 'Иванова',
        'phone': phone_input,
        'email': 'demo@example.com',
        'balance': 1500.50,
        'pets': [
            {'alias': 'Барсик', 'type_title': 'Кот', 'breed_title': 'Британский'},
            {'alias': 'Мурка', 'type_title': 'Кошка'}
        ],
        'appointments': [
            {'date': '2025-12-31', 'time': '11:00'}
        ]
    }
    
    client_info = format_client_info(demo_client, is_real_data=False)
    send_telegram_message(chat_id, client_info)
    
    # Уведомление администратору
    admin_msg = f"""
📱 <b>КЛИЕНТ НЕ НАЙДЕН В БАЗЕ</b>

📞 Запрос: {phone_input}
🆔 Telegram ID: {chat_id}
📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}

⚠️ Показаны демо-данные
ℹ️ Реальный API: {'РАБОТАЕТ' if API_WORKING else 'НЕ РАБОТАЕТ'}
"""
    send_telegram_message(ADMIN_ID, admin_msg)

# ========== ВЕБ-ИНТЕРФЕЙС ==========
@app.route('/')
def index():
    """Главная страница"""
    api_status = "🟢 РАБОТАЕТ" if API_WORKING else "🔴 НЕДОСТУПЕН"
    status_color = "#28a745" if API_WORKING else "#dc3545"
    
    # Пробуем получить реальные данные для демонстрации
    demo_data = ""
    if API_WORKING:
        result = make_api_request('clients', {"limit": 1})
        if result and 'data' in result and result['data']:
            client = result['data'][0]
            demo_data = f"""
            <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 15px 0;">
                <h4>📋 Пример реального клиента из базы:</h4>
                <p><strong>ID:</strong> {client.get('id')}</p>
                <p><strong>Имя:</strong> {client.get('firstName', '')} {client.get('lastName', '')}</p>
                <p><strong>Телефон:</strong> {client.get('phone', '')}</p>
                <p><strong>Email:</strong> {client.get('email', 'не указан')}</p>
            </div>
            """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Vetmanager API Bot</title>
        <style>
            body {{ font-family: Arial; margin: 20px; }}
            .header {{ text-align: center; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; }}
            .status {{ display: inline-block; padding: 10px 20px; background: {status_color}; color: white; border-radius: 20px; font-weight: bold; margin: 10px; }}
            .card {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 10px; border-left: 5px solid #667eea; }}
            .api-info {{ background: #e8f4fd; padding: 15px; border-radius: 8px; font-family: monospace; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🏥 Vetmanager API Bot</h1>
            <p>Ветеринарная Клиника Друг, Невинномысск</p>
            <div class="status">{api_status}</div>
        </div>
        
        <div class="card">
            <h3>📊 Статус системы</h3>
            <p><strong>Vetmanager API:</strong> {api_status}</p>
            <p><strong>Telegram бот:</strong> @Fulsim_bot</p>
            <p><strong>Домен:</strong> {VETMANAGER_DOMAIN}</p>
            <p><strong>Последняя проверка:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
        </div>
        
        {demo_data}
        
        <div class="card">
            <h3>🔧 Информация о подключении</h3>
            <div class="api-info">
                <p><strong>API ключ:</strong> {VETMANAGER_KEY[:10]}...{VETMANAGER_KEY[-6:]}</p>
                <p><strong>Заголовки:</strong> {API_HEADERS if API_HEADERS else 'Не настроены'}</p>
                <p><strong>URL:</strong> {VETMANAGER_URL}/api/</p>
            </div>
        </div>
        
        <div class="card">
            <h3>📱 Тестирование</h3>
            <p><a href="/test">Проверить API подключение</a></p>
            <p><a href="https://t.me/Fulsim_bot" target="_blank">Открыть Telegram бота</a></p>
            <p><a href="/health">Проверить здоровье системы</a></p>
        </div>
        
        <div style="text-align: center; margin-top: 30px;">
            <p>© 2025 Ветеринарная Клиника Друг</p>
        </div>
    </body>
    </html>
    """

@app.route('/test')
def test_page():
    """Страница тестирования API"""
    return """
    <html>
    <body style="font-family: Arial; padding: 20px;">
        <h1>🧪 Тестирование Vetmanager API</h1>
        
        <h3>Тест 1: Прямой запрос к API</h3>
        <div id="test-result">Выполняю тест...</div>
        
        <h3>Тест 2: Команды для Telegram бота</h3>
        <p>Откройте @Fulsim_bot и отправьте:</p>
        <ul>
            <li><code>/testapi</code> - тест подключения</li>
            <li><code>/start</code> - начать поиск</li>
            <li>Любой номер телефона - поиск клиента</li>
        </ul>
        
        <script>
            fetch('/health')
                .then(r => r.json())
                .then(data => {{
                    const div = document.getElementById('test-result');
                    if (data.vetmanager_api.connected) {{
                        div.innerHTML = `
                            <div style="background: #d4edda; padding: 15px; border-radius: 8px;">
                                <h4>✅ API работает!</h4>
                                <p>Клиентов: ${data.vetmanager_api.client_count}</p>
                                <p>Клиника: ${data.clinic.name}</p>
                            </div>
                        `;
                    }} else {{
                        div.innerHTML = `
                            <div style="background: #f8d7da; padding: 15px; border-radius: 8px;">
                                <h4>❌ API не работает</h4>
                                <p>Проверьте настройки подключения</p>
                            </div>
                        `;
                    }}
                }});
        </script>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Проверка здоровья"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "vetmanager_api": {
            "connected": API_WORKING,
            "headers": API_HEADERS if API_HEADERS else None,
            "domain": VETMANAGER_DOMAIN
        },
        "clinic": CLINIC_INFO,
        "telegram_bot": {
            "configured": True,
            "username": "Fulsim_bot"
        }
    })

# ========== ЗАПУСК ==========
def setup_webhook():
    """Настройка вебхука"""
    webhook_url = "https://vetmanager-bot-1.onrender.com/webhook"
    
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
            params={"url": webhook_url}
        )
        logger.info(f"Webhook: {response.json()}")
    except Exception as e:
        logger.error(f"Webhook error: {e}")

if __name__ == '__main__':
    logger.info("🚀 Запуск бота с REAL Vetmanager API...")
    
    # Инициализируем API
    init_vetmanager_api()
    
    # Настраиваем вебхук
    setup_webhook()
    
    # Отправляем сообщение о запуске
    startup_msg = f"""
🚀 <b>БОТ ЗАПУЩЕН С REAL VETMANAGER API</b>

🏥 <b>Клиника:</b> {CLINIC_INFO['name']}
📍 <b>Адрес:</b> {CLINIC_INFO['address']}
📞 <b>Телефон:</b> {CLINIC_INFO['phones'][0]}

🔗 <b>Telegram бот:</b> @Fulsim_bot
🌐 <b>Веб-интерфейс:</b> https://vetmanager-bot-1.onrender.com

📊 <b>СТАТУС API:</b> {'🟢 РАБОТАЕТ' if API_WORKING else '🔴 НЕ РАБОТАЕТ'}
🔑 <b>API ключ:</b> Настроен (от Вазапы)

<b>Действия:</b>
1. Открыть Telegram бота
2. Отправить /testapi для проверки
3. Ввести номер телефона клиента
4. Получить реальные данные из Vetmanager

<b>Для теста:</b>
• /testapi - проверка API
• Любой номер - поиск клиента

✅ <b>Система готова получать реальные данные!</b>
"""
    
    send_telegram_message(ADMIN_ID, startup_msg)
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
