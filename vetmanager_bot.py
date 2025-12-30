import os
import requests
from datetime import datetime
from flask import Flask, request
import logging
import re

app = Flask(__name__)

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI'
VETMANAGER_KEY = 'b5aa96-c7d6f9-7296aa-0c1670-805a64'
VETMANAGER_URL = 'https://drug14.vetmanager2.ru'
ADMIN_ID = 921853682

# Хранилище сессий
user_sessions = {}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== REAL VETMANAGER API ==========
def test_api_connection():
    """Тестирует подключение к Vetmanager API"""
    headers = {"X-User-Token": VETMANAGER_KEY}
    url = f"{VETMANAGER_URL}/api/clients"
    
    logger.info("🔌 Тестирую подключение к Vetmanager API...")
    
    try:
        response = requests.get(url, headers=headers, params={"limit": 1}, timeout=10)
        logger.info(f"Статус API: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            clients = data.get("data", [])
            logger.info(f"✅ API работает! Найдено клиентов: {len(clients)}")
            
            # Логируем первого клиента для отладки
            if clients:
                client = clients[0]
                logger.info(f"Пример клиента: ID={client.get('id')}, Имя={client.get('firstName')}, Телефон={client.get('phone')}")
            
            return True, len(clients)
        else:
            logger.error(f"❌ Ошибка API: {response.status_code}")
            logger.error(f"Ответ: {response.text[:200]}")
            return False, 0
            
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к API: {e}")
        return False, 0

def get_client_by_phone_from_api(phone_input):
    """Ищет клиента по номеру через реальный API"""
    headers = {"X-User-Token": VETMANAGER_KEY}
    url = f"{VETMANAGER_URL}/api/clients"
    
    # Очищаем номер для поиска
    phone_clean = re.sub(r'\D', '', str(phone_input))
    
    # Пробуем разные варианты поиска
    search_patterns = [
        phone_clean,  # 79996925927
        phone_clean[1:] if phone_clean.startswith('7') else phone_clean,  # 9996925927
        phone_clean[1:] if phone_clean.startswith('8') else phone_clean,  # 9996925927 если начинался с 8
    ]
    
    logger.info(f"🔍 Ищу клиента по номеру: {phone_input} (очищенный: {phone_clean})")
    
    for pattern in search_patterns:
        if not pattern:
            continue
            
        params = {"filter[phone]": pattern}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                clients = data.get("data", [])
                
                if clients:
                    client = clients[0]
                    logger.info(f"✅ Найден клиент: ID={client.get('id')}, Имя={client.get('firstName')}")
                    
                    # Получаем дополнительную информацию
                    full_client_info = get_full_client_info(client.get('id'))
                    if full_client_info:
                        client.update(full_client_info)
                    
                    return client
                    
        except Exception as e:
            logger.error(f"Ошибка поиска: {e}")
    
    logger.warning(f"❌ Клиент не найден по номеру: {phone_input}")
    return None

def get_full_client_info(client_id):
    """Получает полную информацию о клиенте"""
    headers = {"X-User-Token": VETMANAGER_KEY}
    
    # 1. Основная информация клиента
    client_url = f"{VETMANAGER_URL}/api/client/{client_id}"
    
    try:
        response = requests.get(client_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json().get("data", {})
            
            # 2. Питомцы клиента
            pets_url = f"{VETMANAGER_URL}/api/pets"
            pets_params = {"filter[client_id]": client_id, "limit": 10}
            pets_response = requests.get(pets_url, headers=headers, params=pets_params, timeout=10)
            
            if pets_response.status_code == 200:
                data['pets'] = pets_response.json().get("data", [])
            
            # 3. Последние записи (будущие)
            from datetime import datetime, timedelta
            today = datetime.now().strftime("%Y-%m-%d")
            future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            
            appointments_url = f"{VETMANAGER_URL}/api/appointments"
            app_params = {
                "filter[client_id]": client_id,
                "filter[date_from]": today,
                "filter[date_to]": future,
                "sort": "date",
                "limit": 5
            }
            
            app_response = requests.get(appointments_url, headers=headers, params=app_params, timeout=10)
            if app_response.status_code == 200:
                data['appointments'] = app_response.json().get("data", [])
            
            return data
            
    except Exception as e:
        logger.error(f"Ошибка получения деталей клиента: {e}")
    
    return {}

# ========== TELEGRAM ФУНКЦИИ ==========
def send_telegram_message(chat_id, text, parse_mode='HTML'):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json().get("ok", False)
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False

# ========== TELEGRAM WEBHOOK ==========
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Обработчик сообщений от Telegram"""
    data = request.json
    
    if 'message' in data:
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        
        if text == '/start':
            handle_start(chat_id)
        elif chat_id in user_sessions:
            handle_phone_input(chat_id, text)
        else:
            send_telegram_message(
                chat_id,
                "Для получения информации из вашей карты клиента отправьте:\n\n"
                "<b>/start</b> - начать поиск"
            )
    
    return 'OK'

def handle_start(chat_id):
    """Обработка команды /start"""
    user_sessions[chat_id] = {'waiting': True}
    
    # Тестируем подключение к API
    api_working, clients_count = test_api_connection()
    
    if not api_working:
        welcome_text = """⚠️ <b>СИСТЕМА В РЕЖИМЕ ОБСЛУЖИВАНИЯ</b>

В настоящее время база данных клиники недоступна.

📱 <b>Для получения информации:</b>
Обратитесь на ресепшн клиники.

📍 <b>Клиника:</b> VetClinic
⏰ <b>Часы работы:</b> Пн-Пт 9:00-20:00"""
        
        logger.warning(f"API не доступен для пользователя {chat_id}")
    else:
        welcome_text = f"""🎉 <b>ДОБРО ПОЖАЛОВАТЬ В VETCLINIC!</b>

Я помогу вам получить информацию из вашей карты клиента.

✅ <b>База данных доступна</b>
📊 Всего клиентов в системе: {clients_count}

<b>📱 ВАШИ ДЕЙСТВИЯ:</b>

1️⃣ <b>Введите номер телефона</b>, указанный в вашей карте
2️⃣ <b>Получите реальную информацию</b> из базы данных
3️⃣ <b>Узнайте о питомцах и записях</b>

<b>👇 ВВЕДИТЕ ВАШ НОМЕР ТЕЛЕФОНА:</b>

💡 <i>Примеры форматов:</i>
• <code>+7(999)692-59-27</code>
• <code>89996925927</code>
• <code>9996925927</code></i>"""
    
    send_telegram_message(chat_id, welcome_text)
    logger.info(f"Пользователь {chat_id} начал диалог. API работает: {api_working}")

def handle_phone_input(chat_id, phone_input):
    """Обработка введенного номера телефона"""
    user_sessions.pop(chat_id, None)
    
    logger.info(f"Пользователь {chat_id} ищет по номеру: {phone_input}")
    
    # Сообщение о поиске
    send_telegram_message(chat_id, "🔍 <b>Ищу вашу карту в базе данных...</b>")
    
    # Ищем клиента через реальный API
    client = get_client_by_phone_from_api(phone_input)
    
    if not client:
        send_telegram_message(
            chat_id,
            "❌ <b>Клиент не найден</b>\n\n"
            "<b>Возможные причины:</b>\n"
            "• Номер введен неправильно\n"
            "• Вы не зарегистрированы в нашей клинике\n"
            "• Ваш номер указан в другом формате\n\n"
            "<b>Попробуйте:</b>\n"
            "• Ввести номер в другом формате\n"
            "• Обратиться на ресепшн для уточнения\n\n"
            "<b>Или начните заново:</b> /start"
        )
        return
    
    # Формируем РЕАЛЬНУЮ информацию из базы
    message_parts = []
    
    # Основная информация
    first_name = client.get('firstName', '')
    last_name = client.get('lastName', '')
    full_name = f"{first_name} {last_name}".strip()
    phone = client.get('phone', phone_input)
    email = client.get('email', 'не указан')
    balance = client.get('balance', 0)
    city = client.get('city', 'не указан')
    address = client.get('address', 'не указан')
    
    message_parts.append("✅ <b>ВАША КАРТА КЛИЕНТА</b>")
    message_parts.append("══════════════════════════════════")
    
    if full_name:
        message_parts.append(f"👤 <b>Имя:</b> {full_name}")
    
    if phone:
        message_parts.append(f"📞 <b>Телефон:</b> {phone}")
    
    if email and email != 'не указан':
        message_parts.append(f"📧 <b>Email:</b> {email}")
    
    if balance is not None:
        message_parts.append(f"💰 <b>Баланс:</b> {balance} руб.")
    
    if city and city != 'не указан':
        message_parts.append(f"🏙️ <b>Город:</b> {city}")
    
    # Питомцы
    pets = client.get('pets', [])
    if pets:
        message_parts.append("")
        message_parts.append("🐾 <b>ВАШИ ПИТОМЦЫ:</b>")
        
        for i, pet in enumerate(pets[:5], 1):
            pet_name = pet.get('alias', 'Без имени')
            pet_type = pet.get('type', '')
            breed = pet.get('breed', '')
            
            pet_info = pet_name
            if pet_type:
                pet_info += f" ({pet_type}"
                if breed:
                    pet_info += f", {breed}"
                pet_info += ")"
            elif breed:
                pet_info += f" ({breed})"
            
            message_parts.append(f"{i}. {pet_info}")
        
        if len(pets) > 5:
            message_parts.append(f"... и ещё {len(pets) - 5} питомцев")
    else:
        message_parts.append("")
        message_parts.append("🐾 <b>Питомцы:</b> не указаны")
    
    # Записи
    appointments = client.get('appointments', [])
    if appointments:
        message_parts.append("")
        message_parts.append("📅 <b>БЛИЖАЙШИЕ ЗАПИСИ:</b>")
        
        for i, app in enumerate(appointments[:3], 1):
            date = app.get('date', '')
            time = app.get('time', '10:00')
            
            # Находим питомца для записи
            pet_name = "питомец"
            pet_id = app.get('pet_id')
            
            for pet in pets:
                if str(pet.get('id')) == str(pet_id):
                    pet_name = pet.get('alias', 'питомец')
                    break
            
            message_parts.append(f"{i}. {date} в {time} - {pet_name}")
        
        if len(appointments) > 3:
            message_parts.append(f"... и ещё {len(appointments) - 3} записей")
    else:
        message_parts.append("")
        message_parts.append("📅 <b>Ближайшие записи:</b> нет")
    
    # Контакты клиники
    message_parts.append("")
    message_parts.append("══════════════════════════════════")
    message_parts.append("🏥 <b>ВЕТКЛИНИКА</b>")
    message_parts.append("📍 <b>Адрес:</b> г. Ростов-на-Дону")
    message_parts.append("📞 <b>Телефон:</b> +7 (XXX) XXX-XX-XX")
    message_parts.append("⏰ <b>Часы работы:</b> Пн-Пт 9:00-20:00, Сб-Вс 10:00-18:00")
    
    message_parts.append("")
    message_parts.append("💡 <i>Для записи на прием или уточнения информации обратитесь на ресепшн</i>")
    
    # Отправляем РЕАЛЬНЫЕ данные клиенту
    send_telegram_message(chat_id, "\n".join(message_parts))
    
    # Уведомление администратору
    admin_msg = f"""📱 <b>КЛИЕНТ ПОЛУЧИЛ РЕАЛЬНУЮ КАРТУ</b>

👤 Клиент: {full_name if full_name else 'Не указано'}
📞 Телефон: {phone}
🆔 Telegram ID: {chat_id}
📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}

✅ Данные загружены из Vetmanager"""
    
    if pets:
        admin_msg += f"\n🐾 Питомцев: {len(pets)}"
    
    if appointments:
        admin_msg += f"\n📅 Записей: {len(appointments)}"
    
    send_telegram_message(ADMIN_ID, admin_msg)
    
    logger.info(f"Реальные данные отправлены клиенту: {full_name}")

# ========== WEB ИНТЕРФЕЙС ==========
@app.route('/')
def home():
    # Тестируем API при загрузке страницы
    api_working, clients_count = test_api_connection()
    
    status = "🟢 РАБОТАЕТ" if api_working else "🔴 НЕДОСТУПЕН"
    
    return f"""
    <html>
    <head>
        <title>🏥 VetClinic Real Data Bot</title>
        <style>
            body {{ font-family: Arial; margin: 40px; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            .card {{ background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 10px; }}
            .status-ok {{ color: green; font-weight: bold; }}
            .status-error {{ color: red; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏥 VetClinic Telegram Bot</h1>
            <p>Система получения РЕАЛЬНЫХ данных из Vetmanager</p>
            
            <div class="card">
                <h2>📊 Статус системы</h2>
                <p><strong>Подключение к Vetmanager:</strong> <span class="{'status-ok' if api_working else 'status-error'}">{status}</span></p>
                <p><strong>Клиентов в базе:</strong> {clients_count}</p>
                <p><strong>Telegram бот:</strong> @Fulsim_bot</p>
            </div>
            
            <div class="card">
                <h2>🔧 Проверка</h2>
                <p><a href="/health">Проверить статус API</a></p>
                <p><a href="/test">Тест поиска клиента</a></p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    api_working, clients_count = test_api_connection()
    
    return {
        "status": "healthy" if api_working else "api_error",
        "vetmanager_api": "connected" if api_working else "disconnected",
        "clients_in_database": clients_count,
        "timestamp": datetime.now().isoformat(),
        "service": "vetclinic-real-data-bot"
    }

@app.route('/test')
def test_page():
    """Тестовая страница для проверки поиска"""
    return """
    <html>
    <body style="font-family: Arial; margin: 40px;">
        <h1>🧪 Тест поиска клиента</h1>
        <p>Проверьте работу поиска по номеру телефона</p>
        
        <h3>Тестовые номера для проверки:</h3>
        <ul>
            <li>+7(999)692-59-27</li>
            <li>89996925927</li>
            <li>9996925927</li>
        </ul>
        
        <p>Откройте Telegram бота @Fulsim_bot и введите любой из этих номеров</p>
        <p><a href="/">На главную</a></p>
    </body>
    </html>
    """

# ========== ЗАПУСК ==========
def setup_webhook():
    """Настройка webhook для Telegram"""
    webhook_url = f"https://vetmanager-bot-1.onrender.com/webhook"
    set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(set_url)
        logger.info(f"Webhook: {response.json()}")
    except Exception as e:
        logger.error(f"Webhook error: {e}")

if __name__ == "__main__":
    logger.info("🚀 Запуск VetClinic Real Data Bot...")
    
    # Тестируем API при запуске
    api_working, clients_count = test_api_connection()
    
    # Настраиваем webhook
    setup_webhook()
    
    # Отправляем сообщение о запуске
    status_msg = "с реальными данными" if api_working else "в режиме ожидания API"
    
    startup_msg = f"""🚀 <b>БОТ ЗАПУЩЕН {status_msg.upper()}</b>

✅ Система получения реальных данных из Vetmanager
🏥 Клиника: VetClinic  
🔗 Бот: @Fulsim_bot
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>СТАТУС API:</b> {'🟢 РАБОТАЕТ' if api_working else '🔴 НЕДОСТУПЕН'}
<b>КЛИЕНТОВ В БАЗЕ:</b> {clients_count}

<b>ФУНКЦИИ:</b>
• Реальный поиск клиентов
• Отображение данных из базы
• Информация о питомцах
• Ближайшие записи

Готов к работе! 🐾"""
    
    send_telegram_message(ADMIN_ID, startup_msg)
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
