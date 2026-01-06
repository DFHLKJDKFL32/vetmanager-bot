from flask import Flask, request
import requests
from datetime import datetime, timedelta
import json
import sqlite3
import threading
import time
import os

app = Flask(__name__)

# ============ ТВОИ КЛЮЧИ ============
TELEGRAM_TOKEN = "8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI"
VETMANAGER_KEY = "29607ccc63c684fa672be9694f7f09ec"
ADMIN_ID = "921853682"

# ============ 1. БАЗА ДАННЫХ ============
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('vetmanager.db')
    cursor = conn.cursor()
    
    # Таблица клиентов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY,
            vetmanager_id INTEGER,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            telegram_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица записей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY,
            vetmanager_id INTEGER,
            client_id INTEGER,
            appointment_date TEXT,
            appointment_time TEXT,
            doctor_name TEXT,
            pet_name TEXT,
            description TEXT,
            status TEXT DEFAULT 'pending', -- pending, confirmed, cancelled, noshow
            reminder_sent BOOLEAN DEFAULT 0,
            confirmation_sent BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')
    
    # Таблица логов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY,
            action TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def log_action(action, details=""):
    """Логирование действий"""
    conn = sqlite3.connect('vetmanager.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO logs (action, details) VALUES (?, ?)', (action, details))
    conn.commit()
    conn.close()

# ============ 2. ПОЛУЧЕНИЕ РЕАЛЬНЫХ ДАННЫХ ИЗ VETMANAGER ============
def fetch_real_appointments():
    """Получение реальных записей из VetManager"""
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    try:
        # Пробуем разные лимиты
        for limit in [50, 100, 200]:
            params = {"limit": limit}
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success"):
                    appointments = data.get("data", {}).get("admission", [])
                    print(f"✅ Получено {len(appointments)} записей (limit={limit})")
                    log_action("FETCH_APPOINTMENTS", f"Получено {len(appointments)} записей")
                    return appointments
                else:
                    error = data.get('error', {}).get('message', 'Unknown')
                    print(f"❌ VetManager API error: {error}")
                    log_action("API_ERROR", error)
            else:
                print(f"❌ HTTP error: {response.status_code}")
                log_action("HTTP_ERROR", str(response.status_code))
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        log_action("CONNECTION_ERROR", str(e))
    
    return []

def process_and_store_appointments():
    """Обработка и сохранение записей в базу"""
    appointments = fetch_real_appointments()
    
    if not appointments:
        return []
    
    conn = sqlite3.connect('vetmanager.db')
    cursor = conn.cursor()
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_appointments = []
    
    for app in appointments:
        admission_date = app.get("admission_date", "")
        
        # Проверяем, что запись на завтра
        if not admission_date.startswith(tomorrow):
            continue
        
        # Извлекаем данные
        vetmanager_id = app.get("id")
        client_data = app.get("client", {})
        pet_data = app.get("pet", {})
        doctor_data = app.get("user", {})
        
        # Время записи
        if " " in admission_date:
            date_part, time_part = admission_date.split(" ")
            appointment_time = time_part[:5]
        else:
            appointment_time = "??:??"
        
        # Данные клиента
        first_name = client_data.get("first_name", "").strip()
        last_name = client_data.get("last_name", "").strip()
        phone = client_data.get("cell_phone", client_data.get("phone", "")).strip()
        
        # Данные питомца
        pet_name = pet_data.get("alias", pet_data.get("pet_name", "питомец")).strip()
        
        # Врач
        doctor_name = doctor_data.get("last_name", doctor_data.get("login", "Врач")).strip()
        
        # Описание
        description = app.get("description", "").strip()
        
        # Сохраняем клиента
        cursor.execute('''
            INSERT OR IGNORE INTO clients 
            (vetmanager_id, first_name, last_name, phone) 
            VALUES (?, ?, ?, ?)
        ''', (vetmanager_id, first_name, last_name, phone))
        
        # Получаем ID клиента
        cursor.execute('SELECT id FROM clients WHERE vetmanager_id = ?', (vetmanager_id,))
        client_row = cursor.fetchone()
        client_id = client_row[0] if client_row else None
        
        # Сохраняем запись
        cursor.execute('''
            INSERT OR REPLACE INTO appointments 
            (vetmanager_id, client_id, appointment_date, appointment_time, 
             doctor_name, pet_name, description, status) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (vetmanager_id, client_id, tomorrow, appointment_time, 
              doctor_name, pet_name, description, 'pending'))
        
        tomorrow_appointments.append({
            'id': vetmanager_id,
            'client_name': f"{first_name} {last_name}".strip() or f"Клиент {vetmanager_id}",
            'phone': phone,
            'time': appointment_time,
            'doctor': doctor_name,
            'pet': pet_name,
            'description': description
        })
    
    conn.commit()
    conn.close()
    
    print(f"📊 Сохранено {len(tomorrow_appointments)} записей на завтра")
    log_action("STORE_APPOINTMENTS", f"Сохранено {len(tomorrow_appointments)} записей")
    
    return tomorrow_appointments

# ============ 3. TELEGRAM ФУНКЦИИ ============
def send_telegram(chat_id, message, reply_markup=None):
    """Отправка сообщения в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    if reply_markup:
        data["reply_markup"] = reply_markup
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Telegram send error: {e}")
        return False

def format_appointment_message(appointment, index, for_admin=True):
    """Форматирование сообщения о записи"""
    if for_admin:
        message = f"📋 <b>Запись #{index}</b>\n"
        message += f"👤 <b>Клиент:</b> {appointment['client_name']}\n"
        message += f"📞 <b>Телефон:</b> {appointment['phone'] or 'Не указан'}\n"
        message += f"🕒 <b>Время:</b> {appointment['time']}\n"
        message += f"👨‍⚕️ <b>Врач:</b> {appointment['doctor']}\n"
        message += f"🐾 <b>Питомец:</b> {appointment['pet']}\n"
        
        if appointment['description']:
            desc = appointment['description'][:100] + "..." if len(appointment['description']) > 100 else appointment['description']
            message += f"📝 <b>Комментарий:</b> {desc}\n"
        
        message += f"\n<b>Статус:</b> ⏳ Ожидает подтверждения"
    else:
        # Для клиента
        message = f"🐾 <b>Напоминание о визите в ветеринарную клинику</b>\n\n"
        message += f"📅 <b>Дата:</b> {(datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')}\n"
        message += f"🕒 <b>Время:</b> {appointment['time']}\n"
        message += f"👨‍⚕️ <b>Врач:</b> {appointment['doctor']}\n"
        message += f"🐶 <b>Питомец:</b> {appointment['pet']}\n"
        
        message += f"\n<i>Пожалуйста, подтвердите визит:</i>"
    
    return message

def get_admin_buttons(appointment_id):
    """Кнопки для администратора"""
    return {
        "inline_keyboard": [
            [
                {"text": "📞 Позвонить", "callback_data": f"call_{appointment_id}"},
                {"text": "✅ Подтвердить", "callback_data": f"confirm_{appointment_id}"}
            ],
            [
                {"text": "❌ Отменить", "callback_data": f"cancel_{appointment_id}"},
                {"text": "📝 Заметка", "callback_data": f"note_{appointment_id}"}
            ]
        ]
    }

def get_client_buttons(appointment_id):
    """Кнопки для клиента"""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Да, приду", "callback_data": f"client_yes_{appointment_id}"},
                {"text": "❌ Не смогу", "callback_data": f"client_no_{appointment_id}"}
            ],
            [
                {"text": "📞 Связаться", "callback_data": f"client_call_{appointment_id}"},
                {"text": "🕐 Перенести", "callback_data": f"client_reschedule_{appointment_id}"}
            ]
        ]
    }

# ============ 4. ОСНОВНЫЕ ФУНКЦИИ ============
def send_daily_report_to_admin():
    """Ежедневный отчет администратору"""
    # Получаем и сохраняем записи
    appointments = process_and_store_appointments()
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    if not appointments:
        send_telegram(ADMIN_ID, f"📭 На завтра ({tomorrow}) нет записей")
        return "📭 Нет записей"
    
    # Общая сводка
    summary = f"📅 <b>ЕЖЕДНЕВНЫЙ ОТЧЕТ - {tomorrow}</b>\n\n"
    summary += f"<i>Всего записей на завтра: {len(appointments)}</i>\n\n"
    
    # Группируем по врачам
    doctors = {}
    for app in appointments:
        doctor = app['doctor']
        if doctor not in doctors:
            doctors[doctor] = []
        doctors[doctor].append(app)
    
    for doctor, apps in doctors.items():
        summary += f"👨‍⚕️ <b>{doctor}:</b> {len(apps)} записей\n"
        for app in apps:
            summary += f"   🕒 {app['time']} - {app['client_name']}\n"
        summary += "\n"
    
    summary += "🔔 <b>Действия:</b>\n"
    summary += "1. Нажмите 📞 чтобы позвонить клиенту\n"
    summary += "2. Нажмите ✅ когда клиент подтвердил\n"
    summary += "3. Нажмите ❌ если запись отменена\n\n"
    summary += "<i>Клиенты получат напоминания в 18:00</i>"
    
    send_telegram(ADMIN_ID, summary)
    
    # Отправляем каждую запись отдельно
    for i, appointment in enumerate(appointments, 1):
        message = format_appointment_message(appointment, i, for_admin=True)
        buttons = get_admin_buttons(appointment['id'])
        send_telegram(ADMIN_ID, message, buttons)
        time.sleep(0.5)  # Пауза между сообщениями
    
    return f"✅ Отчет отправлен! Записей: {len(appointments)}"

def simulate_client_messages():
    """Симуляция отправки сообщений клиентам (тест)"""
    conn = sqlite3.connect('vetmanager.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.*, c.first_name, c.last_name, c.phone 
        FROM appointments a 
        JOIN clients c ON a.client_id = c.id 
        WHERE a.appointment_date = ? AND a.status = 'pending'
    ''', ((datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),))
    
    appointments = cursor.fetchall()
    conn.close()
    
    if not appointments:
        return "❌ Нет записей для отправки клиентам"
    
    message = f"🤖 <b>ТЕСТ РАССЫЛКИ КЛИЕНТАМ</b>\n\n"
    message += f"📅 Дата: {(datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')}\n"
    message += f"👥 Клиентов: {len(appointments)}\n\n"
    message += "<b>Клиенты получат такое сообщение:</b>\n\n"
    
    for i, app in enumerate(appointments[:2], 1):  # Показываем 2 примера
        client_name = f"{app[13]} {app[14]}".strip()  # first_name + last_name
        appointment_data = {
            'id': app[1],  # vetmanager_id
            'client_name': client_name,
            'time': app[4],  # appointment_time
            'doctor': app[5],  # doctor_name
            'pet': app[6],  # pet_name
            'phone': app[15]  # phone
        }
        
        client_message = format_appointment_message(appointment_data, i, for_admin=False)
        buttons = get_client_buttons(appointment_data['id'])
        
        # Отправляем тебе как пример
        test_msg = f"👤 <b>Пример для клиента:</b> {client_name}\n\n{client_message}"
        send_telegram(ADMIN_ID, test_msg, buttons)
        
        message += f"{i}. {client_name} - {app[4]} ({app[5]})\n"
        
        time.sleep(1)
    
    message += f"\n<i>В реальной системе клиенты получат:\n"
    message += f"• Сообщение в Telegram с кнопками\n"
    message += f"• Напоминание за день до визита\n"
    message += f"• Напоминание за 2 часа до визита</i>"
    
    send_telegram(ADMIN_ID, message)
    
    return f"✅ Тест рассылки завершен. Примеры отправлены."

# ============ 5. WEBHOOK И ОБРАБОТКА КНОПОК ============
@app.route("/webhook", methods=["POST"])
def webhook():
    """Обработка Telegram webhook"""
    try:
        data = request.json
        
        if "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["from"]["id"]
            callback_data = callback["data"]
            
            print(f"📲 Callback: {callback_data} from {chat_id}")
            
            # Обработка действий администратора
            if callback_data.startswith("call_"):
                appointment_id = callback_data.split("_")[1]
                handle_admin_call(appointment_id, chat_id)
                
            elif callback_data.startswith("confirm_"):
                appointment_id = callback_data.split("_")[1]
                handle_admin_confirm(appointment_id, chat_id)
                
            elif callback_data.startswith("cancel_"):
                appointment_id = callback_data.split("_")[1]
                handle_admin_cancel(appointment_id, chat_id)
                
            elif callback_data.startswith("note_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"📝 Добавьте заметку для записи #{appointment_id} в VetManager")
            
            # Ответ на callback
            answer_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
            requests.post(answer_url, json={"callback_query_id": callback["id"]})
            
        return "OK"
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return "ERROR"

def handle_admin_call(appointment_id, chat_id):
    """Обработка звонка администратора"""
    conn = sqlite3.connect('vetmanager.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.*, c.first_name, c.last_name, c.phone 
        FROM appointments a 
        JOIN clients c ON a.client_id = c.id 
        WHERE a.vetmanager_id = ?
    ''', (appointment_id,))
    
    appointment = cursor.fetchone()
    conn.close()
    
    if appointment:
        client_name = f"{appointment[13]} {appointment[14]}".strip()
        phone = appointment[15]
        time = appointment[4]
        
        message = f"📞 <b>ДАННЫЕ ДЛЯ ЗВОНКА</b>\n\n"
        message += f"👤 <b>Клиент:</b> {client_name}\n"
        message += f"📱 <b>Телефон:</b> {phone or 'Не указан'}\n"
        message += f"🕒 <b>Время записи:</b> {time}\n"
        message += f"🐾 <b>Питомец:</b> {appointment[6]}\n\n"
        message += f"<i>Цель звонка: подтвердить визит на завтра</i>"
        
        send_telegram(chat_id, message)
        log_action("ADMIN_CALL", f"Звонок клиенту {client_name}")
    else:
        send_telegram(chat_id, f"❌ Запись #{appointment_id} не найдена")

def handle_admin_confirm(appointment_id, chat_id):
    """Подтверждение записи администратором"""
    conn = sqlite3.connect('vetmanager.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE appointments SET status = 'confirmed' 
        WHERE vetmanager_id = ?
    ''', (appointment_id,))
    
    conn.commit()
    
    # Получаем данные клиента
    cursor.execute('''
        SELECT c.first_name, c.last_name, a.appointment_time 
        FROM appointments a 
        JOIN clients c ON a.client_id = c.id 
        WHERE a.vetmanager_id = ?
    ''', (appointment_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        client_name = f"{result[0]} {result[1]}".strip()
        message = f"✅ <b>ЗАПИСЬ ПОДТВЕРЖДЕНА</b>\n\n"
        message += f"👤 Клиент: {client_name}\n"
        message += f"🕒 Время: {result[2]}\n"
        message += f"📅 Дата: {(datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')}\n\n"
        message += f"<i>Статус изменен в системе</i>"
        
        send_telegram(chat_id, message)
        log_action("ADMIN_CONFIRM", f"Запись {appointment_id} подтверждена")
    else:
        send_telegram(chat_id, f"✅ Запись #{appointment_id} отмечена как подтвержденная")

# ============ 6. ВЕБ-ИНТЕРФЕЙС ============
@app.route("/")
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>VetManager Reminder System</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #2c3e50; }
            .card { background: #f8f9fa; border-radius: 10px; padding: 20px; margin: 15px 0; }
            .btn { display: inline-block; background: #3498db; color: white; padding: 12px 24px; 
                   text-decoration: none; border-radius: 5px; margin: 5px; font-weight: bold; }
            .btn:hover { background: #2980b9; }
            .btn-success { background: #27ae60; }
            .btn-success:hover { background: #219653; }
            .btn-warning { background: #f39c12; }
            .btn-warning:hover { background: #e67e22; }
        </style>
    </head>
    <body>
        <h1>🤖 VetManager Reminder System</h1>
        
        <div class="card">
            <h2>🎯 Система напоминаний клиентам</h2>
            <p><b>Статус:</b> 🟢 Активен</p>
            <p><b>База данных:</b> SQLite (vetmanager.db)</p>
            <p><b>Администратор:</b> Telegram ID {ADMIN_ID}</p>
        </div>
        
        <div class="card">
            <h3>📋 Основные функции</h3>
            <a class="btn btn-success" href="/report">📊 Ежедневный отчет</a><br><br>
            <a class="btn" href="/test_send">👥 Тест рассылки клиентам</a><br><br>
            <a class="btn" href="/view_db">🗄️ Просмотр базы данных</a><br><br>
            <a class="btn" href="/settings">⚙️ Настройки</a>
        </div>
        
        <div class="card">
            <h3>🔄 Автоматические задачи</h3>
            <p><b>Ежедневно в 18:00:</b> Отчет администратору</p>
            <p><b>Ежедневно в 19:00:</b> Напоминания клиентам (тест)</p>
            <p><b>По запросу:</b> Обновление данных из VetManager</p>
        </div>
        
        <div class="card">
            <h3>📞 Для работы с клиентами</h3>
            <p>1. Получите ежедневный отчет</p>
            <p>2. Позвоните клиентам по кнопке 📞</p>
            <p>3. Отметьте подтверждения кнопкой ✅</p>
            <p>4. Отмените записи кнопкой ❌</p>
        </div>
    </body>
    </html>
    '''

@app.route("/report")
def report():
    return send_daily_report_to_admin()

@app.route("/test_send")
def test_send():
    return simulate_client_messages()

@app.route("/view_db")
def view_db():
    """Просмотр содержимого базы данных"""
    conn = sqlite3.connect('vetmanager.db')
    cursor = conn.cursor()
    
    html = "<h2>🗄️ Содержимое базы данных</h2>"
    
    # Клиенты
    cursor.execute('SELECT COUNT(*) FROM clients')
    client_count = cursor.fetchone()[0]
    html += f"<p><b>Клиентов в базе:</b> {client_count}</p>"
    
    # Записи на завтра
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    cursor.execute('SELECT COUNT(*) FROM appointments WHERE appointment_date = ?', (tomorrow,))
    app_count = cursor.fetchone()[0]
    html += f"<p><b>Записей на завтра:</b> {app_count}</p>"
    
    # Последние логи
    html += "<h3>📝 Последние действия:</h3>"
    cursor.execute('SELECT action, details, created_at FROM logs ORDER BY id DESC LIMIT 10')
    logs = cursor.fetchall()
    
    for log in logs:
        html += f"<p><b>{log[0]}</b>: {log[1]} <small>({log[2]})</small></p>"
    
    conn.close()
    
    html += '<br><a href="/" class="btn">← На главную</a>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head><style>body {{ font-family: Arial; padding: 20px; }}</style></head>
    <body>{html}</body>
    </html>
    '''

# ============ 7. АВТОМАТИЗАЦИЯ ============
def auto_scheduler():
    """Автоматический планировщик задач"""
    while True:
        now = datetime.now()
        
        # Ежедневно в 18:00 - отчет администратору
        if now.hour == 18 and now.minute == 0:
            print(f"🕕 {now.strftime('%H:%M')} - Отправка ежедневного отчета...")
            send_daily_report_to_admin()
            time.sleep(61)
        
        # Ежедневно в 19:00 - тест рассылки клиентам
        if now.hour == 19 and now.minute == 0:
            print(f"🕖 {now.strftime('%H:%M')} - Тест рассылки клиентам...")
            simulate_client_messages()
            time.sleep(61)
        
        time.sleep(30)

# ============ 8. ЗАПУСК ============
if __name__ == "__main__":
    # Инициализация базы данных
    init_db()
    print("✅ База данных инициализирована")
    
    # Запуск планировщика
    scheduler = threading.Thread(target=auto_scheduler, daemon=True)
    scheduler.start()
    
    print("=" * 60)
    print("🤖 VETMANAGER REMINDER SYSTEM ЗАПУЩЕН!")
    print("=" * 60)
    print("🎯 РЕЖИМ: ПРОИЗВОДСТВЕННЫЙ")
    print("💾 База данных: vetmanager.db")
    print(f"👤 Администратор: {ADMIN_ID}")
    print("🏥 Источник данных: VetManager API")
    print("=" * 60)
    print("🌐 Веб-интерфейс:")
    print("   https://vetmanager-bot-1.onrender.com/")
    print("   https://vetmanager-bot-1.onrender.com/report")
    print("=" * 60)
    print("🔄 Автоматические задачи:")
    print("   🕕 18:00 - Ежедневный отчет")
    print("   🕖 19:00 - Тест рассылки клиентам")
    print("=" * 60)
    
    # Тестовый запуск
    print("\n🚀 Первоначальная загрузка данных...")
    appointments = process_and_store_appointments()
    print(f"📊 Загружено записей на завтра: {len(appointments)}")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
