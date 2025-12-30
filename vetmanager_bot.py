import os
import requests
import json
import random
import string
from datetime import datetime, timedelta
from flask import Flask, request
import logging
from threading import Thread
import time

app = Flask(__name__)

# ========== НАСТРОЙКИ ==========
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'ВАШ_ТОКЕН_ОТ_БОТА')
TELEGRAM_TOKEN = '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI'  # Ваш текущий бот
VETMANAGER_KEY = os.getenv('VETMANAGER_KEY', 'b5aa96-c7d6f9-7296aa-0c1670-805a64')
VETMANAGER_URL = os.getenv('VETMANAGER_URL', 'https://drug14.vetmanager2.ru')
ADMIN_ID = int(os.getenv('ADMIN_ID', 921853682))

# Промокоды и скидки
PROMO_DISCOUNT = 300  # 300 рублей скидки
PROMO_PREFIX = "VET"  # Префикс промокода: VET123456

# Хранилище сессий (в проде нужно Redis/БД)
user_sessions = {}

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
        print(f"Vetmanager error: {e}")
    
    return []

def find_client_by_phone(phone):
    """Ищет клиента по номеру телефона"""
    # Очищаем номер от лишних символов
    phone_clean = ''.join(filter(str.isdigit, str(phone)))
    
    # Ищем в Vetmanager
    clients = get_vetmanager_data("clients", {"filter[phone]": phone_clean})
    
    if clients:
        client = clients[0]
        return {
            'id': client.get('id'),
            'name': f"{client.get('firstName', '')} {client.get('lastName', '')}".strip(),
            'phone': phone_clean,
            'email': client.get('email', ''),
            'existing_promo': get_client_promo(client.get('id'))
        }
    
    return None

def get_client_promo(client_id):
    """Получает промокод клиента из customFields"""
    client_data = get_vetmanager_data(f"client/{client_id}")
    
    if client_data and 'customFields' in client_data:
        for field in client_data['customFields']:
            if field.get('fieldName') in ['promo_code', 'Промокод', 'Promo']:
                return field.get('fieldValue')
    
    return None

def save_telegram_and_promo(client_id, telegram_id, promo_code):
    """Сохраняет Telegram ID и промокод в Vetmanager"""
    update_url = f"{VETMANAGER_URL}/api/client/{client_id}"
    headers = {"X-User-Token": VETMANAGER_KEY}
    
    try:
        # Получаем текущие данные клиента
        response = requests.get(update_url, headers=headers)
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
            elif field.get('fieldName') == 'promo_code':
                field['fieldValue'] = promo_code
        
        if not telegram_field_exists:
            client_data['customFields'].append({
                'fieldName': 'Telegram',
                'fieldValue': str(telegram_id),
                'fieldType': 'text'
            })
        
        # Добавляем промокод если нет
        if not any(f.get('fieldName') == 'promo_code' for f in client_data['customFields']):
            client_data['customFields'].append({
                'fieldName': 'promo_code',
                'fieldValue': promo_code,
                'fieldType': 'text'
            })
        
        # Сохраняем изменения
        update_response = requests.put(update_url, headers=headers, json=client_data)
        return update_response.status_code == 200
        
    except Exception as e:
        print(f"Save error: {e}")
        return False

def generate_promo_code():
    """Генерирует уникальный промокод"""
    return PROMO_PREFIX + ''.join(random.choices(string.digits, k=6))

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
    except:
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
        elif text == '/promo':
            handle_promo(chat_id)
        elif chat_id in user_sessions and user_sessions[chat_id].get('waiting_for_phone'):
            handle_phone_input(chat_id, text)
        else:
            send_telegram_message(chat_id, "Используйте /start для начала")
    
    return 'OK'

def handle_start(chat_id):
    """Обработка команды /start"""
    user_sessions[chat_id] = {
        'waiting_for_phone': True,
        'step': 'phone_input'
    }
    
    welcome_text = f"""🎉 <b>Добро пожаловать в VetClinic!</b>

Получите <b>{PROMO_DISCOUNT}₽ скидку</b> на следующий визит в ветклинику!

<b>Как это работает:</b>
1. Введите номер телефона, который указан в вашей карте
2. Система проверит вас в базе клиники
3. Вы получите персональный промокод
4. Покажите промокод на ресепшене при оплате

💡 <i>После регистрации вы будете получать:</i>
• Напоминания о визитах
• Уведомления о прививках
• Специальные акции

<b>Введите ваш номер телефона:</b>"""
    
    send_telegram_message(chat_id, welcome_text)

def handle_promo(chat_id):
    """Проверка существующего промокода"""
    # Можно добавить проверку по chat_id в базе
    send_telegram_message(chat_id, "Используйте /start для получения промокода")

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
            "Проверьте правильность номера или обратитесь на ресепшн клиники."
        )
        return
    
    # Проверяем, есть ли уже промокод
    if client['existing_promo']:
        send_telegram_message(
            chat_id,
            f"✅ <b>Вы уже зарегистрированы!</b>\n\n"
            f"Ваш промокод: <code>{client['existing_promo']}</code>\n"
            f"Скидка: {PROMO_DISCOUNT}₽\n\n"
            f"<i>Покажите этот код на ресепшене</i> 🏥"
        )
        return
    
    # Генерируем новый промокод
    promo_code = generate_promo_code()
    
    # Сохраняем в Vetmanager
    success = save_telegram_and_promo(client['id'], chat_id, promo_code)
    
    if success:
        # Сообщение клиенту
        client_message = f"""✅ <b>Регистрация успешна!</b>

Добро пожаловать, {client['name']}!

<b>Ваш промокод:</b> <code>{promo_code}</code>
<b>Скидка:</b> {PROMO_DISCOUNT}₽ на следующий визит

💡 <i>Что теперь:</i>
1. Покажите промокод на ресепшене при оплате
2. Получайте напоминания о визитах
3. Будьте в курсе акций и важных уведомлений

Спасибо, что с нами! 🐾"""
        
        send_telegram_message(chat_id, client_message)
        
        # Уведомление администратору
        admin_message = f"""📱 <b>НОВЫЙ КЛИЕНТ В TELEGRAM</b>

👤 Имя: {client['name']}
📞 Телефон: {client['phone']}
🆔 Telegram ID: {chat_id}
🎫 Промокод: {promo_code}
💰 Скидка: {PROMO_DISCOUNT}₽

Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""
        
        send_telegram_message(ADMIN_ID, admin_message)
        
        # Логируем
        print(f"New client: {client['name']}, Promo: {promo_code}")
    else:
        send_telegram_message(
            chat_id,
            "❌ <b>Ошибка регистрации</b>\n\n"
            "Пожалуйста, обратитесь на ресепшн клиники."
        )

# ========== АВТОМАТИЧЕСКИЕ ФУНКЦИИ ==========
def check_and_send_reminders():
    """Проверяет завтрашние записи и отправляет напоминания"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Получаем завтрашние записи
    appointments = get_vetmanager_data("appointments", {
        "filter[date]": tomorrow,
        "limit": 50
    })
    
    if not appointments:
        return
    
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
            # Отправляем напоминание
            reminder = f"""🔔 <b>НАПОМИНАНИЕ О ВИЗИТЕ</b>

Добрый день! Напоминаем, что завтра {tomorrow} в {app_time}
у вас запись в ветклинике с {pet_name}.

📍 Адрес: [Ваш адрес]
📞 Телефон: [Ваш телефон]

<i>Пожалуйста, подтвердите визит ответным сообщением!</i>"""
            
            send_telegram_message(telegram_id, reminder)

# ========== WEB ИНТЕРФЕЙС ДЛЯ АДМИНА ==========
@app.route('/')
def home():
    return """
    <html>
    <head>
        <title>VetClinic Telegram Bot</title>
        <style>
            body { font-family: Arial; margin: 40px; }
            .container { max-width: 800px; margin: 0 auto; }
            .card { background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 10px; }
            .btn { display: inline-block; padding: 10px 20px; background: #0088cc; 
                   color: white; text-decoration: none; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏥 VetClinic Telegram Bot</h1>
            
            <div class="card">
                <h2>🤖 Бот-регистратор</h2>
                <p>Клиенты получают промокод 300₽ в обмен на Telegram ID</p>
                <p><strong>Ссылка для клиентов:</strong></p>
                <p><code>https://t.me/VetClinicHelperBot</code></p>
                <a href="https://t.me/VetClinicHelperBot" class="btn" target="_blank">Открыть бота</a>
            </div>
            
            <div class="card">
                <h2>⚡ Быстрые действия</h2>
                <p><a href="/send_reminders" class="btn">Отправить напоминания</a></p>
                <p><a href="/stats" class="btn">Статистика</a></p>
            </div>
            
            <div class="card">
                <h2>📊 Инструкция для персонала</h2>
                <p>Говорите клиентам: "Хотите получать напоминания и скидки в Telegram? 
                Вот наш бот: t.me/VetClinicHelperBot"</p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/send_reminders')
def manual_reminders():
    """Ручная отправка напоминаний"""
    Thread(target=check_and_send_reminders).start()
    return "Напоминания отправляются..."

# ========== ЗАПУСК ==========
def setup_webhook():
    """Настройка webhook для Telegram"""
    webhook_url = f"https://vetmanager-bot-1.onrender.com/webhook"
    set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(set_url)
        print(f"Webhook setup: {response.json()}")
    except Exception as e:
        print(f"Webhook error: {e}")

if __name__ == "__main__":
    print("🚀 Запуск VetClinic Telegram Bot...")
    
    # Настраиваем webhook
    setup_webhook()
    
    # Отправляем сообщение о запуске
    startup_msg = f"""🚀 <b>БОТ-РЕГИСТРАТОР ЗАПУЩЕН</b>

✅ Система готова собирать Telegram ID клиентов
🎫 Промокод: {PROMO_DISCOUNT}₽ скидки
🔗 Ссылка: t.me/VetClinicHelperBot
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

Клиенты могут регистрироваться и получать промокоды!"""
    
    send_telegram_message(ADMIN_ID, startup_msg)
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
