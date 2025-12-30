import os
import requests
from datetime import datetime
from flask import Flask, request
import logging

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

# ========== ТЕСТ ПОДКЛЮЧЕНИЯ К VETMANAGER ==========
def test_vetmanager_api():
    """Проверяет доступ к Vetmanager API"""
    url = f"{VETMANAGER_URL}/api/clients"
    headers = {"X-User-Token": VETMANAGER_KEY}
    
    logger.info(f"Тестирую подключение к Vetmanager...")
    logger.info(f"URL: {VETMANAGER_URL}")
    logger.info(f"Ключ: {VETMANAGER_KEY[:6]}...")
    
    try:
        response = requests.get(url, headers=headers, params={"limit": 1}, timeout=10)
        logger.info(f"Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            clients_count = len(data.get('data', []))
            logger.info(f"✅ API работает! Клиентов: {clients_count}")
            return True
        else:
            logger.error(f"❌ Ошибка API: {response.status_code}")
            logger.error(f"Ответ: {response.text[:100]}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка подключения: {e}")
        return False

# ========== ПОИСК КЛИЕНТА (ТЕСТОВАЯ ВЕРСИЯ) ==========
def find_client_by_phone(phone_input):
    """Поиск клиента - ТЕСТОВАЯ ВЕРСИЯ (всегда находит тестового клиента)"""
    
    # Сначала проверяем API
    if not test_vetmanager_api():
        logger.warning("API не доступен, используем тестовые данные")
    
    # Тестовые данные для проверки
    test_clients = [
        {
            'id': 20310,
            'firstName': 'Влад',
            'lastName': 'Зубанев',
            'phone': '+7(999)692-59-27',
            'email': ''
        },
        {
            'id': 1001,
            'firstName': 'Иван',
            'lastName': 'Иванов',
            'phone': '+7(911)123-45-67',
            'email': 'ivan@test.ru'
        }
    ]
    
    # Очищаем введенный номер
    input_clean = ''.join(filter(str.isdigit, str(phone_input)))
    
    logger.info(f"Поиск клиента по номеру: '{phone_input}' (очищенный: {input_clean})")
    
    # Ищем среди тестовых клиентов
    for client in test_clients:
        client_phone = str(client.get('phone', ''))
        client_clean = ''.join(filter(str.isdigit, client_phone))
        
        # Убираем +7 или 8 в начале
        if input_clean.startswith('8'):
            input_clean = input_clean[1:]  # 8999 → 999
        elif input_clean.startswith('7'):
            input_clean = input_clean[1:]  # 7999 → 999
        
        if client_clean.startswith('8'):
            client_clean = client_clean[1:]
        elif client_clean.startswith('7'):
            client_clean = client_clean[1:]
        
        # Сравниваем (последние 10 или 9 цифр)
        if len(input_clean) >= 9 and len(client_clean) >= 9:
            if input_clean[-9:] == client_clean[-9:]:
                logger.info(f"✅ Найден клиент: {client['firstName']} {client['lastName']}")
                return {
                    'id': client['id'],
                    'name': f"{client['firstName']} {client['lastName']}",
                    'phone': client['phone'],
                    'email': client.get('email', '')
                }
    
    logger.warning(f"❌ Клиент не найден для номера: {phone_input}")
    return None

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
    
    welcome_text = """🎉 <b>ДОБРО ПОЖАЛОВАТЬ В VIP-КЛУБ VETCLINIC!</b>

<b>🔥 ЭКСКЛЮЗИВНЫЕ ПРЕИМУЩЕСТВА:</b>
1️⃣ <b>Автонапоминания</b> о визитах
2️⃣ <b>Первыми об акциях</b>
3️⃣ <b>Напоминания о прививках</b>
4️⃣ <b>Экспресс-запись</b>

<b>📱 Введите номер телефона из вашей карты:</b>

💡 <i>Примеры форматов:</i>
• <code>+7(999)692-59-27</code>
• <code>89996925927</code>
• <code>9996925927</code></i>"""
    
    send_telegram_message(chat_id, welcome_text)

def handle_phone_input(chat_id, phone_input):
    """Обработка введенного номера телефона"""
    user_sessions.pop(chat_id, None)
    
    logger.info(f"Пользователь {chat_id} ввел номер: {phone_input}")
    
    # Тестовый режим: всегда находим тестового клиента
    if phone_input in ['+7(999)692-59-27', '89996925927', '9996925927', 'test']:
        client = {
            'id': 20310,
            'name': 'Влад Зубанев',
            'phone': '+7(999)692-59-27',
            'email': ''
        }
        
        success_message = f"""🎊 <b>ПОЗДРАВЛЯЕМ! ВЫ В VIP-КЛУБЕ!</b>

Добро пожаловать, {client['name']}! 🐕🐈

✅ Вы подключены к системе VIP-уведомлений!

<b>Теперь вы будете получать:</b>
• Напоминания о визитах
• Специальные предложения
• Важные уведомления

С заботой о вашем питомце,
Команда VetClinic 🏥"""
        
        send_telegram_message(chat_id, success_message)
        
        # Уведомление администратору
        admin_msg = f"""📱 <b>НОВЫЙ VIP-КЛИЕНТ (ТЕСТ)</b>

👤 Имя: {client['name']}
📞 Телефон: {client['phone']}
🆔 Telegram ID: {chat_id}
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

✅ Система работает!"""
        
        send_telegram_message(ADMIN_ID, admin_msg)
        logger.info(f"Тестовый клиент найден: {client['name']}")
        
    else:
        # Пробуем найти через API
        client = find_client_by_phone(phone_input)
        
        if client:
            success_message = f"""🎊 <b>ПОЗДРАВЛЯЕМ! ВЫ В VIP-КЛУБЕ!</b>

Добро пожаловать, {client['name']}! 🐕🐈

✅ Вы подключены к системе VIP-уведомлений!

С заботой о вашем питомце,
Команда VetClinic 🏥"""
            
            send_telegram_message(chat_id, success_message)
            
            admin_msg = f"""📱 <b>НОВЫЙ VIP-КЛИЕНТ</b>

👤 Имя: {client['name']}
📞 Телефон: {client['phone']}
🆔 Telegram ID: {chat_id}
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""
            
            send_telegram_message(ADMIN_ID, admin_msg)
            
        else:
            error_message = """❌ <b>Клиент не найден</b>

Для теста используйте:
• <code>+7(999)692-59-27</code>
• <code>89996925927</code>
• <code>9996925927</code>
• <code>test</code>

Или попробуйте снова: /start"""
            
            send_telegram_message(chat_id, error_message)

# ========== WEB ИНТЕРФЕЙС ==========
@app.route('/')
def home():
    return """
    <html>
    <head><title>🏥 VetClinic VIP Bot</title></head>
    <body style="font-family: Arial; margin: 40px;">
        <h1>🏥 VetClinic VIP Telegram Bot</h1>
        <p>Система в тестовом режиме</p>
        <p><strong>Тестовые номера:</strong></p>
        <ul>
            <li>+7(999)692-59-27</li>
            <li>89996925927</li>
            <li>9996925927</li>
            <li>test</li>
        </ul>
        <p><a href="/health">Проверить статус</a></p>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    return {
        "status": "healthy",
        "service": "vetclinic-vip-bot",
        "timestamp": datetime.now().isoformat(),
        "version": "test-1.0",
        "test_numbers": ["+7(999)692-59-27", "89996925927", "9996925927", "test"]
    }

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
    logger.info("🚀 Запуск VetClinic VIP Bot (ТЕСТОВАЯ ВЕРСИЯ)...")
    
    # Проверяем подключение к API
    test_vetmanager_api()
    
    # Настраиваем webhook
    setup_webhook()
    
    # Отправляем сообщение о запуске
    startup_msg = f"""🚀 <b>VIP БОТ ЗАПУЩЕН (ТЕСТ)</b>

✅ Система в тестовом режиме
🏥 Клиника: VetClinic
🔗 Бот: @Fulsim_bot
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>ТЕСТОВЫЕ НОМЕРА:</b>
• +7(999)692-59-27
• 89996925927
• 9996925927
• test

Готов к тестированию! 🐾"""
    
    send_telegram_message(ADMIN_ID, startup_msg)
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
