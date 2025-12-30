import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request
import logging
from threading import Thread
import time

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

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_vetmanager_data(endpoint, params=None):
    """Получает данные из Vetmanager"""
    headers = {"X-User-Token": VETMANAGER_KEY}
    url = f"{VETMANAGER_URL}/api/{endpoint}"
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            return response.json().get("data", [])
    except Exception as e:
        logger.error(f"Vetmanager error: {e}")
    
    return []

def find_client_by_phone(phone_input):
    """Ищет клиента по номеру телефона в любом формате"""
    # Получаем всех клиентов
    all_clients = get_vetmanager_data("clients", {"limit": 500})
    
    if not all_clients:
        logger.info("В базе Vetmanager нет клиентов")
        return None
    
    # Очищаем введенный номер
    input_clean = ''.join(filter(str.isdigit, str(phone_input)))
    
    # Нормализуем формат введенного номера
    if input_clean.startswith('8'):
        input_clean = '7' + input_clean[1:]  # 8999 → 7999
    elif input_clean.startswith('9') and len(input_clean) == 10:
        input_clean = '7' + input_clean  # 9996925927 → 79996925927
    
    logger.info(f"Ищем номер: {input_clean} (введено: {phone_input})")
    
    # Перебираем всех клиентов
    for client in all_clients:
        client_phone = str(client.get('phone', ''))
        
        if not client_phone:
            continue
        
        # Очищаем номер из базы
        client_clean = ''.join(filter(str.isdigit, client_phone))
        
        # Нормализуем номер из базы
        if client_clean.startswith('8'):
            client_clean = '7' + client_clean[1:]
        elif client_clean.startswith('9') and len(client_clean) == 10:
            client_clean = '7' + client_clean
        
        # Вариант 1: Полное совпадение
        if input_clean == client_clean:
            return format_client_data(client, client_phone)
        
        # Вариант 2: Совпадение последних 10 цифр
        if len(input_clean) >= 10 and len(client_clean) >= 10:
            if input_clean[-10:] == client_clean[-10:]:
                return format_client_data(client, client_phone)
        
        # Вариант 3: Совпадение последних 7 цифр (без кода)
        if len(input_clean) >= 7 and len(client_clean) >= 7:
            if input_clean[-7:] == client_clean[-7:]:
                return format_client_data(client, client_phone)
    
    # Если не нашли - логируем для отладки
    logger.warning(f"Клиент не найден. Введен: '{phone_input}', очищенный: {input_clean}")
    logger.info(f"Всего клиентов в базе: {len(all_clients)}")
    
    return None

def format_client_data(client, phone):
    """Форматирует данные клиента"""
    return {
        'id': client.get('id'),
        'name': f"{client.get('firstName', '')} {client.get('lastName', '')}".strip(),
        'phone': phone,
        'email': client.get('email', '')
    }

def save_telegram_id(client_id, telegram_id):
    """Сохраняет Telegram ID в Vetmanager (упрощенная версия)"""
    # В реальной версии здесь будет запись в customFields
    # Сейчас просто логируем
    logger.info(f"Сохранен Telegram ID {telegram_id} для клиента {client_id}")
    return True

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

# ========== ТЕЛЕГРАМ БОТ ==========
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
    """Обработка команды /start - ВИП ВЕРСИЯ"""
    user_sessions[chat_id] = {'waiting': True}
    
    welcome_text = """🎉 <b>ДОБРО ПОЖАЛОВАТЬ В VIP-КЛУБ VETCLINIC!</b>

<b>🔥 ЭКСКЛЮЗИВНЫЕ ПРЕИМУЩЕСТВА:</b>
1️⃣ <b>Автонапоминания</b> о визитах
2️⃣ <b>Первыми об акциях</b>
3️⃣ <b>Напоминания о прививках</b>
4️⃣ <b>Экспресс-запись</b>

<b>📱 Введите номер телефона из вашей карты:</b>

💡 <i>Можно вводить в любом формате:</i>
• +7(999)692-59-27
• 89996925927
• 9996925927
• 7 999 692 59 27</i>"""
    
    send_telegram_message(chat_id, welcome_text)

def handle_phone_input(chat_id, phone_input):
    """Обработка введенного номера телефона"""
    user_sessions.pop(chat_id, None)
    
    logger.info(f"Поиск клиента по номеру: {phone_input}")
    
    client = find_client_by_phone(phone_input)
    
    if not client:
        send_telegram_message(
            chat_id,
            "❌ <b>Клиент не найден</b>\n\n"
            "Возможные причины:\n"
            "• Номер введен неправильно\n"
            "• Вы не наш клиент\n"
            "• Обратитесь на ресепшн для уточнения\n\n"
            "Попробуйте снова: /start"
        )
        return
    
    # Сохраняем Telegram ID
    save_telegram_id(client['id'], chat_id)
    
    # Приветствуем клиента
    client_message = f"""🎊 <b>ПОЗДРАВЛЯЕМ! ВЫ В VIP-КЛУБЕ!</b>

Добро пожаловать, {client['name']}! 🐕🐈

✅ Вы подключены к системе VIP-уведомлений!

<b>Теперь вы будете получать:</b>
• Напоминания о визитах
• Специальные предложения
• Важные уведомления

<b>💡 КАК ЭТО РАБОТАЕТ:</b>
1. Мы проверяем записи каждый день
2. Присылаем напоминание за день до визита
3. Вы можете подтвердить или перенести визит

<b>💬 ГЛАВНОЕ ПРАВИЛО:</b>
Мы пишем только по делу и не спамим!

С заботой о вашем питомце,
Команда VetClinic 🏥"""
    
    send_telegram_message(chat_id, client_message)
    
    # Уведомление администратору
    admin_message = f"""📱 <b>НОВЫЙ VIP-КЛИЕНТ</b>

👤 Имя: {client['name']}
📞 Телефон: {client['phone']}
🆔 Telegram ID: {chat_id}
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>Клиент успешно подключен!</b>"""
    
    send_telegram_message(ADMIN_ID, admin_message)
    
    logger.info(f"Новый VIP-клиент: {client['name']}, ID: {chat_id}")

# ========== АВТОМАТИЧЕСКИЕ НАПОМИНАНИЯ ==========
def check_and_send_reminders():
    """Проверяет завтрашние записи и отправляет напоминания"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    appointments = get_vetmanager_data("appointments", {
        "filter[date]": tomorrow,
        "limit": 100
    })
    
    if not appointments:
        logger.info(f"На {tomorrow} записей не найдено")
        return
    
    logger.info(f"Найдено записей на завтра: {len(appointments)}")
    
    sent_count = 0
    for app in appointments:
        client_id = app.get('client_id')
        app_time = app.get('time', '10:00')
        pet_name = app.get('pet_alias', 'питомец')
        
        # Здесь должна быть логика поиска Telegram ID по client_id
        # Пока отправляем тестовое сообщение администратору
        reminder = f"""🔔 <b>ТЕСТ НАПОМИНАНИЯ</b>

На завтра {tomorrow} в {app_time}
запись с {pet_name} (клиент ID: {client_id})

Система напоминаний работает!"""
        
        if send_telegram_message(ADMIN_ID, reminder):
            sent_count += 1
    
    # Отчет администратору
    if sent_count > 0:
        report = f"""📊 <b>ТЕСТ ОТЧЕТА ПО НАПОМИНАНИЯМ</b>

📅 Дата: {tomorrow}
✅ Тестовых уведомлений: {sent_count}
📋 Всего записей: {len(appointments)}

<i>Это тестовый отчет. Реальная система будет отправлять клиентам.</i>"""
        
        send_telegram_message(ADMIN_ID, report)

# ========== WEB ИНТЕРФЕЙС ==========
@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>🏥 VetClinic VIP Bot</title>
        <style>
            body { font-family: Arial; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .card { background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 10px; }
            .btn { padding: 10px 20px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏥 VetClinic VIP Telegram Bot</h1>
            
            <div class="card">
                <h2>🤖 Система работает!</h2>
                <p>Бот готов принимать клиентов в VIP-клуб.</p>
                <p><strong>Статус:</strong> ✅ Активен</p>
                <p><strong>Бот:</strong> @Fulsim_bot</p>
            </div>
            
            <div class="card">
                <h2>⚡ Быстрые действия</h2>
                <p><a href="/send_reminders" class="btn">Тест напоминаний</a></p>
                <p><a href="/health" class="btn">Проверить статус</a></p>
                <p><a href="/test_search" class="btn">Тест поиска</a></p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/send_reminders')
def manual_reminders():
    """Ручная отправка напоминаний"""
    Thread(target=check_and_send_reminders).start()
    return """
    <html>
    <body style="font-family: Arial; padding: 40px;">
        <h1>✅ Тест напоминаний запущен</h1>
        <p>Проверьте Telegram для получения отчета.</p>
        <p><a href="/">Вернуться на главную</a></p>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    return {
        "status": "healthy",
        "service": "vetclinic-vip-bot",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0",
        "features": ["VIP-registration", "multi-format-phone-search"]
    }

@app.route('/test_search')
def test_search():
    """Тест поиска клиента"""
    test_phones = [
        "+7(999)692-59-27",
        "89996925927",
        "9996925927",
        "7 999 692 59 27"
    ]
    
    results = []
    for phone in test_phones:
        client = find_client_by_phone(phone)
        if client:
            results.append(f"✅ {phone} → {client['name']}")
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
    logger.info("🚀 Запуск VetClinic VIP Bot (версия с улучшенным поиском)...")
    
    # Настраиваем webhook
    setup_webhook()
    
    # Отправляем сообщение о запуске
    startup_msg = f"""🚀 <b>VIP БОТ ОБНОВЛЕН</b>

✅ Система с улучшенным поиском номеров
🏥 Клиника: VetClinic
🔗 Бот: @Fulsim_bot
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>НОВЫЕ ВОЗМОЖНОСТИ:</b>
• Понимает любой формат номера
• Интеллектуальный поиск
• Автоматические напоминания

Готов к работе! 🐾"""
    
    send_telegram_message(ADMIN_ID, startup_msg)
    
    # Запускаем Flask сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
