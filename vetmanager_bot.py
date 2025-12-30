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
    headers = {"X-User-Token": VETMANAGER_KEY}
    url = f"{VETMANAGER_URL}/api/{endpoint}"
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            return response.json().get("data", [])
    except:
        pass
    return []

def find_client_by_phone(phone):
    phone_clean = ''.join(filter(str.isdigit, str(phone)))
    if len(phone_clean) < 10:
        return None
    clients = get_vetmanager_data("clients", {"filter[phone]": phone_clean})
    if clients:
        client = clients[0]
        return {
            'id': client.get('id'),
            'name': f"{client.get('firstName', '')} {client.get('lastName', '')}".strip(),
            'phone': phone_clean
        }
    return None

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json().get("ok", False)
    except:
        return False

# ========== ТЕЛЕГРАМ БОТ ==========
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    data = request.json
    if 'message' in data:
        message = data['message']
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        
        if text == '/start':
            handle_start(chat_id)
        elif chat_id in user_sessions:
            handle_phone_input(chat_id, text)
    
    return 'OK'

def handle_start(chat_id):
    user_sessions[chat_id] = {'waiting': True}
    
    welcome_text = """🎉 <b>ДОБРО ПОЖАЛОВАТЬ В VIP-КЛУБ VETCLINIC!</b>

<b>🔥 ЭКСКЛЮЗИВНЫЕ ПРЕИМУЩЕСТВА:</b>
1️⃣ <b>Автонапоминания</b> о визитах
2️⃣ <b>Первыми об акциях</b>
3️⃣ <b>Напоминания о прививках</b>
4️⃣ <b>Экспресс-запись</b>

<b>📱 Введите номер телефона из вашей карты:</b>"""
    
    send_telegram_message(chat_id, welcome_text)

def handle_phone_input(chat_id, phone_input):
    user_sessions.pop(chat_id, None)
    
    client = find_client_by_phone(phone_input)
    
    if not client:
        send_telegram_message(chat_id, "❌ Клиент не найден. Попробуйте /start")
        return
    
    send_telegram_message(
        chat_id,
        f"""🎊 <b>ПОЗДРАВЛЯЕМ! ВЫ В VIP-КЛУБЕ!</b>

Добро пожаловать, {client['name']}! 🐕🐈

✅ Вы подключены к системе VIP-уведомлений!

<b>Теперь вы будете получать:</b>
• Напоминания о визитах
• Специальные предложения
• Важные уведомления

С заботой о вашем питомце! 🏥"""
    )
    
    send_telegram_message(
        ADMIN_ID,
        f"📱 НОВЫЙ VIP-КЛИЕНТ\nИмя: {client['name']}\nTelegram ID: {chat_id}"
    )

# ========== ВЕБ-ИНТЕРФЕЙС ==========
@app.route('/')
def home():
    return "🏥 VetClinic VIP Bot работает!"

@app.route('/health')
def health_check():
    return {"status": "ok"}

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🚀 VIP Bot запущен")
    
    # Настраиваем webhook
    webhook_url = f"https://vetmanager-bot-1.onrender.com/webhook"
    requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}")
    
    # Сообщение о запуске
    send_telegram_message(ADMIN_ID, "✅ VIP Bot перезапущен")
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
