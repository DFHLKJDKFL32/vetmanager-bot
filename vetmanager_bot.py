import os
import requests
from datetime import datetime
from flask import Flask, request
import logging

app = Flask(__name__)

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI'
ADMIN_ID = 921853682

# Хранилище сессий
user_sessions = {}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                "Для получения информации отправьте команду:\n\n"
                "<b>/start</b> - начать поиск карты клиента"
            )
    
    return 'OK'

def handle_start(chat_id):
    """Обработка команды /start - четкие инструкции"""
    user_sessions[chat_id] = {'waiting': True}
    
    welcome_text = """🎉 <b>ДОБРО ПОЖАЛОВАТЬ В VETCLINIC!</b>

Я помогу вам получить информацию из вашей карты клиента.

<b>📱 ВАШИ ДЕЙСТВИЯ:</b>

1️⃣ <b>Введите номер телефона</b>, указанный в вашей карте
2️⃣ <b>Получите информацию</b> о себе и питомцах
3️⃣ <b>Узнайте о ближайших записях</b>

<b>👇 ВВЕДИТЕ ВАШ НОМЕР ТЕЛЕФОНА:</b>

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
    
    logger.info(f"Пользователь {chat_id} ввел номер: {phone_input}")
    
    # Сначала показываем что ищем
    send_telegram_message(chat_id, "🔍 <b>Ищу вашу карту в базе...</b>")
    
    # Тестовые данные для демонстрации
    test_data = {
        '+7(999)692-59-27': {
            'name': 'Влад Зубанев',
            'phone': '+7(999)692-59-27',
            'email': 'vlad@example.com',
            'balance': '0 руб.',
            'pets': ['Барсик (кот)', 'Шарик (собака)'],
            'appointments': ['Завтра в 15:00 - Барсик', '05.01.2026 в 11:00 - Шарик']
        },
        '89996925927': {
            'name': 'Влад Зубанев',
            'phone': '+7(999)692-59-27',
            'email': 'vlad@example.com',
            'balance': '0 руб.',
            'pets': ['Барсик (кот)', 'Шарик (собака)'],
            'appointments': ['Завтра в 15:00 - Барсик', '05.01.2026 в 11:00 - Шарик']
        },
        '9996925927': {
            'name': 'Влад Зубанев', 
            'phone': '+7(999)692-59-27',
            'email': 'vlad@example.com',
            'balance': '0 руб.',
            'pets': ['Барсик (кот)', 'Шарик (собака)'],
            'appointments': ['Завтра в 15:00 - Барсик', '05.01.2026 в 11:00 - Шарик']
        }
    }
    
    # Проверяем тестовые данные
    normalized_input = phone_input.strip()
    
    if normalized_input in test_data:
        client = test_data[normalized_input]
        
        # Формируем информацию
        message_parts = []
        
        message_parts.append("✅ <b>ВАША КАРТА КЛИЕНТА</b>")
        message_parts.append("═" * 30)
        message_parts.append(f"👤 <b>Имя:</b> {client['name']}")
        message_parts.append(f"📞 <b>Телефон:</b> {client['phone']}")
        message_parts.append(f"📧 <b>Email:</b> {client['email']}")
        message_parts.append(f"💰 <b>Баланс:</b> {client['balance']}")
        
        message_parts.append("")
        message_parts.append("🐾 <b>ВАШИ ПИТОМЦЫ:</b>")
        for i, pet in enumerate(client['pets'], 1):
            message_parts.append(f"{i}. {pet}")
        
        message_parts.append("")
        message_parts.append("📅 <b>БЛИЖАЙШИЕ ЗАПИСИ:</b>")
        for i, appointment in enumerate(client['appointments'], 1):
            message_parts.append(f"{i}. {appointment}")
        
        message_parts.append("")
        message_parts.append("═" * 30)
        message_parts.append("🏥 <b>ВЕТКЛИНИКА VETCLINIC</b>")
        message_parts.append("📍 Адрес: г. Ростов-на-Дону")
        message_parts.append("📞 Телефон: +7 (XXX) XXX-XX-XX")
        message_parts.append("⏰ Часы работы: Пн-Пт 9:00-20:00, Сб-Вс 10:00-18:00")
        
        message_parts.append("")
        message_parts.append("💡 <i>Для записи на прием обратитесь на ресепшн</i>")
        
        # Отправляем клиенту
        send_telegram_message(chat_id, "\n".join(message_parts))
        
        # Уведомление администратору
        admin_msg = f"""📱 <b>КЛИЕНТ ПОЛУЧИЛ КАРТУ</b>

👤 Клиент: {client['name']}
📞 Телефон: {client['phone']}
🆔 Telegram ID: {chat_id}
📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}

✅ Тестовая система работает!"""
        
        send_telegram_message(ADMIN_ID, admin_msg)
        
    else:
        # Если номер не тестовый
        send_telegram_message(
            chat_id,
            "❌ <b>Клиент не найден</b>\n\n"
            "<b>Для теста используйте:</b>\n"
            "• <code>+7(999)692-59-27</code>\n"
            "• <code>89996925927</code>\n"
            "• <code>9996925927</code>\n\n"
            "<b>Или попробуйте снова:</b> /start"
        )
        
        # Логируем попытку
        logger.info(f"Неизвестный номер: {phone_input}")

# ========== WEB ИНТЕРФЕЙС ==========
@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>🏥 VetClinic Info Bot</title>
        <style>
            body { font-family: Arial; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .card { background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 10px; }
            .btn { padding: 10px 20px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px; }
            .instruction { background: #e8f4f8; padding: 15px; border-left: 4px solid #0088cc; margin: 15px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏥 VetClinic Telegram Bot</h1>
            <p>Система получения информации для клиентов</p>
            
            <div class="card">
                <h2>📱 Как работает бот:</h2>
                <div class="instruction">
                    <h3>1. Клиент пишет:</h3>
                    <p><code>/start</code></p>
                </div>
                <div class="instruction">
                    <h3>2. Бот просит:</h3>
                    <p><b>"Введите ваш номер телефона"</b></p>
                </div>
                <div class="instruction">
                    <h3>3. Клиент вводит номер:</h3>
                    <p>Например: <code>+7(999)692-59-27</code></p>
                </div>
                <div class="instruction">
                    <h3>4. Бот показывает:</h3>
                    <p>• Имя клиента<br>• Питомцы<br>• Ближайшие записи<br>• Контакты клиники</p>
                </div>
            </div>
            
            <div class="card">
                <h2>🔗 Ссылки</h2>
                <p><strong>Telegram бот:</strong> @Fulsim_bot</p>
                <p><strong>Команда для начала:</strong> <code>/start</code></p>
                <p><strong>Тестовые номера:</strong> +7(999)692-59-27, 89996925927, 9996925927</p>
            </div>
            
            <div class="card">
                <h2>✅ Статус системы</h2>
                <p><strong>Статус:</strong> 🟢 Работает (тестовый режим)</p>
                <p><strong>Последнее обновление:</strong> """ + datetime.now().strftime('%d.%m.%Y %H:%M') + """</p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    return {
        "status": "healthy",
        "service": "vetclinic-telegram-bot",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0",
        "bot": "@Fulsim_bot",
        "test_numbers": ["+7(999)692-59-27", "89996925927", "9996925927"]
    }

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
    logger.info("🚀 Запуск VetClinic Telegram Bot (тестовый режим)...")
    
    # Настраиваем webhook
    setup_webhook()
    
    # Отправляем сообщение о запуске
    startup_msg = f"""🚀 <b>ТЕЛЕГРАМ БОТ ЗАПУЩЕН</b>

✅ Система получения информации для клиентов
🏥 Клиника: VetClinic  
🔗 Бот: @Fulsim_bot
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>КАК РАБОТАЕТ:</b>
1. Клиент пишет /start
2. Бот просит номер телефона
3. Клиент вводит номер
4. Бот показывает информацию

<b>ТЕСТОВЫЕ НОМЕРА:</b>
• +7(999)692-59-27
• 89996925927  
• 9996925927

Готов к работе! 🐾"""
    
    send_telegram_message(ADMIN_ID, startup_msg)
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
