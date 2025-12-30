import os
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import logging
import re
import json

app = Flask(__name__)

# ========== КОНФИГУРАЦИЯ ==========
TELEGRAM_TOKEN = '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI'
VETMANAGER_KEY = '487bc6-4a39ee-be14b6-1ef17a-be257f'  # ПРАВИЛЬНЫЙ КЛЮЧ ОТ ВАЗАПЫ
VETMANAGER_DOMAIN = 'drug14.vetmanager2.ru'
VETMANAGER_URL = f'https://{VETMANAGER_DOMAIN}'
ADMIN_ID = 921853682

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
    
    logger.info(f"🔄 Запрос к API: {endpoint}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=15)
        else:
            response = requests.post(url, headers=headers, json=params, timeout=15)
        
        logger.info(f"📊 Ответ API: {response.status_code}")
        
        if response.status_code == 401:
            logger.error("❌ Ошибка 401: Неверный API ключ или нет прав доступа")
            return None
        elif response.status_code == 403:
            logger.error("❌ Ошибка 403: Доступ запрещен")
            return None
        
        response.raise_for_status()
        
        # Пытаемся распарсить JSON
        try:
            data = response.json()
            logger.info(f"✅ Успешный запрос к {endpoint}")
            return data
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON: {e}")
            logger.error(f"Ответ: {response.text[:500]}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ошибка запроса: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка: {e}")
        return None

def test_vetmanager_connection():
    """Тестирует подключение к Vetmanager"""
    logger.info("🔌 Тестирую подключение к Vetmanager с новым ключом...")
    
    # Тест 1: Проверяем базовое соединение
    try:
        test_response = requests.get(VETMANAGER_URL, timeout=10)
        logger.info(f"🌐 Сайт доступен: {test_response.status_code}")
    except Exception as e:
        logger.error(f"🌐 Сайт недоступен: {e}")
        return False, 0
    
    # Тест 2: Пробуем получить список клиник (обычно этот endpoint всегда доступен)
    result = make_vetmanager_request('clinics')
    
    if result and 'data' in result:
        clinics = result['data']
        logger.info(f"✅ Подключение к API успешно! Клиник найдено: {len(clinics)}")
        
        # Тест 3: Пробуем получить клиентов
        clients_result = make_vetmanager_request('clients', {'limit': 1})
        
        if clients_result and 'data' in clients_result:
            client_count = len(clients_result['data'])
            
            # Пробуем получить больше клиентов для точного подсчета
            all_clients_result = make_vetmanager_request('clients', {'limit': 50})
            if all_clients_result and 'data' in all_clients_result:
                client_count = len(all_clients_result['data'])
            
            logger.info(f"✅ Клиенты доступны! Найдено: {client_count}")
            
            # Логируем первого клиента для отладки
            if clients_result['data']:
                client = clients_result['data'][0]
                logger.info(f"📋 Пример клиента: ID={client.get('id')}, Имя={client.get('firstName')}, Телефон={client.get('phone')}")
            
            return True, client_count
        else:
            logger.warning("⚠️ Клиенты не найдены, но API отвечает")
            return True, 0
    
    logger.error("❌ Не удалось подключиться к Vetmanager API")
    return False, 0

def find_client_by_phone(phone_number):
    """Ищет клиента по номеру телефона"""
    # Очищаем номер
    phone_clean = re.sub(r'\D', '', str(phone_number))
    logger.info(f"🔍 Поиск клиента по номеру: {phone_number} (очищенный: {phone_clean})")
    
    # Пробуем разные варианты поиска
    search_patterns = []
    
    if len(phone_clean) == 11:
        if phone_clean.startswith('7'):
            search_patterns = [
                phone_clean,  # 79996925927
                phone_clean[1:],  # 9996925927
                f"8{phone_clean[1:]}",  # 89996925927
                f"+7 ({phone_clean[1:4]}) {phone_clean[4:7]}-{phone_clean[7:9]}-{phone_clean[9:]}",  # +7 (999) 692-59-27
                f"7 ({phone_clean[1:4]}) {phone_clean[4:7]}-{phone_clean[7:9]}-{phone_clean[9:]}"  # 7 (999) 692-59-27
            ]
        elif phone_clean.startswith('8'):
            search_patterns = [
                phone_clean,  # 89996925927
                f"7{phone_clean[1:]}",  # 79996925927
                phone_clean[1:],  # 9996925927
                f"+7 ({phone_clean[1:4]}) {phone_clean[4:7]}-{phone_clean[7:9]}-{phone_clean[9:]}"  # +7 (999) 692-59-27
            ]
    elif len(phone_clean) == 10:
        search_patterns = [
            f"7{phone_clean}",  # 79996925927
            f"8{phone_clean}",  # 89996925927
            phone_clean,  # 9996925927
            f"+7 ({phone_clean[0:3]}) {phone_clean[3:6]}-{phone_clean[6:8]}-{phone_clean[8:]}",  # +7 (999) 692-59-27
            f"8 ({phone_clean[0:3]}) {phone_clean[3:6]}-{phone_clean[6:8]}-{phone_clean[8:]}"  # 8 (999) 692-59-27
        ]
    
    logger.info(f"🔎 Варианты поиска: {search_patterns}")
    
    # Ищем по всем вариантам
    for pattern in search_patterns:
        if not pattern:
            continue
            
        params = {
            'filter[phone]': pattern,
            'limit': 1
        }
        
        logger.info(f"🔎 Пробую найти по паттерну: {pattern}")
        result = make_vetmanager_request('clients', params)
        
        if result and 'data' in result and result['data']:
            client_data = result['data'][0]
            client_id = client_data.get('id')
            logger.info(f"✅ Найден клиент ID: {client_id}, Имя: {client_data.get('firstName')}")
            
            # Получаем полную информацию
            full_info = get_full_client_info(client_id)
            if full_info:
                client_data.update(full_info)
            
            return client_data
    
    logger.warning(f"❌ Клиент не найден по номеру: {phone_number}")
    return None

def get_full_client_info(client_id):
    """Получает полную информацию о клиенте и его питомцах"""
    logger.info(f"📋 Получаю полную информацию для клиента ID: {client_id}")
    client_info = {}
    
    try:
        # 1. Детальная информация о клиенте
        result = make_vetmanager_request(f'client/{client_id}')
        if result and 'data' in result:
            client_info.update(result['data'])
            logger.info(f"✅ Получены данные клиента: {client_info.get('firstName')}")
        
        # 2. Питомцы клиента
        pets_result = make_vetmanager_request('pets', {
            'filter[client_id]': client_id,
            'limit': 10
        })
        
        if pets_result and 'data' in pets_result:
            client_info['pets'] = pets_result['data']
            logger.info(f"✅ Получены питомцы: {len(client_info['pets'])} шт.")
        
        # 3. Записи на прием (будущие)
        today = datetime.now().strftime('%Y-%m-%d')
        future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        
        appointments_result = make_vetmanager_request('appointments', {
            'filter[client_id]': client_id,
            'filter[date_from]': today,
            'filter[date_to]': future_date,
            'sort': 'date',
            'limit': 5
        })
        
        if appointments_result and 'data' in appointments_result:
            client_info['appointments'] = appointments_result['data']
            logger.info(f"✅ Получены записи: {len(client_info['appointments'])} шт.")
        
        # 4. Баланс клиента
        finance_result = make_vetmanager_request('invoice', {
            'filter[client_id]': client_id,
            'limit': 10
        })
        
        if finance_result and 'data' in finance_result:
            invoices = finance_result['data']
            balance = 0
            
            for invoice in invoices:
                status = invoice.get('status', '')
                amount = float(invoice.get('amount', 0))
                
                if status == 'UNPAID':
                    balance += amount
            
            client_info['balance'] = balance
            logger.info(f"✅ Рассчитан баланс: {balance} руб.")
        
        # 5. Последние визиты
        visits_result = make_vetmanager_request('admission', {
            'filter[client_id]': client_id,
            'sort': '-id',
            'limit': 3
        })
        
        if visits_result and 'data' in visits_result:
            client_info['last_visits'] = visits_result['data']
            logger.info(f"✅ Получены визиты: {len(client_info['last_visits'])} шт.")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении полной информации: {e}")
    
    return client_info

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
    if not client_data:
        return "❌ Информация о клиенте не найдена"
    
    lines = []
    
    # Определяем источник данных
    source = client_data.get('source', 'api')
    if source == 'api':
        lines.append("✅ <b>ВАША КАРТА КЛИЕНТА (РЕАЛЬНЫЕ ДАННЫЕ)</b>")
    else:
        lines.append("⚠️ <b>ВАША КАРТА КЛИЕНТА (ТЕСТОВЫЕ ДАННЫЕ)</b>")
    
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
    if balance:
        lines.append(f"💰 <b>Баланс:</b> {balance:.2f} руб.")
    
    # Дата рождения
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
        
        for i, pet in enumerate(pets[:5], 1):
            pet_name = pet.get('alias', 'Без имени')
            pet_type = pet.get('type_title', pet.get('type', ''))
            breed = pet.get('breed_title', pet.get('breed', ''))
            birth_date = pet.get('birthday', '')
            
            pet_line = f"{i}. <b>{pet_name}</b>"
            
            if pet_type or breed or birth_date:
                pet_line += " ("
                details = []
                if pet_type:
                    details.append(pet_type)
                if breed:
                    details.append(breed)
                if birth_date:
                    try:
                        birth_obj = datetime.strptime(birth_date, '%Y-%m-%d')
                        age_years = (datetime.now() - birth_obj).days // 365
                        details.append(f"{age_years} лет")
                    except:
                        pass
                
                pet_line += ", ".join(details) + ")"
            
            lines.append(pet_line)
        
        if len(pets) > 5:
            lines.append(f"... и ещё {len(pets) - 5} питомцев")
    else:
        lines.append("🐾 <b>Питомцы:</b> нет")
    
    lines.append("")
    
    # Записи на прием
    appointments = client_data.get('appointments', [])
    if appointments:
        lines.append("📅 <b>БЛИЖАЙШИЕ ЗАПИСИ:</b>")
        
        for i, app in enumerate(appointments[:3], 1):
            date = app.get('date', '')
            time = app.get('time', '10:00')
            
            # Форматируем дату
            try:
                date_obj = datetime.strptime(date, '%Y-%m-%d')
                date_str = date_obj.strftime('%d.%m.%Y')
                
                # Определяем день недели
                weekday = date_obj.strftime('%A')
                weekday_ru = {
                    'Monday': 'Пн',
                    'Tuesday': 'Вт',
                    'Wednesday': 'Ср',
                    'Thursday': 'Чт',
                    'Friday': 'Пт',
                    'Saturday': 'Сб',
                    'Sunday': 'Вс'
                }.get(weekday, weekday)
                
                date_display = f"{date_str} ({weekday_ru})"
            except:
                date_display = date
            
            lines.append(f"{i}. {date_display} в {time}")
    else:
        lines.append("📅 <b>Ближайшие записи:</b> нет")
    
    # Контакты клиники
    lines.append("")
    lines.append("══════════════════════════════════")
    lines.append("🏥 <b>ВЕТКЛИНИКА</b>")
    lines.append("📍 <b>Адрес:</b> г. Ростов-на-Дону")
    lines.append("📞 <b>Телефон:</b> +7 (XXX) XXX-XX-XX")
    lines.append("⏰ <b>Часы работы:</b> Пн-Пт 9:00-20:00, Сб-Вс 10:00-18:00")
    
    if source == 'api':
        lines.append("")
        lines.append("✅ <i>Данные загружены из системы Vetmanager</i>")
    else:
        lines.append("")
        lines.append("⚠️ <i>Используются тестовые данные (реальный API временно недоступен)</i>")
    
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
            
            logger.info(f"📨 Получено сообщение от {chat_id}: {text}")
            
            if text == '/start':
                handle_start_command(chat_id)
            elif text == '/test':
                # Команда для тестирования API
                api_working, client_count = test_vetmanager_connection()
                if api_working:
                    send_telegram_message(chat_id, f"✅ API работает! Клиентов в базе: {client_count}")
                else:
                    send_telegram_message(chat_id, "❌ API не доступен")
            elif chat_id in user_sessions and user_sessions[chat_id].get('awaiting_phone'):
                handle_phone_input(chat_id, text)
            else:
                # Если пользователь просто отправляет текст, предполагаем, что это номер телефона
                if re.search(r'\d', text) and len(text) >= 5:
                    handle_phone_input(chat_id, text)
                else:
                    send_telegram_message(
                        chat_id,
                        "🤔 <b>Я не понял ваш запрос</b>\n\n"
                        "Чтобы найти свою карту клиента, отправьте мне номер телефона, "
                        "указанный в вашей карте.\n\n"
                        "Или используйте команду /start"
                    )
        
        return jsonify({"status": "ok"})
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)})

def handle_start_command(chat_id):
    """Обработка команды /start"""
    # Тестируем подключение к Vetmanager
    api_working, client_count = test_vetmanager_connection()
    
    if api_working:
        welcome_text = f"""🎉 <b>ДОБРО ПОЖАЛОВАТЬ В VETCLINIC!</b>

✅ <b>Система подключена к реальной базе данных Vetmanager</b>
📊 Клиентов в системе: {client_count}

<b>📱 КАК ПОЛЬЗОВАТЬСЯ:</b>

1️⃣ <b>Введите номер телефона</b>, указанный в вашей карте
2️⃣ <b>Получите полную информацию</b> о себе и питомцах
3️⃣ <b>Узнайте о ближайших записях</b> на прием

<b>👇 ВВЕДИТЕ ВАШ НОМЕР ТЕЛЕФОНА:</b>

💡 <i>Пример правильного формата:</i>
<code>+7(999)692-59-27</code>
<code>89996925927</code>
<code>9996925927</code>

<i>Попробуйте ввести свой номер для получения реальных данных!</i>"""
    else:
        welcome_text = """⚠️ <b>СИСТЕМА В РЕЖИМЕ ОБСЛУЖИВАНИЯ</b>

В настоящее время подключение к базе данных временно недоступна.

📱 <b>Для получения информации:</b>
Обратитесь на ресепшн клиники.

📍 <b>Клиника:</b> VetClinic
📞 <b>Телефон:</b> +7 (XXX) XXX-XX-XX
⏰ <b>Часы работы:</b> Пн-Пт 9:00-20:00

<i>Вы всё равно можете ввести номер телефона для теста:</i>"""
    
    send_telegram_message(chat_id, welcome_text)
    
    if api_working:
        user_sessions[chat_id] = {'awaiting_phone': True}
        logger.info(f"Пользователь {chat_id} начал поиск. API работает: {api_working}")

def handle_phone_input(chat_id, phone_input):
    """Обработка введенного номера телефона"""
    # Сбрасываем сессию
    user_sessions.pop(chat_id, None)
    
    logger.info(f"Пользователь {chat_id} ищет по номеру: {phone_input}")
    
    # Сообщение о поиске
    send_telegram_message(chat_id, "🔍 <b>Ищу вашу карту в базе данных...</b>")
    
    # Ищем клиента
    client_data = find_client_by_phone(phone_input)
    
    if not client_data:
        # Проверяем подключение к API
        api_working, _ = test_vetmanager_connection()
        
        if not api_working:
            error_text = """❌ <b>База данных временно недоступна</b>

Не удалось подключиться к системе Vetmanager.

📱 <b>Что делать:</b>
1. Попробуйте повторить попытку позже
2. Обратитесь на ресепшн клиники для получения информации

📍 <b>Контакты клиники:</b>
Телефон: +7 (XXX) XXX-XX-XX
Адрес: г. Ростов-на-Дону

Или начните заново: /start"""
        else:
            error_text = f"""❌ <b>Клиент не найден</b>

По номеру <code>{phone_input}</code> не найдено карт в базе данных.

<b>Возможные причины:</b>
• Номер введен неправильно
• Вы не зарегистрированы в нашей клинике
• Ваш номер указан в другом формате

<b>Попробуйте:</b>
• Ввести номер в другом формате
• Обратиться на ресепшн для уточнения данных

<b>Примеры правильных форматов:</b>
• <code>+7(999)692-59-27</code>
• <code>89996925927</code>
• <code>9996925927</code>

Или начните заново: /start"""
        
        send_telegram_message(chat_id, error_text)
        return
    
    # Форматируем и отправляем информацию
    client_info = format_client_info(client_data)
    send_telegram_message(chat_id, client_info)
    
    # Логируем успешный поиск
    client_name = f"{client_data.get('lastName', '')} {client_data.get('firstName', '')}".strip()
    phone = client_data.get('phone', phone_input)
    pet_count = len(client_data.get('pets', []))
    appointment_count = len(client_data.get('appointments', []))
    
    logger.info(f"✅ Данные отправлены клиенту: {client_name}, питомцев: {pet_count}, записей: {appointment_count}")
    
    # Уведомление администратору
    admin_message = f"""📱 <b>КЛИЕНТ ПОЛУЧИЛ КАРТУ</b>

👤 Клиент: {client_name or 'Не указано'}
📞 Телефон: {phone}
🆔 Telegram ID: {chat_id}
📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}

✅ Данные загружены из Vetmanager
🐾 Питомцев: {pet_count}
📅 Записей: {appointment_count}"""

    send_telegram_message(ADMIN_ID, admin_message)

# ========== ВЕБ-ИНТЕРФЕЙС ==========
@app.route('/')
def index():
    """Главная страница"""
    api_working, client_count = test_vetmanager_connection()
    
    status_color = "green" if api_working else "red"
    status_text = "РАБОТАЕТ" if api_working else "НЕДОСТУПЕН"
    status_emoji = "🟢" if api_working else "🔴"
    
    # Получаем информацию о первом клиенте для демонстрации
    demo_info = ""
    if api_working:
        result = make_vetmanager_request('clients', {'limit': 1})
        if result and 'data' in result and result['data']:
            client = result['data'][0]
            demo_info = f"""
            <div class="demo-info">
                <h4>📋 Пример клиента из базы:</h4>
                <p><strong>ID:</strong> {client.get('id', 'N/A')}</p>
                <p><strong>Имя:</strong> {client.get('firstName', 'N/A')} {client.get('lastName', 'N/A')}</p>
                <p><strong>Телефон:</strong> {client.get('phone', 'N/A')}</p>
            </div>
            """
    
    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🏥 VetClinic Telegram Bot</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
            }}
            .container {{
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 10px;
                color: white;
            }}
            .header h1 {{
                font-size: 2.5em;
                margin-bottom: 10px;
            }}
            .status {{
                display: inline-block;
                padding: 10px 20px;
                border-radius: 25px;
                font-weight: bold;
                margin: 10px 0;
                font-size: 1.2em;
            }}
            .status-working {{
                background: #d4edda;
                color: #155724;
                border: 3px solid #28a745;
            }}
            .status-error {{
                background: #f8d7da;
                color: #721c24;
                border: 3px solid #dc3545;
            }}
            .card {{
                background: #f8f9fa;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
                border-left: 5px solid #667eea;
            }}
            .card h3 {{
                color: #2c3e50;
                margin-top: 0;
            }}
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }}
            .feature {{
                background: white;
                border-radius: 10px;
                padding: 20px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.05);
                text-align: center;
                transition: transform 0.3s;
            }}
            .feature:hover {{
                transform: translateY(-5px);
            }}
            .feature h4 {{
                color: #667eea;
                margin: 15px 0;
            }}
            .btn {{
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 12px 30px;
                border-radius: 25px;
                text-decoration: none;
                font-weight: bold;
                margin: 10px;
                transition: transform 0.3s, box-shadow 0.3s;
            }}
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
                color: white;
                text-decoration: none;
            }}
            .btn-test {{
                background: #28a745;
            }}
            .btn-test:hover {{
                box-shadow: 0 10px 20px rgba(40, 167, 69, 0.3);
            }}
            .api-info {{
                background: #e3f2fd;
                border-radius: 10px;
                padding: 20px;
                margin: 20px 0;
                font-family: monospace;
                overflow-x: auto;
            }}
            .demo-info {{
                background: #d1ecf1;
                border-radius: 10px;
                padding: 15px;
                margin: 15px 0;
                border-left: 5px solid #17a2b8;
            }}
            .footer {{
                text-align: center;
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #666;
            }}
            .instructions {{
                background: #fff3cd;
                border-left: 5px solid #ffc107;
                padding: 15px;
                border-radius: 5px;
                margin: 20px 0;
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
                <h1>🏥 VetClinic Telegram Bot</h1>
                <p>Система получения информации из карт клиентов Vetmanager</p>
                <div class="status {'status-working' if api_working else 'status-error'}">
                    {status_emoji} Vetmanager API: {status_text}
                </div>
            </div>
            
            <div class="card">
                <h3>📊 Статистика системы</h3>
                <p><strong>Статус подключения:</strong> {status_emoji} {status_text}</p>
                <p><strong>Клиентов в базе:</strong> {client_count}</p>
                <p><strong>Telegram бот:</strong> @Fulsim_bot</p>
                <p><strong>API ключ:</strong> Обновлён (от Вазапы)</p>
                <p><strong>Последняя проверка:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            </div>
            
            {demo_info}
            
            <div class="instructions">
                <h4>🚀 Как начать пользоваться:</h4>
                <p>1. Откройте Telegram и найдите бота <strong>@Fulsim_bot</strong></p>
                <p>2. Отправьте команду <code>/start</code></p>
                <p>3. Введите номер телефона, указанный в вашей карте клиента</p>
                <p>4. Получите полную информацию о себе и своих питомцах</p>
            </div>
            
            <div class="grid">
                <div class="feature">
                    <h4>👤 Реальный поиск</h4>
                    <p>Подключение к реальной базе Vetmanager</p>
                </div>
                
                <div class="feature">
                    <h4>🐾 Питомцы клиента</h4>
                    <p>Полный список животных с детальной информацией</p>
                </div>
                
                <div class="feature">
                    <h4>📅 Управление записями</h4>
                    <p>Просмотр ближайших визитов к врачу</p>
                </div>
                
                <div class="feature">
                    <h4>💰 Финансы</h4>
                    <p>Информация о балансе и платежах</p>
                </div>
            </div>
            
            <div class="card">
                <h3>🔗 Полезные ссылки</h3>
                <p>
                    <a href="/health" class="btn">Проверить API</a>
                    <a href="/test-api" class="btn btn-test">Тест подключения</a>
                    <a href="https://t.me/Fulsim_bot" class="btn" target="_blank">Открыть бота</a>
                </p>
            </div>
            
            <div class="api-info">
                <h4>🔧 Информация о подключении</h4>
                <p><strong>Vetmanager домен:</strong> {VETMANAGER_DOMAIN}</p>
                <p><strong>API URL:</strong> {VETMANAGER_URL}/api/</p>
                <p><strong>API ключ:</strong> Обновлён и проверен</p>
                <p><strong>Telegram токен:</strong> Настроен</p>
            </div>
            
            <div class="footer">
                <p>© 2025 VetClinic. Все права защищены.</p>
                <p>Система работает на Flask + Vetmanager API + Telegram Bot</p>
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
        "vetmanager_api": {
            "connected": api_working,
            "client_count": client_count,
            "domain": VETMANAGER_DOMAIN,
            "api_key": "configured"
        },
        "telegram_bot": {
            "token_set": bool(TELEGRAM_TOKEN),
            "webhook_configured": True
        },
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0"
    })

@app.route('/test-api')
def test_api():
    """Страница тестирования API"""
    api_working, client_count = test_vetmanager_connection()
    
    if api_working:
        # Получаем несколько клиентов для демонстрации
        result = make_vetmanager_request('clients', {'limit': 3})
        clients_html = ""
        
        if result and 'data' in result:
            clients = result['data']
            for client in clients:
                clients_html += f"""
                <div style="background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 5px;">
                    <p><strong>ID:</strong> {client.get('id')}</p>
                    <p><strong>Имя:</strong> {client.get('firstName')} {client.get('lastName')}</p>
                    <p><strong>Телефон:</strong> {client.get('phone')}</p>
                    <p><strong>Email:</strong> {client.get('email', 'не указан')}</p>
                </div>
                """
        
        html = f"""
        <html>
        <head>
            <title>✅ API Test</title>
            <style>
                body {{ font-family: Arial; padding: 20px; }}
                .success {{ background: #d4edda; padding: 20px; border-radius: 10px; }}
            </style>
        </head>
        <body>
            <div class="success">
                <h1>✅ Vetmanager API работает!</h1>
                <p><strong>Клиентов в базе:</strong> {client_count}</p>
                <p><strong>Примеры клиентов:</strong></p>
                {clients_html}
            </div>
            <p style="margin-top: 20px;">
                <a href="/">На главную</a> | 
                <a href="/health">Проверить здоровье системы</a>
            </p>
        </body>
        </html>
        """
    else:
        html = """
        <html>
        <head>
            <title>❌ API Test</title>
            <style>
                body { font-family: Arial; padding: 20px; }
                .error { background: #f8d7da; padding: 20px; border-radius: 10px; }
            </style>
        </head>
        <body>
            <div class="error">
                <h1>❌ Vetmanager API недоступен</h1>
                <p>Проверьте:</p>
                <ul>
                    <li>API ключ в настройках бота</li>
                    <li>Доступ к домену: drug14.vetmanager2.ru</li>
                    <li>Настройки API в Vetmanager</li>
                    <li>Белый список IP адресов (если используется)</li>
                </ul>
            </div>
            <p style="margin-top: 20px;">
                <a href="/">На главную</a> | 
                <a href="/health">Проверить здоровье системы</a>
            </p>
        </body>
        </html>
        """
    
    return html

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
            logger.error(f"❌ Ошибка настройки webhook: {result}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при настройке webhook: {e}")

if __name__ == '__main__':
    logger.info("🚀 Запуск VetClinic Telegram Bot с НОВЫМ API ключом...")
    
    # Тестируем подключение с новым ключом
    logger.info(f"🔑 Использую новый API ключ: {VETMANAGER_KEY[:10]}...")
    api_working, client_count = test_vetmanager_connection()
    
    # Настраиваем вебхук
    setup_telegram_webhook()
    
    # Отправляем сообщение о запуске администратору
    startup_message = f"""🚀 <b>VETCLINIC БОТ ЗАПУЩЕН С НОВЫМ КЛЮЧОМ</b>

✅ API ключ обновлён (от Вазапы)
🏥 Клиника: VetClinic  
🔗 Бот: @Fulsim_bot
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

<b>СТАТУС VETMANAGER:</b> {'🟢 ПОДКЛЮЧЕН' if api_working else '🔴 НЕДОСТУПЕН'}
<b>КЛИЕНТОВ В БАЗЕ:</b> {client_count}

<b>Используемый API ключ:</b>
487bc6-4a39ee-be14b6-1ef17a-be257f

<b>Веб-интерфейс:</b> https://vetmanager-bot-1.onrender.com

Готов к работе! 🐾"""
    
    send_telegram_message(ADMIN_ID, startup_message)
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
