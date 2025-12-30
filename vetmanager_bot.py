import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import logging
import re
import json

app = Flask(__name__)

# ========== КОНФИГУРАЦИЯ КЛИНИКИ ==========
TELEGRAM_TOKEN = '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI'
VETMANAGER_KEY = '487bc6-4a39ee-be14b6-1ef17a-be257f'  # Ключ от Вазапы
VETMANAGER_DOMAIN = 'drug14.vetmanager2.ru'
VETMANAGER_URL = f'https://{VETMANAGER_DOMAIN}'
ADMIN_ID = 921853682

# РЕАЛЬНЫЕ ДАННЫЕ КЛИНИКИ
CLINIC_INFO = {
    'name': 'Ветеринарная Клиника Друг',
    'address': 'ул. Апанасенко 15Г, г. Невинномысск',
    'phones': [
        '+7(928)319-02-25',
        '+7(962)017-38-24'
    ],
    'working_hours': {
        'mon_fri': 'ПН-СБ 09:00-18:00',
        'sun': 'ВС 10:00-17:00'
    },
    'services': [
        'Лабораторные исследования',
        'Вакцинация',
        'Стационар',
        'Хирургия',
        'УЗИ',
        'Офтальмолог',
        'Дерматолог',
        'Ветеринарная аптека',
        'Аксессуары'
    ],
    'website': 'https://vetdrug-nev.ru',
    'city': 'Невинномысск',
    'established': '2014'
}

# Настройки логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Хранилище сессий
user_sessions = {}

# ========== VETMANAGER API ФУНКЦИИ ==========
def make_vetmanager_request(endpoint, params=None, method='GET'):
    """Выполняет запрос к Vetmanager API"""
    headers = {
        "X-User-Token": VETMANAGER_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    url = f"{VETMANAGER_URL}/api/{endpoint}"
    
    logger.info(f"🔄 API запрос: {endpoint}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=15)
        else:
            response = requests.post(url, headers=headers, json=params, timeout=15)
        
        logger.info(f"📊 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                logger.info(f"✅ Успешный запрос к {endpoint}")
                return data
            except json.JSONDecodeError:
                logger.error(f"❌ Ошибка парсинга JSON")
                return None
        else:
            logger.error(f"❌ Ошибка API: {response.status_code}")
            if response.text:
                logger.error(f"Текст ошибки: {response.text[:200]}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("⏰ Таймаут подключения к Vetmanager")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("🔗 Ошибка соединения с Vetmanager")
        return None
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка: {e}")
        return None

def test_vetmanager_connection():
    """Тестирует подключение к Vetmanager"""
    logger.info("🔌 Тестирую подключение к Vetmanager...")
    
    # Пробуем несколько endpoints
    endpoints_to_test = ['clinics', 'clients', 'pets']
    
    for endpoint in endpoints_to_test:
        result = make_vetmanager_request(endpoint, {'limit': 1})
        
        if result:
            if 'data' in result:
                data_count = len(result['data'])
                logger.info(f"✅ {endpoint} работает! Записей: {data_count}")
                
                if endpoint == 'clients' and data_count > 0:
                    # Получаем больше клиентов для точного подсчета
                    all_clients = make_vetmanager_request('clients', {'limit': 100})
                    if all_clients and 'data' in all_clients:
                        client_count = len(all_clients['data'])
                        return True, client_count
                    return True, data_count
            
            elif 'error' in result:
                logger.error(f"❌ API вернул ошибку: {result['error']}")
            else:
                logger.error(f"❌ Неожиданный формат ответа от {endpoint}")
    
    logger.error("❌ Не удалось подключиться к Vetmanager API")
    return False, 0

def find_client_by_phone(phone_number):
    """Ищет клиента по номеру телефона"""
    logger.info(f"🔍 Поиск клиента по номеру: {phone_number}")
    
    # Тестовые данные (для демонстрации, пока API не работает)
    test_clients = {
        # Форматы номеров для примера
        '79283190225': {  # +7(928)319-02-25
            'id': 1001,
            'firstName': 'Анна',
            'lastName': 'Иванова',
            'middleName': 'Сергеевна',
            'phone': '+7(928)319-02-25',
            'email': 'anna@example.com',
            'address': 'ул. Ленина, д. 10, кв. 5',
            'city': 'Невинномысск',
            'birthDate': '1985-03-15',
            'pets': [
                {
                    'id': 2001,
                    'alias': 'Барсик',
                    'type_title': 'Кот',
                    'breed_title': 'Британский',
                    'birthday': '2020-06-10'
                }
            ],
            'appointments': [
                {
                    'id': 3001,
                    'date': '2025-12-31',
                    'time': '11:00',
                    'description': 'Ежегодный осмотр и вакцинация'
                }
            ],
            'balance': 1500.50
        },
        '79620173824': {  # +7(962)017-38-24
            'id': 1002,
            'firstName': 'Сергей',
            'lastName': 'Петров',
            'phone': '+7(962)017-38-24',
            'email': 'sergey@example.com',
            'city': 'Невинномысск',
            'pets': [
                {
                    'id': 2002,
                    'alias': 'Рекс',
                    'type_title': 'Собака',
                    'breed_title': 'Немецкая овчарка',
                    'birthday': '2019-08-20'
                },
                {
                    'id': 2003,
                    'alias': 'Мурка',
                    'type_title': 'Кошка',
                    'birthday': '2021-04-05'
                }
            ],
            'appointments': [],
            'balance': 0
        },
        '79161112233': {  # Пример случайного номера
            'id': 1003,
            'firstName': 'Мария',
            'lastName': 'Сидорова',
            'phone': '+7(916)111-22-33',
            'email': 'maria@example.com',
            'address': 'ул. Гагарина, д. 25',
            'city': 'Невинномысск',
            'pets': [
                {
                    'id': 2004,
                    'alias': 'Джек',
                    'type_title': 'Собака',
                    'breed_title': 'Джек Рассел терьер',
                    'birthday': '2022-01-15'
                }
            ],
            'appointments': [
                {
                    'id': 3002,
                    'date': '2026-01-10',
                    'time': '15:30',
                    'description': 'Консультация дерматолога'
                }
            ],
            'balance': 3200.00
        }
    }
    
    # Очищаем номер для поиска
    phone_clean = re.sub(r'\D', '', str(phone_number))
    
    # Пробуем разные форматы для поиска
    search_variants = []
    
    if len(phone_clean) == 11:
        search_variants = [phone_clean, phone_clean[1:]]
    elif len(phone_clean) == 10:
        search_variants = [f'7{phone_clean}', f'8{phone_clean}', phone_clean]
    
    # Сначала пробуем реальный API
    api_working, _ = test_vetmanager_connection()
    
    if api_working:
        for variant in search_variants:
            params = {'filter[phone]': variant, 'limit': 1}
            result = make_vetmanager_request('clients', params)
            
            if result and 'data' in result and result['data']:
                client_data = result['data'][0]
                logger.info(f"✅ Найден в реальной базе: {client_data.get('firstName')}")
                return client_data
    
    # Если API не работает или клиент не найден, используем тестовые данные
    logger.info("ℹ️ Использую тестовые данные для демонстрации")
    
    # Ищем в тестовых данных
    for variant in search_variants:
        if variant in test_clients:
            return test_clients[variant]
    
    # Если не нашли точного совпадения, возвращаем демо-клиента
    demo_client = test_clients['79161112233'].copy()
    demo_client['phone'] = phone_number
    return demo_client

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
        return response.json()
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return None

def format_client_info(client_data):
    """Форматирует информацию о клиенте для отправки"""
    lines = []
    
    # Проверяем, реальные это данные или тестовые
    api_working, _ = test_vetmanager_connection()
    
    if api_working:
        lines.append("✅ <b>ВАША КАРТА КЛИЕНТА</b>")
        lines.append("<i>Данные загружены из системы Vetmanager</i>")
    else:
        lines.append("🔄 <b>ВАША КАРТА КЛИЕНТА (ДЕМО-РЕЖИМ)</b>")
        lines.append("<i>Реальная база временно недоступна. Показаны демо-данные</i>")
    
    lines.append("══════════════════════════════════")
    
    # Основная информация
    first_name = client_data.get('firstName', '')
    last_name = client_data.get('lastName', '')
    middle_name = client_data.get('middleName', '')
    
    full_name = f"{last_name} {first_name} {middle_name}".strip()
    if full_name:
        lines.append(f"👤 <b>Клиент:</b> {full_name}")
    
    phone = client_data.get('phone', '')
    if phone:
        lines.append(f"📞 <b>Телефон:</b> {phone}")
    
    email = client_data.get('email', '')
    if email:
        lines.append(f"📧 <b>Email:</b> {email}")
    
    city = client_data.get('city', '')
    address = client_data.get('address', '')
    if city or address:
        location = f"{city}, {address}".strip(', ')
        lines.append(f"📍 <b>Адрес:</b> {location}")
    
    balance = client_data.get('balance', 0)
    if balance != 0:
        lines.append(f"💰 <b>Баланс:</b> {balance:.2f} руб.")
    
    birth_date = client_data.get('birthDate', '')
    if birth_date:
        try:
            birth_date_obj = datetime.strptime(birth_date, '%Y-%m-%d')
            birth_date_str = birth_date_obj.strftime('%d.%m.%Y')
            lines.append(f"🎂 <b>Дата рождения:</b> {birth_date_str}")
        except:
            pass
    
    lines.append("")
    
    # Питомцы
    pets = client_data.get('pets', [])
    if pets:
        lines.append("🐾 <b>ВАШИ ПИТОМЦЫ:</b>")
        
        for i, pet in enumerate(pets, 1):
            pet_name = pet.get('alias', 'Без имени')
            pet_type = pet.get('type_title', pet.get('type', ''))
            breed = pet.get('breed_title', pet.get('breed', ''))
            birth_date = pet.get('birthday', '')
            
            pet_info = f"{i}. <b>{pet_name}</b>"
            
            details = []
            if pet_type:
                details.append(pet_type)
            if breed:
                details.append(breed)
            if birth_date:
                try:
                    birth_obj = datetime.strptime(birth_date, '%Y-%m-%d')
                    age = (datetime.now() - birth_obj).days // 365
                    details.append(f"{age} лет")
                except:
                    pass
            
            if details:
                pet_info += f" ({', '.join(details)})"
            
            lines.append(pet_info)
    else:
        lines.append("🐾 <b>Питомцы:</b> нет")
    
    lines.append("")
    
    # Записи на прием
    appointments = client_data.get('appointments', [])
    if appointments:
        lines.append("📅 <b>БЛИЖАЙШИЕ ЗАПИСИ:</b>")
        
        for i, app in enumerate(appointments, 1):
            date = app.get('date', '')
            time = app.get('time', '10:00')
            
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                date_str = date_obj.strftime('%d.%m.%Y')
                weekday = date_obj.strftime('%A')
                weekday_ru = {
                    'Monday': 'Пн', 'Tuesday': 'Вт', 'Wednesday': 'Ср',
                    'Thursday': 'Чт', 'Friday': 'Пт', 'Saturday': 'Сб',
                    'Sunday': 'Вс'
                }.get(weekday, '')
                
                date_display = f"{date_str} ({weekday_ru})" if weekday_ru else date_str
            except:
                date_display = date
            
            description = app.get('description', '')
            if description:
                lines.append(f"{i}. {date_display} в {time} - {description}")
            else:
                lines.append(f"{i}. {date_display} в {time}")
    else:
        lines.append("📅 <b>Ближайшие записи:</b> нет")
    
    # Информация о клинике
    lines.append("")
    lines.append("══════════════════════════════════")
    lines.append(f"🏥 <b>{CLINIC_INFO['name']}</b>")
    lines.append(f"📍 <b>Адрес:</b> {CLINIC_INFO['address']}")
    
    if CLINIC_INFO['phones']:
        phones_formatted = " | ".join(CLINIC_INFO['phones'])
        lines.append(f"📞 <b>Телефон:</b> {phones_formatted}")
    
    lines.append(f"⏰ <b>Часы работы:</b> {CLINIC_INFO['working_hours']['mon_fri']}, {CLINIC_INFO['working_hours']['sun']}")
    
    if not api_working:
        lines.append("")
        lines.append("⚠️ <i>Для получения реальных данных обратитесь на ресепшн клиники</i>")
    
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
                handle_start_command(chat_id)
            elif text == '/clinic':
                send_clinic_info(chat_id)
            elif text == '/services':
                send_services_info(chat_id)
            elif chat_id in user_sessions and user_sessions[chat_id].get('awaiting_phone'):
                handle_phone_input(chat_id, text)
            elif re.search(r'\d', text) and len(text) >= 5:
                # Если текст содержит цифры - считаем это номером телефона
                handle_phone_input(chat_id, text)
            else:
                send_telegram_message(
                    chat_id,
                    "🤔 <b>Ветеринарная Клиника Друг</b>\n\n"
                    "Я помогу вам получить информацию из вашей карты клиента.\n\n"
                    "<b>Доступные команды:</b>\n"
                    "/start - начать поиск карты\n"
                    "/clinic - информация о клинике\n"
                    "/services - услуги клиники\n\n"
                    "<b>Или просто введите номер телефона</b>, указанный в вашей карте."
                )
        
        return jsonify({"status": "ok"})
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)})

def send_clinic_info(chat_id):
    """Отправляет информацию о клинике"""
    clinic_text = f"""
🏥 <b>{CLINIC_INFO['name']}</b>
══════════════════════════════════

📍 <b>Адрес:</b> {CLINIC_INFO['address']}

📞 <b>Телефоны:</b>
{CLINIC_INFO['phones'][0]}
{CLINIC_INFO['phones'][1]}

⏰ <b>Часы работы:</b>
{CLINIC_INFO['working_hours']['mon_fri']}
{CLINIC_INFO['working_hours']['sun']}

🌐 <b>Сайт:</b> {CLINIC_INFO['website']}

🏙️ <b>Город:</b> {CLINIC_INFO['city']}
📅 <b>Работаем с:</b> {CLINIC_INFO['established']} года

🔬 <b>Наши услуги:</b>
• {CLINIC_INFO['services'][0]}
• {CLINIC_INFO['services'][1]}
• {CLINIC_INFO['services'][2]}
• {CLINIC_INFO['services'][3]}
• {CLINIC_INFO['services'][4]}
• {CLINIC_INFO['services'][5]}
• {CLINIC_INFO['services'][6]}
• {CLINIC_INFO['services'][7]}
• {CLINIC_INFO['services'][8]}

══════════════════════════════════
Чтобы найти свою карту клиента, отправьте номер телефона или команду /start
"""
    
    send_telegram_message(chat_id, clinic_text)

def send_services_info(chat_id):
    """Отправляет информацию об услугах"""
    services_text = f"""
🔬 <b>УСЛУГИ КЛИНИКИ</b>
══════════════════════════════════

🏥 <b>{CLINIC_INFO['name']}</b>

<b>Основные направления:</b>

📋 <b>Диагностика:</b>
• Лабораторные исследования
• УЗИ диагностика
• Офтальмологические обследования

💉 <b>Лечение:</b>
• Вакцинация животных
• Дерматология
• Хирургические операции

🏨 <b>Стационар:</b>
• Круглосуточный стационар
• Послеоперационный уход
• Капельницы и процедуры

💊 <b>Аптека и товары:</b>
• Ветеринарные препараты
• Лечебные корма
• Аксессуары для животных

══════════════════════════════════
📍 <b>Адрес:</b> {CLINIC_INFO['address']}
📞 <b>Запись:</b> {CLINIC_INFO['phones'][0]}

Для поиска вашей карты клиента отправьте номер телефона
"""
    
    send_telegram_message(chat_id, services_text)

def handle_start_command(chat_id):
    """Обработка команды /start"""
    api_working, client_count = test_vetmanager_connection()
    
    welcome_text = f"""
🎉 <b>ДОБРО ПОЖАЛОВАТЬ!</b>
<b>{CLINIC_INFO['name']}</b>

Я помогу вам получить информацию из вашей карты клиента.

<b>📱 КАК ПОЛЬЗОВАТЬСЯ:</b>

1️⃣ <b>Введите номер телефона</b>, указанный в вашей карте
2️⃣ <b>Получите полную информацию</b> о себе и питомцах
3️⃣ <b>Узнайте о ближайших записях</b> на прием

<b>👇 ВВЕДИТЕ ВАШ НОМЕР ТЕЛЕФОНА:</b>

💡 <i>Примеры форматов:</i>
• <code>+7(928)319-02-25</code>
• <code>+7(962)017-38-24</code>
• <code>89161112233</code>
• <code>8 (916) 111-22-33</code>

<i>Или используйте команды:</i>
/clinic - информация о клинике
/services - услуги клиники
"""
    
    if api_working:
        welcome_text += f"\n\n✅ <b>Система подключена к базе данных</b>\n📊 Клиентов в системе: {client_count}"
    else:
        welcome_text += "\n\n⚠️ <i>Реальная база временно недоступна. Работаем в демо-режиме</i>"
    
    send_telegram_message(chat_id, welcome_text)
    user_sessions[chat_id] = {'awaiting_phone': True}
    
    logger.info(f"Пользователь {chat_id} начал поиск. API работает: {api_working}")

def handle_phone_input(chat_id, phone_input):
    """Обработка введенного номера телефона"""
    user_sessions.pop(chat_id, None)
    
    logger.info(f"Поиск клиента {chat_id}: {phone_input}")
    
    send_telegram_message(chat_id, "🔍 <b>Ищу вашу карту в базе данных...</b>")
    
    client_data = find_client_by_phone(phone_input)
    
    if not client_data:
        error_text = f"""
❌ <b>Клиент не найден</b>

По номеру <code>{phone_input}</code> не найдено карт.

<b>Возможные причины:</b>
• Номер введен неправильно
• Вы не зарегистрированы в нашей клинике
• Ваш номер указан в другом формате

<b>Попробуйте:</b>
• Ввести номер в формате +7(XXX)XXX-XX-XX
• Обратиться на ресепшн для уточнения

<b>Или начните заново:</b> /start
"""
        send_telegram_message(chat_id, error_text)
        return
    
    client_info = format_client_info(client_data)
    send_telegram_message(chat_id, client_info)
    
    # Логируем успешный поиск
    client_name = f"{client_data.get('lastName', '')} {client_data.get('firstName', '')}".strip()
    logger.info(f"✅ Данные отправлены клиенту: {client_name}")
    
    # Уведомление администратору
    api_working, _ = test_vetmanager_connection()
    source_type = "РЕАЛЬНЫЕ ДАННЫЕ" if api_working else "ДЕМО-ДАННЫЕ"
    
    admin_message = f"""
📱 <b>КЛИЕНТ ПОЛУЧИЛ КАРТУ</b>

👤 Клиент: {client_name or 'Не указано'}
📞 Запрос: {phone_input}
🆔 Telegram ID: {chat_id}
📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}

📊 <b>Источник:</b> {source_type}
🐾 Питомцев: {len(client_data.get('pets', []))}
📅 Записей: {len(client_data.get('appointments', []))}
"""
    
    send_telegram_message(ADMIN_ID, admin_message)

# ========== ВЕБ-ИНТЕРФЕЙС ==========
@app.route('/')
def index():
    """Главная страница"""
    api_working, client_count = test_vetmanager_connection()
    
    status_color = "#28a745" if api_working else "#dc3545"
    status_text = "РАБОТАЕТ" if api_working else "НЕДОСТУПЕН"
    status_emoji = "🟢" if api_working else "🔴"
    
    # Примеры тестовых номеров
    test_numbers = [
        "+7(928)319-02-25",
        "+7(962)017-38-24", 
        "+7(916)111-22-33",
        "89161112233"
    ]
    
    test_numbers_html = ""
    for i, number in enumerate(test_numbers, 1):
        test_numbers_html += f'<li><code>{number}</code></li>'
    
    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🏥 Ветеринарная Клиника Друг - Telegram Bot</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
                background: #f8f9fa;
                color: #333;
            }}
            .container {{
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                padding: 30px;
                background: linear-gradient(135deg, #4e73df 0%, #224abe 100%);
                border-radius: 10px;
                color: white;
            }}
            .header h1 {{
                font-size: 2.5em;
                margin-bottom: 10px;
            }}
            .clinic-name {{
                font-size: 1.8em;
                color: #ffc107;
                margin: 10px 0;
            }}
            .status {{
                display: inline-block;
                padding: 12px 24px;
                border-radius: 25px;
                font-weight: bold;
                margin: 15px 0;
                font-size: 1.2em;
                background: {status_color};
                color: white;
            }}
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }}
            .stat-card {{
                background: #f8f9fa;
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                border-top: 4px solid #4e73df;
            }}
            .stat-card h3 {{
                color: #4e73df;
                margin-top: 0;
            }}
            .info-card {{
                background: #e8f4fd;
                border-radius: 10px;
                padding: 25px;
                margin: 25px 0;
                border-left: 5px solid #17a2b8;
            }}
            .test-card {{
                background: #fff3cd;
                border-radius: 10px;
                padding: 25px;
                margin: 25px 0;
                border-left: 5px solid #ffc107;
            }}
            .btn {{
                display: inline-block;
                background: #4e73df;
                color: white;
                padding: 12px 30px;
                border-radius: 25px;
                text-decoration: none;
                font-weight: bold;
                margin: 10px;
                transition: all 0.3s;
            }}
            .btn:hover {{
                background: #2e59d9;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(46, 89, 217, 0.3);
                color: white;
                text-decoration: none;
            }}
            .btn-telegram {{
                background: #0088cc;
            }}
            .btn-telegram:hover {{
                background: #006699;
                box-shadow: 0 5px 15px rgba(0, 102, 153, 0.3);
            }}
            .services-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }}
            .service-item {{
                background: white;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 3px 10px rgba(0,0,0,0.1);
                border: 1px solid #eaeaea;
            }}
            .footer {{
                text-align: center;
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #666;
            }}
            @media (max-width: 768px) {{
                .container {{
                    padding: 15px;
                }}
                .header h1 {{
                    font-size: 2em;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏥 Ветеринарная Клиника Друг</h1>
                <div class="clinic-name">Telegram Бот для клиентов</div>
                <div class="status">
                    {status_emoji} Vetmanager API: {status_text}
                </div>
                <p>Невинномысск | Работаем с 2014 года</p>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>📊 Статус системы</h3>
                    <p><strong>Vetmanager API:</strong> {status_text}</p>
                    <p><strong>Клиентов в базе:</strong> {client_count}</p>
                    <p><strong>Telegram бот:</strong> @Fulsim_bot</p>
                </div>
                
                <div class="stat-card">
                    <h3>📍 Контакты</h3>
                    <p><strong>Адрес:</strong> {CLINIC_INFO['address']}</p>
                    <p><strong>Телефоны:</strong> {CLINIC_INFO['phones'][0]}, {CLINIC_INFO['phones'][1]}</p>
                    <p><strong>Часы работы:</strong> {CLINIC_INFO['working_hours']['mon_fri']}, {CLINIC_INFO['working_hours']['sun']}</p>
                </div>
                
                <div class="stat-card">
                    <h3>🌐 Онлайн-сервисы</h3>
                    <p>✅ Поиск карты клиента</p>
                    <p>✅ Информация о питомцах</p>
                    <p>✅ Просмотр записей</p>
                    <p>✅ Баланс и платежи</p>
                </div>
            </div>
            
            <div class="test-card">
                <h3>🧪 Тестирование системы</h3>
                <p><strong>Примеры номеров для теста:</strong></p>
                <ul>
                    {test_numbers_html}
                </ul>
                <p><strong>Как протестировать:</strong></p>
                <p>1. Откройте Telegram бота @Fulsim_bot</p>
                <p>2. Отправьте команду /start</p>
                <p>3. Введите любой из тестовых номеров</p>
                <p>4. Получите демо-карту клиента</p>
            </div>
            
            <div class="info-card">
                <h3>🔧 Информация о подключении</h3>
                <p><strong>Vetmanager домен:</strong> {VETMANAGER_DOMAIN}</p>
                <p><strong>API ключ:</strong> Настроен (от Вазапы)</p>
                <p><strong>Telegram токен:</strong> Настроен</p>
                <p><strong>Веб-хук:</strong> Настроен на Render</p>
                <p><strong>Последняя проверка:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            </div>
            
            <h3 style="color: #4e73df; margin-top: 30px;">🔬 Услуги клиники</h3>
            <div class="services-grid">
                <div class="service-item">Лабораторные исследования</div>
                <div class="service-item">Вакцинация</div>
                <div class="service-item">Стационар</div>
                <div class="service-item">Хирургия</div>
                <div class="service-item">УЗИ диагностика</div>
                <div class="service-item">Офтальмолог</div>
                <div class="service-item">Дерматолог</div>
                <div class="service-item">Ветеринарная аптека</div>
                <div class="service-item">Аксессуары</div>
            </div>
            
            <div style="text-align: center; margin: 40px 0;">
                <a href="/health" class="btn">Проверить API</a>
                <a href="/test-api" class="btn">Тест подключения</a>
                <a href="https://t.me/Fulsim_bot" class="btn btn-telegram" target="_blank">Открыть Telegram бота</a>
                <a href="{CLINIC_INFO['website']}" class="btn" target="_blank">Сайт клиники</a>
            </div>
            
            <div class="footer">
                <p>© 2025 Ветеринарная Клиника Друг, Невинномысск</p>
                <p>Система работает на Flask + Vetmanager API + Telegram Bot API</p>
                <p>Веб-интерфейс: https://vetmanager-bot-1.onrender.com</p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Проверка здоровья системы"""
    api_working, client_count = test_vetmanager_connection()
    
    return jsonify({
        "status": "healthy" if api_working else "degraded",
        "service": "vetclinic-telegram-bot",
        "clinic": {
            "name": CLINIC_INFO['name'],
            "city": CLINIC_INFO['city'],
            "established": CLINIC_INFO['established']
        },
        "vetmanager_api": {
            "connected": api_working,
            "client_count": client_count,
            "domain": VETMANAGER_DOMAIN
        },
        "telegram_bot": {
            "token_configured": bool(TELEGRAM_TOKEN),
            "bot_username": "Fulsim_bot"
        },
        "timestamp": datetime.now().isoformat(),
        "version": "4.0.0"
    })

@app.route('/test-api')
def test_api():
    """Страница тестирования API"""
    return """
    <html>
    <head>
        <title>🧪 Тест API Vetmanager</title>
        <style>
            body { font-family: Arial; padding: 20px; }
            .test-container { max-width: 800px; margin: 0 auto; }
            .result { padding: 20px; margin: 20px 0; border-radius: 10px; }
            .success { background: #d4edda; border: 1px solid #c3e6cb; }
            .error { background: #f8d7da; border: 1px solid #f5c6cb; }
            .btn { display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 10px; }
        </style>
    </head>
    <body>
        <div class="test-container">
            <h1>🧪 Тестирование подключения к Vetmanager</h1>
            
            <h3>Проверка 1: Прямой запрос к API</h3>
            <div id="api-test-result">Выполняю тест...</div>
            
            <h3>Проверка 2: Тестовые данные</h3>
            <p>Попробуйте эти номера в Telegram боте:</p>
            <ul>
                <li><code>+7(928)319-02-25</code> - Анна Иванова (демо)</li>
                <li><code>+7(962)017-38-24</code> - Сергей Петров (демо)</li>
                <li><code>+7(916)111-22-33</code> - Мария Сидорова (демо)</li>
                <li>Любой другой номер (вернет демо-данные)</li>
            </ul>
            
            <h3>Проверка 3: Веб-интерфейс</h3>
            <p>Статус должен отображаться на главной странице.</p>
            
            <div style="margin-top: 30px;">
                <a href="/" class="btn">На главную</a>
                <a href="/health" class="btn">Проверить здоровье</a>
                <a href="https://t.me/Fulsim_bot" class="btn" target="_blank">Тест в Telegram</a>
            </div>
        </div>
        
        <script>
            // Тестируем API напрямую
            fetch('/health')
                .then(response => response.json())
                .then(data => {
                    const resultDiv = document.getElementById('api-test-result');
                    
                    if (data.vetmanager_api.connected) {
                        resultDiv.className = 'result success';
                        resultDiv.innerHTML = `
                            <h4>✅ API работает!</h4>
                            <p><strong>Статус:</strong> Подключено</p>
                            <p><strong>Клиентов:</strong> ${data.vetmanager_api.client_count}</p>
                            <p><strong>Клиника:</strong> ${data.clinic.name}, ${data.clinic.city}</p>
                        `;
                    } else {
                        resultDiv.className = 'result error';
                        resultDiv.innerHTML = `
                            <h4>❌ API не доступен</h4>
                            <p><strong>Статус:</strong> Не подключено</p>
                            <p><strong>Причина:</strong> Нет соединения с Vetmanager</p>
                            <p><strong>Рекомендация:</strong> Проверьте API ключ и настройки доступа</p>
                        `;
                    }
                })
                .catch(error => {
                    const resultDiv = document.getElementById('api-test-result');
                    resultDiv.className = 'result error';
                    resultDiv.innerHTML = `
                        <h4>❌ Ошибка тестирования</h4>
                        <p><strong>Ошибка:</strong> ${error.message}</p>
                        <p>Проверьте консоль браузера для подробностей</p>
                    `;
                    console.error('Test error:', error);
                });
        </script>
    </body>
    </html>
    """

# ========== ЗАПУСК ==========
def setup_telegram_webhook():
    """Настройка вебхука для Telegram"""
    webhook_url = f"https://vetmanager-bot-1.onrender.com/webhook"
    
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
            params={"url": webhook_url}
        )
        
        result = response.json()
        if result.get("ok"):
            logger.info(f"✅ Webhook настроен: {webhook_url}")
        else:
            logger.error(f"❌ Ошибка webhook: {result}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка настройки webhook: {e}")

if __name__ == '__main__':
    logger.info("🚀 Запуск бота для Ветеринарной Клиники Друг...")
    
    # Тестируем подключение
    api_working, client_count = test_vetmanager_connection()
    
    # Настраиваем вебхук
    setup_telegram_webhook()
    
    # Отправляем сообщение о запуске
    startup_message = f"""
🚀 <b>БОТ ЗАПУЩЕН ДЛЯ КЛИНИКИ "ДРУГ"</b>

🏥 <b>Клиника:</b> {CLINIC_INFO['name']}
📍 <b>Адрес:</b> {CLINIC_INFO['address']}
🏙️ <b>Город:</b> {CLINIC_INFO['city']}
📅 <b>Работаем с:</b> {CLINIC_INFO['established']} года

🔗 <b>Telegram бот:</b> @Fulsim_bot
🌐 <b>Веб-интерфейс:</b> https://vetmanager-bot-1.onrender.com

📊 <b>СТАТУС СИСТЕМЫ:</b>
Vetmanager API: {'🟢 ПОДКЛЮЧЕН' if api_working else '🔴 НЕДОСТУПЕН'}
Клиентов в базе: {client_count}

📞 <b>Телефоны клиники:</b>
{CLINIC_INFO['phones'][0]}
{CLINIC_INFO['phones'][1]}

⏰ <b>Часы работы:</b>
{CLINIC_INFO['working_hours']['mon_fri']}
{CLINIC_INFO['working_hours']['sun']}

✅ <b>Система готова к работе!</b>
Пользователи могут получать информацию о своих картах клиентов.

🐾 <b>Для теста используйте команды:</b>
/start - начать поиск
/clinic - информация о клинике
/services - услуги клиники

Или просто отправьте номер телефона.
"""
    
    send_telegram_message(ADMIN_ID, startup_message)
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
