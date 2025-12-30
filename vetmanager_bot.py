```python
import os
import requests
import json
from datetime import datetime, timedelta
from flask import Flask, request
import logging
from threading import Thread
import time

app = Flask(__name__)

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI')
VETMANAGER_KEY = os.getenv('VETMANAGER_KEY', 'b5aa96-c7d6f9-7296aa-0c1670-805a64')
VETMANAGER_URL = os.getenv('VETMANAGER_URL', 'https://drug14.vetmanager2.ru')
ADMIN_ID = int(os.getenv('ADMIN_ID', 921853682))

# Хранилище сессий (временное, для прода нужно Redis)
user_sessions = {}

# Настройка логирования
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

def find_client_by_phone(phone):
    """Ищет клиента по номеру телефона"""
    # Очищаем номер от лишних символов
    phone_clean = ''.join(filter(str.isdigit, str(phone)))
    
    if len(phone_clean) < 10:
        return None
    
    # Ищем в Vetmanager
    clients = get_vetmanager_data("clients", {"filter[phone]": phone_clean})
    
    if clients:
        client = clients[0]
        return {
            'id': client.get('id'),
            'name': f"{client.get('firstName', '')} {client.get('lastName', '')}".strip(),
            'phone': phone_clean,
            'email': client.get('email', '')
        }
    
    return None

def client_has_telegram(client_id):
    """Проверяет, есть ли у клиента Telegram ID"""
    client_data = get_vetmanager_data(f"client/{client_id}")
    
    if client_data and 'customFields' in client_data:
        for field in client_data['customFields']:
            if field.get('fieldName') == 'Telegram':
                return True
    return False

def save_telegram_id(client_id, telegram_id):
    """Сохраняет Telegram ID в Vetmanager"""
    update_url = f"{VETMANAGER_URL}/api/client/{client_id}"
    headers = {"X-User-Token": VETMANAGER_KEY}
    
    try:
        # Получаем текущие данные клиента
        response = requests.get(update_url, headers=headers)
        if response.status_code != 200:
            return False
            
        client_data = response.json().get('data', {})
        
        # Добавляем/обновляем customFields
        if 'customFields' not in client_data:
            client_data['customFields'] = []
        
        # Обновляем или добавляем Telegram поле
        telegram_field_exists = False
        for field in client_data['customFields']:
            if field.get('fieldName') == 'Telegram':
                field['fieldValue'] = str(telegram_id)
                telegram_field_exists = True
                break
        
        if not telegram_field_exists:
            client_data['customFields'].append({
                'fieldName': 'Telegram',
                'fieldValue': str(telegram_id),
                'fieldType': 'text'
            })
        
        # Сохраняем изменения
        update_response = requests.put(update_url, headers=headers, json=client_data)
        return update_response.status_code == 200
        
    except Exception as e:
        logger.error(f"Save error: {e}")
        return False

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

# ========== ТЕЛЕГРАМ БОТ WEBHOOK ==========
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    """Обработчик сообщений от Telegram"""
    data = request.json
    
    if 'message' in data:
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        
        # Обработка команд
        if text == '/start':
            handle_start(chat_id)
        elif chat_id in user_sessions and user_sessions[chat_id].get('waiting_for_phone'):
            handle_phone_input(chat_id, text)
        else:
            send_telegram_message(chat_id, "Для начала работы отправьте /start")
    
    return 'OK'

def handle_start(chat_id):
    """Обработка команды /start"""
    user_sessions[chat_id] = {
        'waiting_for_phone': True,
        'step': 'phone_input'
    }
    
    welcome_text = """🎉 <b>ДОБРО ПОЖАЛОВАТЬ В VIP-КЛУБ VETCLINIC!</b>

Подключите Telegram-уведомления и получайте:

<b>🔥 ЭКСКЛЮЗИВНЫЕ ПРЕИМУЩЕСТВА:</b>
1️⃣ <b>Автонапоминания</b> — никогда не пропустите визит
2️⃣ <b>Первыми узнавайте об акциях</b> — скидки, распродажи, спецпредложения
3️⃣ <b>Напоминания о прививках</b> — здоровье питомца под контролем
4️⃣ <b>Экспресс-запись</b> — бронируйте время в 2 клика
5️⃣ <b>Быстрая связь с врачом</b> — задавайте вопросы в чате

<b>📱 КАК ПОДКЛЮЧИТЬ:</b>
1. Введите номер телефона из вашей карты
2. Получите подтверждение подключения
3. Наслаждайтесь заботой о питомце!

<b>💡 ЭТО БЕСПЛАТНО И СОХРАНЯЕТ ВАШЕ ВРЕМЯ!</b>

Введите ваш номер телефона:"""
    
    send_telegram_message(chat_id, welcome_text)

def handle_phone_input(chat_id, phone_input):
    """Обработка введенного номера телефона"""
    # Удаляем сессию
    user_sessions.pop(chat_id, None)
    
    # Ищем клиента
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
    
    # Проверяем, есть ли уже Telegram ID
    if client_has_telegram(client['id']):
        send_telegram_message(
            chat_id,
            f"✅ <b>Вы уже в VIP-клубе!</b>\n\n"
            f"Рады снова видеть, {client['name']}! 🐾\n\n"
            f"<i>Вы уже получаете:</i>\n"
            f"• Напоминания о визитах\n"
            f"• Специальные предложения\n"
            f"• Важные уведомления\n\n"
            f"Спасибо, что с нами!"
        )
        return
    
    # Сохраняем Telegram ID в Vetmanager
    success = save_telegram_id(client['id'], chat_id)
    
    if success:
        # Поздравительное сообщение клиенту
        client_message = f"""🎊 <b>ПОЗДРАВЛЯЕМ! ВЫ В VIP-КЛУБЕ!</b>

Добро пожаловать, {client['name']}! 🐕🐈

<b>✅ ВАШИ НОВЫЕ ВОЗМОЖНОСТИ:</b>

1. <b>АВТОНАПОМИНАНИЯ</b>
   • За день до визита
   • За 2 часа до визита
   • О прививках и процедурах

2. <b>ЭКСКЛЮЗИВНЫЕ АКЦИИ</b>
   • Первыми узнаете о скидках
   • Спецпредложения только для VIP
   • Бонусы за рекомендации

3. <b>БЫСТРАЯ СВЯЗЬ</b>
   • Экспресс-запись через бота
   • Ответы на частые вопросы
   • Экстренные уведомления

4. <b>ЗАБОТА О ПИТОМЦЕ</b>
   • Напоминания о прививках
   • Рекомендации по уходу
   • История посещений

<b>🎯 ЧТО ДЕЛАТЬ ДАЛЬШЕ?</b>
1. Ждите напоминание перед следующим визитом
2. Следите за акциями в этом чате
3. Для записи напишите: "Запись"

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
⭐ Статус: VIP-уведомления
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>Клиент подключен к системе уведомлений!</b>"""
        
        send_telegram_message(ADMIN_ID, admin_message)
        
        logger.info(f"Новый VIP-клиент: {client['name']}, ID: {chat_id}")
    else:
        send_telegram_message(
            chat_id,
            "⚠️ <b>Техническая ошибка</b>\n\n"
            "Пожалуйста, сообщите на ресепшн о проблеме.\n"
            "Мы вас обязательно подключим!"
        )

# ========== АВТОМАТИЧЕСКИЕ ФУНКЦИИ ==========
def check_and_send_reminders():
    """Проверяет завтрашние записи и отправляет напоминания"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Получаем завтрашние записи
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
        
        # Получаем данные клиента
        client_data = get_vetmanager_data(f"client/{client_id}")
        if not client_data:
            continue
        
        # Ищем Telegram ID
        telegram_id = None
        if 'customFields' in client_data:
            for field in client_data['customFields']:
                if field.get('fieldName') == 'Telegram':
                    telegram_id = field.get('fieldValue')
                    break
        
        if telegram_id:
            # Получаем имя клиента
            client_name = f"{client_data.get('firstName', '')} {client_data.get('lastName', '')}".strip()
            if not client_name:
                client_name = "Уважаемый клиент"
            
            # Отправляем напоминание
            reminder = f"""🔔 <b>НАПОМИНАНИЕ О ВИЗИТЕ</b>

Добрый день, {client_name}! 

Напоминаем, что <b>завтра {tomorrow} в {app_time}</b>
у вас запись в ветклинике с {pet_name}.

📍 <b>Адрес:</b> [Ваш адрес клиники]
📞 <b>Телефон:</b> [Ваш телефон]

<i>Пожалуйста, подтвердите визит ответным сообщением "Подтверждаю"!</i>"""
            
            if send_telegram_message(telegram_id, reminder):
                sent_count += 1
                logger.info(f"Напоминание отправлено: {client_name}, {app_time}")
    
    # Отчет администратору
    if sent_count > 0:
        report = f"""📊 <b>ОТЧЕТ ПО НАПОМИНАНИЯМ</b>

📅 Дата: {tomorrow}
✅ Отправлено: {sent_count} напоминаний
📋 Всего записей: {len(appointments)}

Время отправки: {datetime.now().strftime('%H:%M')}"""
        
        send_telegram_message(ADMIN_ID, report)

# ========== WEB ИНТЕРФЕЙС ДЛЯ АДМИНА ==========
@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>🏥 VetClinic VIP Telegram Bot</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa; }
            .container { max-width: 800px; margin: 0 auto; }
            .card { background: white; padding: 25px; margin: 20px 0; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .btn { display: inline-block; padding: 12px 24px; background: #0088cc; 
                   color: white; text-decoration: none; border-radius: 8px; font-weight: bold; }
            .btn:hover { background: #006699; }
            h1 { color: #2c3e50; }
            .status { color: #27ae60; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏥 VetClinic VIP Telegram Bot</h1>
            
            <div class="card">
                <h2>🤖 Бот VIP-уведомлений</h2>
                <p>Система автоматических напоминаний и эксклюзивных предложений для клиентов</p>
                <p><strong>Ссылка для клиентов:</strong></p>
                <p><code>https://t.me/Fulsim_bot</code></p>
                <a href="https://t.me/Fulsim_bot" class="btn" target="_blank">🔗 Открыть бота</a>
            </div>
            
            <div class="card">
                <h2>⚡ Управление системой</h2>
                <p><a href="/send_reminders" class="btn">📨 Отправить напоминания</a></p>
                <p><a href="/check_webhook" class="btn">🔧 Проверить Webhook</a></p>
                <p><a href="/health" class="btn">❤️ Проверить здоровье</a></p>
            </div>
            
            <div class="card">
                <h2>📊 Инструкция для персонала</h2>
                <p><strong>Что говорить клиентам:</strong></p>
                <p>"Подключите VIP-уведомления в Telegram! Вы будете получать напоминания о визитах, 
                первыми узнавать об акциях и никогда не пропустите важную прививку питомца. 
                Это бесплатно! Просто напишите <code>/start</code> в @Fulsim_bot"</p>
                
                <p><strong>Преимущества для клиники:</strong></p>
                <ul>
                    <li>Снижение no-show до 50%</li>
                    <li>Прямой канал связи с клиентами</li>
                    <li>Автоматические напоминания</li>
                    <li>Повышение лояльности</li>
                </ul>
            </div>
            
            <div class="card">
                <p class="status">✅ Система работает | Последнее обновление: """ + datetime.now().strftime('%d.%m.%Y %H:%M') + """</p>
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
        <h1>✅ Напоминания отправляются...</h1>
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
        "telegram_configured": bool(TELEGRAM_TOKEN),
        "vetmanager_connected": bool(VETMANAGER_KEY),
        "webhook_url": "https://vetmanager-bot-1.onrender.com/webhook"
    }

@app.route('/check_webhook')
def check_webhook():
    """Проверка статуса webhook"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getWebhookInfo"
    try:
        response = requests.get(url)
        return response.json()
    except:
        return {"error": "Cannot check webhook"}

# ========== ЗАПУСК СИСТЕМЫ ==========
def setup_webhook():
    """Настройка webhook для Telegram"""
    webhook_url = f"https://vetmanager-bot-1.onrender.com/webhook"
    set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(set_url)
        logger.info(f"Webhook setup: {response.json()}")
    except Exception as e:
        logger.error(f"Webhook error: {e}")

if __name__ == "__main__":
    logger.info("🚀 Запуск VetClinic VIP Telegram Bot...")
    
    # Настраиваем webhook
    setup_webhook()
    
    # Отправляем сообщение о запуске
    startup_msg = f"""🚀 <b>VIP БОТ ЗАПУЩЕН</b>

✅ Система VIP-уведомлений активирована
🏥 Клиника: VetClinic
🔗 Бот: @Fulsim_bot
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>ВОЗМОЖНОСТИ СИСТЕМЫ:</b>
• Автоматические напоминания о визитах
• VIP-предложения для клиентов
• Уведомления о прививках
• Снижение no-show

Готов к работе! 🐾"""
    
    send_telegram_message(ADMIN_ID, startup_msg)
    
    # Запускаем Flask сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
```
