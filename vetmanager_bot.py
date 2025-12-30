cd "C:\Users\vladz\OneDrive\Рабочий стол"

# 1. Удалите старый файл
Remove-Item -Path "vetmanager_bot.py" -Force -ErrorAction SilentlyContinue

# 2. Создайте новый файл с ВИП-кодом
@'
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

# Хранилище сессий
user_sessions = {}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== VETMANAGER ФУНКЦИИ ==========
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
    phone_clean = ''.join(filter(str.isdigit, str(phone)))
    
    if len(phone_clean) < 10:
        return None
    
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
        response = requests.get(update_url, headers=headers)
        if response.status_code != 200:
            return False
            
        client_data = response.json().get('data', {})
        
        if 'customFields' not in client_data:
            client_data['customFields'] = []
        
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
        
        update_response = requests.put(update_url, headers=headers, json=client_data)
        return update_response.status_code == 200
        
    except Exception as e:
        logger.error(f"Save error: {e}")
        return False

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
        elif chat_id in user_sessions and user_sessions[chat_id].get('waiting_for_phone'):
            handle_phone_input(chat_id, text)
        else:
            send_telegram_message(chat_id, "Для начала работы отправьте /start")
    
    return 'OK'

def handle_start(chat_id):
    """Обработка команды /start - ВИП ВЕРСИЯ"""
    user_sessions[chat_id] = {'waiting_for_phone': True, 'step': 'phone_input'}
    
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
    user_sessions.pop(chat_id, None)
    
    client = find_client_by_phone(phone_input)
    
    if not client:
        send_telegram_message(
            chat_id,
            "❌ <b>Клиент не найден</b>\n\n"
            "Проверьте номер или обратитесь на ресепшн.\n"
            "Попробуйте снова: /start"
        )
        return
    
    if client_has_telegram(client['id']):
        send_telegram_message(
            chat_id,
            f"✅ <b>Вы уже в VIP-клубе!</b>\n\n"
            f"Рады снова видеть, {client['name']}! 🐾\n"
            f"Вы получаете все VIP-уведомления."
        )
        return
    
    if save_telegram_id(client['id'], chat_id):
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

3. <b>БЫСТРАЯ СВЯЗЬ</b>
   • Экспресс-запись через бота
   • Ответы на частые вопросы

<b>💬 Мы пишем только по делу и не спамим!</b>

С заботой о вашем питомце,
Команда VetClinic 🏥"""
        
        send_telegram_message(chat_id, client_message)
        
        admin_message = f"""📱 <b>НОВЫЙ VIP-КЛИЕНТ</b>

👤 Имя: {client['name']}
📞 Телефон: {client['phone']}
🆔 Telegram ID: {chat_id}
⭐ Статус: VIP-уведомления
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""
        
        send_telegram_message(ADMIN_ID, admin_message)
        logger.info(f"Новый VIP-клиент: {client['name']}")
    else:
        send_telegram_message(chat_id, "⚠️ <b>Ошибка подключения</b>\nОбратитесь на ресепшн.")

# ========== АВТОМАТИЧЕСКИЕ НАПОМИНАНИЯ ==========
def check_and_send_reminders():
    """Проверяет завтрашние записи и отправляет напоминания"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    appointments = get_vetmanager_data("appointments", {
        "filter[date]": tomorrow,
        "limit": 100
    })
    
    if not appointments:
        logger.info(f"На {tomorrow} записей нет")
        return
    
    sent_count = 0
    for app in appointments:
        client_id = app.get('client_id')
        app_time = app.get('time', '10:00')
        pet_name = app.get('pet_alias', 'питомец')
        
        client_data = get_vetmanager_data(f"client/{client_id}")
        if not client_data:
            continue
        
        telegram_id = None
        if 'customFields' in client_data:
            for field in client_data['customFields']:
                if field.get('fieldName') == 'Telegram':
                    telegram_id = field.get('fieldValue')
                    break
        
        if telegram_id:
            client_name = f"{client_data.get('firstName', '')} {client_data.get('lastName', '')}".strip()
            if not client_name:
                client_name = "Уважаемый клиент"
            
            reminder = f"""🔔 <b>НАПОМИНАНИЕ О ВИЗИТЕ</b>

Добрый день, {client_name}! 

Напоминаем, что <b>завтра {tomorrow} в {app_time}</b>
у вас запись в ветклинике с {pet_name}.

📍 <b>Адрес:</b> Ваша клиника
📞 <b>Телефон:</b> Ваш телефон

<i>Подтвердите визит ответным сообщением!</i>"""
            
            if send_telegram_message(telegram_id, reminder):
                sent_count += 1
    
    if sent_count > 0:
        report = f"""📊 <b>ОТЧЕТ ПО НАПОМИНАНИЯМ</b>

📅 Дата: {tomorrow}
✅ Отправлено: {sent_count} напоминаний
📋 Всего записей: {len(appointments)}"""
        
        send_telegram_message(ADMIN_ID, report)

# ========== WEB ИНТЕРФЕЙС ==========
@app.route('/')
def home():
    return """
    <html>
    <head><title>🏥 VetClinic VIP Bot</title></head>
    <body style="font-family: Arial; margin: 40px;">
        <h1>🏥 VetClinic VIP Telegram Bot</h1>
        <p>Система автоматических напоминаний</p>
        <p><a href="/send_reminders">Отправить напоминания</a></p>
        <p><a href="/health">Проверить статус</a></p>
    </body>
    </html>
    """

@app.route('/send_reminders')
def manual_reminders():
    """Ручная отправка напоминаний"""
    Thread(target=check_and_send_reminders).start()
    return "Напоминания отправляются..."

@app.route('/health')
def health_check():
    return {"status": "healthy", "time": datetime.now().isoformat()}

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
    logger.info("🚀 Запуск VetClinic VIP Bot...")
    
    setup_webhook()
    
    startup_msg = f"""🚀 <b>VIP БОТ ЗАПУЩЕН</b>

✅ Система VIP-уведомлений активирована
🏥 Клиника: VetClinic
🔗 Бот: @Fulsim_bot
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Готов к работе! 🐾"""
    
    send_telegram_message(ADMIN_ID, startup_msg)
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
'@ | Out-File -FilePath "vetmanager_bot.py" -Encoding UTF8

# 3. Проверьте файл
Get-Content vetmanager_bot.py -First 10

