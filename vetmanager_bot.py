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

# ========== ОЧИСТКА НОМЕРА ТЕЛЕФОНА ==========
def clean_phone_number(phone):
    """Очищает номер телефона от всего кроме цифр"""
    if not phone:
        return ""
    # Убираем все кроме цифр
    digits = re.sub(r'\D', '', str(phone))
    # Убираем лидирующие 8 или 7 для сравнения
    if digits.startswith('8'):
        digits = digits[1:]
    elif digits.startswith('7'):
        digits = digits[1:]
    return digits

# ========== VETMANAGER API ФУНКЦИИ ==========
def get_all_clients():
    """Получает всех клиентов из Vetmanager"""
    headers = {"X-User-Token": VETMANAGER_KEY}
    url = f"{VETMANAGER_URL}/api/clients"
    
    all_clients = []
    page = 1
    limit = 100  # Максимально за раз
    
    try:
        while True:
            params = {"limit": limit, "page": page}
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Ошибка API: {response.status_code}")
                break
            
            data = response.json()
            clients = data.get("data", [])
            
            if not clients:
                break
                
            all_clients.extend(clients)
            logger.info(f"Загружено клиентов: {len(all_clients)}")
            
            if len(clients) < limit:
                break
                
            page += 1
            
        logger.info(f"Всего загружено клиентов: {len(all_clients)}")
        return all_clients
        
    except Exception as e:
        logger.error(f"Ошибка загрузки клиентов: {e}")
        return []

def find_client_by_phone(phone_input):
    """Ищет клиента по номеру телефона в реальной базе Vetmanager"""
    logger.info(f"Поиск клиента по номеру: '{phone_input}'")
    
    # Получаем всех клиентов
    all_clients = get_all_clients()
    
    if not all_clients:
        logger.error("Не удалось получить клиентов из Vetmanager")
        return None
    
    # Очищаем введенный номер
    input_clean = clean_phone_number(phone_input)
    logger.info(f"Очищенный номер для поиска: {input_clean}")
    
    # Ищем клиента
    for client in all_clients:
        client_phone = client.get('phone', '')
        
        if not client_phone:
            continue
        
        # Очищаем номер клиента
        client_clean = clean_phone_number(client_phone)
        
        # Сравниваем очищенные номера
        if input_clean == client_clean:
            logger.info(f"✅ Найден клиент: {client.get('firstName', '')} {client.get('lastName', '')}")
            
            # Получаем дополнительные данные клиента
            client_id = client.get('id')
            client_details = get_client_details(client_id)
            
            if client_details:
                client.update(client_details)
            
            return client
    
    logger.warning(f"❌ Клиент не найден для номера: {phone_input}")
    logger.info(f"Проверено клиентов: {len(all_clients)}")
    return None

def get_client_details(client_id):
    """Получает детальную информацию о клиенте"""
    headers = {"X-User-Token": VETMANAGER_KEY}
    url = f"{VETMANAGER_URL}/api/client/{client_id}"
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            return response.json().get("data", {})
    except Exception as e:
        logger.error(f"Ошибка получения деталей клиента: {e}")
    
    return {}

def get_client_pets(client_id):
    """Получает питомцев клиента"""
    headers = {"X-User-Token": VETMANAGER_KEY}
    url = f"{VETMANAGER_URL}/api/pets"
    params = {"filter[client_id]": client_id}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if response.status_code == 200:
            return response.json().get("data", [])
    except Exception as e:
        logger.error(f"Ошибка получения питомцев: {e}")
    
    return []

def get_client_appointments(client_id):
    """Получает будущие записи клиента"""
    headers = {"X-User-Token": VETMANAGER_KEY}
    url = f"{VETMANAGER_URL}/api/appointments"
    
    # Записи на ближайшие 30 дней
    from datetime import datetime, timedelta
    today = datetime.now().strftime("%Y-%m-%d")
    future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    params = {
        "filter[client_id]": client_id,
        "filter[date_from]": today,
        "filter[date_to]": future,
        "sort": "date",
        "limit": 10
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if response.status_code == 200:
            return response.json().get("data", [])
    except Exception as e:
        logger.error(f"Ошибка получения записей: {e}")
    
    return []

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
            send_telegram_message(chat_id, "Для начала работы отправьте /start")
    
    return 'OK'

def handle_start(chat_id):
    """Обработка команды /start"""
    user_sessions[chat_id] = {'waiting': True}
    
    welcome_text = """🎉 <b>ДОБРО ПОЖАЛОВАТЬ В VETCLINIC!</b>

Я помогу вам получить информацию из вашей карты клиента.

<b>📱 Введите номер телефона, указанный в вашей карте:</b>

💡 <i>Примеры форматов:</i>
• <code>+7(999)692-59-27</code>
• <code>89996925927</code>
• <code>9996925927</code>
• <code>7 999 692 59 27</code></i>"""
    
    send_telegram_message(chat_id, welcome_text)
    logger.info(f"Пользователь {chat_id} начал диалог")

def handle_phone_input(chat_id, phone_input):
    """Обработка введенного номера телефона"""
    user_sessions.pop(chat_id, None)
    
    logger.info(f"Поиск клиента для {chat_id}: {phone_input}")
    
    # Показываем сообщение о поиске
    send_telegram_message(chat_id, "🔍 <b>Ищу вашу карту в базе...</b>")
    
    # Ищем клиента
    client = find_client_by_phone(phone_input)
    
    if not client:
        send_telegram_message(
            chat_id,
            "❌ <b>Клиент не найден</b>\n\n"
            "Возможные причины:\n"
            "• Номер введен неправильно\n"
            "• Вы не зарегистрированы в нашей клинике\n"
            "• Обратитесь на ресепшн для уточнения\n\n"
            "Попробуйте снова: /start"
        )
        return
    
    # Формируем информацию о клиенте
    client_id = client.get('id', '')
    first_name = client.get('firstName', '')
    last_name = client.get('lastName', '')
    full_name = f"{first_name} {last_name}".strip()
    phone = client.get('phone', phone_input)
    email = client.get('email', 'не указан')
    balance = client.get('balance', 0)
    
    # Получаем дополнительные данные
    pets = get_client_pets(client_id)
    appointments = get_client_appointments(client_id)
    
    # Формируем сообщение
    message_parts = []
    
    # Основная информация
    message_parts.append(f"✅ <b>ВАША КАРТА КЛИЕНТА</b>")
    message_parts.append("═" * 30)
    message_parts.append(f"👤 <b>Имя:</b> {full_name}")
    message_parts.append(f"📞 <b>Телефон:</b> {phone}")
    
    if email and email != 'не указан':
        message_parts.append(f"📧 <b>Email:</b> {email}")
    
    message_parts.append(f"💰 <b>Баланс:</b> {balance} руб.")
    
    # Питомцы
    if pets:
        message_parts.append("")
        message_parts.append("🐾 <b>ВАШИ ПИТОМЦЫ:</b>")
        for i, pet in enumerate(pets[:5], 1):
            pet_name = pet.get('alias', 'Без имени')
            pet_type = pet.get('type', 'Неизвестно')
            breed = pet.get('breed', '')
            message_parts.append(f"{i}. {pet_name} ({pet_type}" + (f", {breed})" if breed else ")"))
        
        if len(pets) > 5:
            message_parts.append(f"... и ещё {len(pets) - 5} питомцев")
    else:
        message_parts.append("")
        message_parts.append("🐾 <b>Питомцы:</b> не указаны")
    
    # Будущие записи
    if appointments:
        message_parts.append("")
        message_parts.append("📅 <b>БЛИЖАЙШИЕ ЗАПИСИ:</b>")
        for i, app in enumerate(appointments[:3], 1):
            date = app.get('date', '')
            time = app.get('time', '')
            pet_id = app.get('pet_id', '')
            pet_name = "питомец"
            
            # Находим имя питомца
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
    
    # Контактная информация
    message_parts.append("")
    message_parts.append("═" * 30)
    message_parts.append("🏥 <b>ВЕТКЛИНИКА</b>")
    message_parts.append("📍 Адрес: [Ваш адрес]")
    message_parts.append("📞 Телефон: [Ваш телефон]")
    message_parts.append("⏰ Часы работы: [Ваше расписание]")
    
    # Конец сообщения
    message_parts.append("")
    message_parts.append("💡 <i>Для новой записи обратитесь на ресепшн</i>")
    
    # Отправляем сообщение клиенту
    send_telegram_message(chat_id, "\n".join(message_parts))
    
    # Уведомление администратору
    admin_msg = f"""📱 <b>ЗАПРОС КАРТЫ КЛИЕНТА</b>

👤 Клиент: {full_name}
📞 Телефон: {phone}
🆔 Telegram ID: {chat_id}
📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}

✅ Информация отправлена клиенту"""
    
    send_telegram_message(ADMIN_ID, admin_msg)
    logger.info(f"Информация отправлена клиенту: {full_name}")

# ========== WEB ИНТЕРФЕЙС ==========
@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>🏥 VetClinic Client Info Bot</title>
        <style>
            body { font-family: Arial; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .card { background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 10px; }
            .btn { padding: 10px 20px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏥 VetClinic Client Information Bot</h1>
            
            <div class="card">
                <h2>📱 Telegram Bot</h2>
                <p>Клиенты могут получить свою карту через Telegram</p>
                <p><strong>Бот:</strong> @Fulsim_bot</p>
                <p><strong>Команда:</strong> /start</p>
            </div>
            
            <div class="card">
                <h2>⚡ Функции</h2>
                <ul>
                    <li>Поиск клиента по номеру телефона</li>
                    <li>Отображение основной информации</li>
                    <li>Список питомцев клиента</li>
                    <li>Ближайшие записи</li>
                    <li>Уведомление администратору</li>
                </ul>
            </div>
            
            <div class="card">
                <h2>🔧 Проверка системы</h2>
                <p><a href="/health" class="btn">Проверить статус</a></p>
                <p><a href="/test_search" class="btn">Тест поиска</a></p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    return {
        "status": "healthy",
        "service": "vetclinic-client-info",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0",
        "features": ["client-search", "pets-info", "appointments", "telegram-notifications"]
    }

@app.route('/test_search')
def test_search():
    """Тестовая страница поиска"""
    test_numbers = [
        "+7(999)692-59-27",
        "89996925927", 
        "9996925927",
        "test"
    ]
    
    results = []
    for phone in test_numbers:
        client = find_client_by_phone(phone)
        if client:
            results.append(f"✅ {phone} → {client.get('firstName', '')} {client.get('lastName', '')}")
        else:
            results.append(f"❌ {phone} → не найден")
    
    return "<br>".join(results)

# ========== ЗАПУСК ==========
def setup_webhook():
    """Настройка webhook для Telegram"""
    webhook_url = f"https://vetmanager-bot-1.onrender.com/webhook"
    set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(set_url)
        logger.info(f"Webhook установлен: {response.json()}")
    except Exception as e:
        logger.error(f"Ошибка webhook: {e}")

if __name__ == "__main__":
    logger.info("🚀 Запуск VetClinic Client Info Bot...")
    
    # Настраиваем webhook
    setup_webhook()
    
    # Отправляем сообщение о запуске
    startup_msg = f"""🚀 <b>БОТ ДЛЯ КЛИЕНТОВ ЗАПУЩЕН</b>

✅ Система получения информации из карты клиента
🏥 Клиника: VetClinic  
🔗 Бот: @Fulsim_bot
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>ФУНКЦИИ:</b>
• Поиск клиента по номеру телефона
• Отображение информации из карты
• Список питомцев и записей
• Уведомления администратору

Готов к работе! 🐾"""
    
    send_telegram_message(ADMIN_ID, startup_msg)
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
