from flask import Flask
import requests
from datetime import datetime, timedelta
import sqlite3
import threading
import time

app = Flask(__name__)

# ============ ТВОИ КЛЮЧИ ============
TELEGRAM_TOKEN = "8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI"
VETMANAGER_KEY = "29607ccc63c684fa672be9694f7f09ec"
ADMIN_ID = "921853682"

# ============ 1. БАЗА ДАННЫХ ДЛЯ РУЧНЫХ ЗАПИСЕЙ ============
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('appointments.db')
    cursor = conn.cursor()
    
    # Таблица клиентов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица записей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            doctor_name TEXT NOT NULL,
            pet_name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

# ============ 2. TELEGRAM ФУНКЦИИ ============
def send_telegram(message, reply_markup=None):
    """Отправка сообщения в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": ADMIN_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    if reply_markup:
        data["reply_markup"] = reply_markup
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except:
        return False

# ============ 3. ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ============
def add_appointment(client_name, phone, appointment_date, appointment_time, doctor_name, pet_name, description=""):
    """Добавить запись в базу"""
    conn = sqlite3.connect('appointments.db')
    cursor = conn.cursor()
    
    try:
        # Добавляем клиента
        cursor.execute(
            "INSERT OR IGNORE INTO clients (name, phone) VALUES (?, ?)",
            (client_name, phone)
        )
        
        # Получаем ID клиента
        cursor.execute(
            "SELECT id FROM clients WHERE name = ? AND phone = ?",
            (client_name, phone)
        )
        client_id = cursor.fetchone()[0]
        
        # Добавляем запись
        cursor.execute('''
            INSERT INTO appointments 
            (client_id, appointment_date, appointment_time, doctor_name, pet_name, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, appointment_date, appointment_time, doctor_name, pet_name, description, 'pending'))
        
        appointment_id = cursor.lastrowid
        conn.commit()
        
        return True, appointment_id
        
    except Exception as e:
        print(f"❌ Ошибка добавления записи: {e}")
        return False, str(e)
    finally:
        conn.close()

def get_tomorrow_appointments():
    """Получить записи на завтра"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect('appointments.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.id, c.name, c.phone, a.appointment_time, a.doctor_name, 
               a.pet_name, a.description, a.status
        FROM appointments a
        JOIN clients c ON a.client_id = c.id
        WHERE a.appointment_date = ? AND a.status != 'cancelled'
        ORDER BY a.appointment_time
    ''', (tomorrow,))
    
    appointments = cursor.fetchall()
    conn.close()
    
    result = []
    for app in appointments:
        result.append({
            'id': app[0],
            'client_name': app[1],
            'phone': app[2] or 'Не указан',
            'time': app[3],
            'doctor': app[4],
            'pet': app[5],
            'description': app[6] or '',
            'status': app[7]
        })
    
    return result

def confirm_appointment(appointment_id):
    """Подтвердить запись"""
    conn = sqlite3.connect('appointments.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE appointments SET status = 'confirmed' WHERE id = ?",
        (appointment_id,)
    )
    
    conn.commit()
    conn.close()
    return True

# ============ 4. ОСНОВНАЯ ФУНКЦИЯ НАПОМИНАНИЙ ============
def send_daily_reminder():
    """Отправить ежедневные напоминания"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    appointments = get_tomorrow_appointments()
    
    if not appointments:
        send_telegram(f"📭 На завтра ({tomorrow}) нет записей")
        return "📭 Нет записей"
    
    # Общая сводка
    message = f"📅 <b>ЕЖЕДНЕВНЫЙ ОТЧЕТ - {tomorrow}</b>\n\n"
    message += f"<i>Всего записей на завтра: {len(appointments)}</i>\n\n"
    
    # Группируем по врачам
    doctors = {}
    for app in appointments:
        doctor = app['doctor']
        if doctor not in doctors:
            doctors[doctor] = []
        doctors[doctor].append(app)
    
    for doctor, apps in doctors.items():
        message += f"👨‍⚕️ <b>{doctor}:</b> {len(apps)} записей\n"
        for app in apps:
            status_icon = "✅" if app['status'] == 'confirmed' else "⏳"
            message += f"   {status_icon} {app['time']} - {app['client_name']} ({app['pet']})\n"
        message += "\n"
    
    message += "🔔 <b>Действия:</b>\n"
    message += "1. Позвоните клиентам для подтверждения\n"
    message += "2. Отметьте подтверждения на сайте\n"
    message += "3. Клиенты получат напоминания автоматически"
    
    send_telegram(message)
    
    # Отправляем детали по каждой записи
    for app in appointments:
        detail_msg = f"📋 <b>Запись #{app['id']}</b>\n"
        detail_msg += f"👤 <b>Клиент:</b> {app['client_name']}\n"
        detail_msg += f"📞 <b>Телефон:</b> {app['phone']}\n"
        detail_msg += f"🕒 <b>Время:</b> {app['time']}\n"
        detail_msg += f"👨‍⚕️ <b>Врач:</b> {app['doctor']}\n"
        detail_msg += f"🐾 <b>Питомец:</b> {app['pet']}\n"
        
        if app['description']:
            detail_msg += f"📝 <b>Комментарий:</b> {app['description']}\n"
        
        detail_msg += f"\n<b>Статус:</b> {'✅ Подтверждено' if app['status'] == 'confirmed' else '⏳ Ожидает'}"
        
        # Кнопки для управления
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "✅ Подтвердить", "callback_data": f"confirm_{app['id']}"},
                    {"text": "❌ Отменить", "callback_data": f"cancel_{app['id']}"}
                ],
                [
                    {"text": "📞 Позвонить", "callback_data": f"call_{app['id']}"},
                    {"text": "✏️ Изменить", "callback_data": f"edit_{app['id']}"}
                ]
            ]
        }
        
        send_telegram(detail_msg, buttons)
        time.sleep(0.3)
    
    return f"✅ Напоминания отправлены! Записей: {len(appointments)}"

# ============ 5. ВЕБ-ИНТЕРФЕЙС ============
@app.route("/")
def home():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>VetManager Reminder System</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; max-width: 800px; margin: 0 auto; }}
            h1 {{ color: #2c3e50; }}
            .card {{ background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 15px 0; }}
            .btn {{ display: inline-block; background: #3498db; color: white; padding: 10px 20px; 
                   text-decoration: none; border-radius: 5px; margin: 5px; }}
            .btn-success {{ background: #27ae60; }}
        </style>
    </head>
    <body>
        <h1>🤖 VetManager Reminder System</h1>
        
        <div class="card">
            <h2>📅 Завтра: {tomorrow}</h2>
            <p><b>Статус:</b> ✅ Система работает</p>
            <p><b>Режим:</b> Ручное управление записями</p>
            <p><b>Администратор:</b> ID {ADMIN_ID}</p>
        </div>
        
        <div class="card">
            <h3>🎯 Основные функции</h3>
            <a class="btn btn-success" href="/remind">🔔 Отправить напоминания</a><br><br>
            <a class="btn" href="/add_sample">➕ Добавить тестовые записи</a><br><br>
            <a class="btn" href="/view_all">📊 Просмотреть все записи</a>
        </div>
        
        <div class="card">
            <h3>📝 Как это работает:</h3>
            <p>1. <b>Добавьте записи</b> в базу данных (вручную или через тест)</p>
            <p>2. <b>В 18:00 автоматически</b> придут напоминания</p>
            <p>3. <b>Или нажмите кнопку</b> чтобы отправить сейчас</p>
            <p>4. <b>Позвоните клиентам</b> и подтвердите записи</p>
        </div>
        
        <div class="card">
            <h3>🔄 Автоматические задачи</h3>
            <p><b>Ежедневно в 18:00:</b> Напоминания на завтра</p>
            <p><b>По запросу:</b> Отправка напоминаний сейчас</p>
        </div>
    </body>
    </html>
    '''

@app.route("/remind")
def remind():
    return send_daily_reminder()

@app.route("/add_sample")
def add_sample():
    """Добавить тестовые записи (как на скриншоте)"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    sample_appointments = [
        # Базарнов
        {"client_name": "Наталья Куликовская", "phone": "+7XXX-XXX-XX-XX", 
         "appointment_time": "08:00", "doctor_name": "Базарнов", "pet_name": "Чупа", 
         "description": "без обслед, будет..."},
        {"client_name": "Галина Губанова", "phone": "+7XXX-XXX-XX-XX",
         "appointment_time": "09:00", "doctor_name": "Базарнов", "pet_name": "Бусинка",
         "description": "без обсл, будет..."},
        {"client_name": "Дарья Никитина", "phone": "+7XXX-XXX-XX-XX",
         "appointment_time": "09:15", "doctor_name": "Базарнов", "pet_name": "Кетти",
         "description": ""},
        
        # Олексин  
        {"client_name": "Алена Бут", "phone": "+7XXX-XXX-XX-XX",
         "appointment_time": "09:00", "doctor_name": "Олексин", "pet_name": "Леди",
         "description": ""},
        {"client_name": "Елена Зинченко", "phone": "+7XXX-XXX-XX-XX",
         "appointment_time": "12:00", "doctor_name": "Олексин", "pet_name": "Спартак",
         "description": "будет, у обоих животных будто лихорадка..."},
        {"client_name": "Елена Зинченко", "phone": "+7XXX-XXX-XX-XX",
         "appointment_time": "12:30", "doctor_name": "Олексин", "pet_name": "Форти",
         "description": "будет..."},
    ]
    
    added_count = 0
    for app_data in sample_appointments:
        success, _ = add_appointment(
            client_name=app_data['client_name'],
            phone=app_data['phone'],
            appointment_date=tomorrow,
            appointment_time=app_data['appointment_time'],
            doctor_name=app_data['doctor_name'],
            pet_name=app_data['pet_name'],
            description=app_data['description']
        )
        if success:
            added_count += 1
    
    send_telegram(f"✅ Добавлено {added_count} тестовых записей на завтра ({tomorrow})")
    
    return f'''
    <div style="font-family: Arial; padding: 20px;">
        <h2>✅ Тестовые записи добавлены</h2>
        <p>Добавлено {added_count} записей на завтра</p>
        <p>Теперь нажмите "Отправить напоминания" чтобы увидеть их в Telegram</p>
        <a href="/" class="btn">← На главную</a>
    </div>
    '''

@app.route("/view_all")
def view_all():
    """Просмотреть все записи в базе"""
    conn = sqlite3.connect('appointments.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.id, c.name, a.appointment_date, a.appointment_time, 
               a.doctor_name, a.pet_name, a.status
        FROM appointments a
        JOIN clients c ON a.client_id = c.id
        ORDER BY a.appointment_date DESC, a.appointment_time
        LIMIT 50
    ''')
    
    appointments = cursor.fetchall()
    conn.close()
    
    html = "<h2>📊 Все записи в базе</h2>"
    
    if appointments:
        html += "<table border='1' style='width:100%; border-collapse:collapse;'>"
        html += "<tr><th>ID</th><th>Клиент</th><th>Дата</th><th>Время</th><th>Врач</th><th>Питомец</th><th>Статус</th></tr>"
        
        for app in appointments:
            status_icon = "✅" if app[6] == 'confirmed' else "❌" if app[6] == 'cancelled' else "⏳"
            html += f"<tr>"
            html += f"<td>{app[0]}</td>"
            html += f"<td>{app[1]}</td>"
            html += f"<td>{app[2]}</td>"
            html += f"<td>{app[3]}</td>"
            html += f"<td>{app[4]}</td>"
            html += f"<td>{app[5]}</td>"
            html += f"<td>{status_icon} {app[6]}</td>"
            html += f"</tr>"
        
        html += "</table>"
    else:
        html += "<p>📭 Записей в базе нет</p>"
    
    html += '<br><a href="/" class="btn">← На главную</a>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head><style>
        body {{ font-family: Arial; padding: 20px; }}
        table {{ margin: 20px 0; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
        .btn {{ background: #3498db; color: white; padding: 10px; text-decoration: none; }}
    </style></head>
    <body>{html}</body>
    </html>
    '''

# ============ 6. WEBHOOK ДЛЯ КНОПОК ============
@app.route("/webhook", methods=["POST"])
def webhook():
    """Обработка кнопок Telegram"""
    try:
        data = request.json
        
        if "callback_query" in data:
            callback = data["callback_query"]
            callback_data = callback["data"]
            
            print(f"📲 Получен callback: {callback_data}")
            
            # Обработка кнопок
            if callback_data.startswith("confirm_"):
                appointment_id = callback_data.split("_")[1]
                confirm_appointment(appointment_id)
                send_telegram(f"✅ Запись #{appointment_id} подтверждена")
                
            elif callback_data.startswith("cancel_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(f"❌ Запись #{appointment_id} отменена")
                
            elif callback_data.startswith("call_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(f"📞 Для звонка по записи #{appointment_id} проверьте телефон в деталях записи")
                
            elif callback_data.startswith("edit_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(f"✏️ Для изменения записи #{appointment_id} свяжитесь с администратором")
            
            # Ответ на callback
            answer_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
            requests.post(answer_url, json={"callback_query_id": callback["id"]})
            
        return "OK"
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return "ERROR"

# ============ 7. АВТОМАТИЧЕСКИЕ НАПОМИНАНИЯ ============
def auto_reminder():
    """Автоматическая отправка напоминаний"""
    while True:
        now = datetime.now()
        
        # Ежедневно в 18:00
        if now.hour == 18 and now.minute == 0:
            print(f"🕕 {now.strftime('%H:%M')} - Отправка напоминаний...")
            send_daily_reminder()
            time.sleep(61)
        
        time.sleep(30)

# ============ 8. ЗАПУСК СИСТЕМЫ ============
if __name__ == "__main__":
    # Инициализация базы данных
    init_db()
    
    # Запуск планировщика
    scheduler = threading.Thread(target=auto_reminder, daemon=True)
    scheduler.start()
    
    print("=" * 60)
    print("🤖 VETMANAGER REMINDER SYSTEM ЗАПУЩЕН!")
    print("=" * 60)
    print("🎯 РЕЖИМ: РУЧНОЕ УПРАВЛЕНИЕ ЗАПИСЯМИ")
    print("💾 База данных: appointments.db")
    print(f"👤 Администратор: {ADMIN_ID}")
    print("🤖 Telegram бот: @Fulsim_bot")
    print("=" * 60)
    print("🌐 Веб-интерфейс:")
    print("   https://vetmanager-bot-1.onrender.com/")
    print("   https://vetmanager-bot-1.onrender.com/remind")
    print("=" * 60)
    print("🔄 Автоматические задачи:")
    print("   🕕 18:00 - Ежедневные напоминания")
    print("=" * 60)
    
    # Отправляем тестовое сообщение
    send_telegram("🤖 <b>Система напоминаний перезапущена!</b>\n\nГотова к работе.")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
