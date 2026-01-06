from flask import Flask, request, render_template_string
import requests
from datetime import datetime, timedelta
import json
import sqlite3
import threading
import time

app = Flask(__name__)

# ============ ТВОИ КЛЮЧИ ============
TELEGRAM_TOKEN = "8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI"
ADMIN_ID = "921853682"

# ============ 1. БАЗА ДАННЫХ ДЛЯ РУЧНЫХ ЗАПИСЕЙ ============
def init_db():
    """Создаем базу данных для ручного управления"""
    conn = sqlite3.connect('manual_appointments.db')
    cursor = conn.cursor()
    
    # Таблица клиентов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            telegram_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица записей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            doctor_name TEXT NOT NULL,
            pet_name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending', -- pending, confirmed, cancelled
            reminder_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

# ============ 2. TELEGRAM ФУНКЦИИ ============
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
    except:
        return False

# ============ 3. ДОБАВЛЕНИЕ ЗАПИСИ ВРУЧНУЮ ============
def add_manual_appointment(data):
    """Добавить запись вручную"""
    conn = sqlite3.connect('manual_appointments.db')
    cursor = conn.cursor()
    
    try:
        # Добавляем или находим клиента
        cursor.execute(
            "INSERT OR IGNORE INTO clients (name, phone) VALUES (?, ?)",
            (data['client_name'], data.get('phone', ''))
        )
        
        # Получаем ID клиента
        cursor.execute(
            "SELECT id FROM clients WHERE name = ? AND phone = ?",
            (data['client_name'], data.get('phone', ''))
        )
        client_id = cursor.fetchone()[0]
        
        # Добавляем запись
        cursor.execute('''
            INSERT INTO appointments 
            (client_id, appointment_date, appointment_time, doctor_name, pet_name, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            client_id,
            data['appointment_date'],
            data['appointment_time'],
            data['doctor_name'],
            data['pet_name'],
            data.get('description', ''),
            'pending'
        ))
        
        appointment_id = cursor.lastrowid
        conn.commit()
        
        # Отправляем подтверждение
        send_telegram(
            ADMIN_ID,
            f"✅ <b>Запись добавлена вручную</b>\n\n"
            f"👤 Клиент: {data['client_name']}\n"
            f"📅 Дата: {data['appointment_date']}\n"
            f"🕒 Время: {data['appointment_time']}\n"
            f"👨‍⚕️ Врач: {data['doctor_name']}\n"
            f"🐾 Питомец: {data['pet_name']}\n"
            f"📝 ID записи: {appointment_id}"
        )
        
        return True, appointment_id
        
    except Exception as e:
        print(f"❌ Ошибка добавления записи: {e}")
        return False, str(e)
    finally:
        conn.close()

# ============ 4. ПОЛУЧЕНИЕ ЗАПИСЕЙ НА ДАТУ ============
def get_appointments_for_date(date_str):
    """Получить записи на определенную дату"""
    conn = sqlite3.connect('manual_appointments.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT a.id, c.name, c.phone, a.appointment_time, a.doctor_name, 
               a.pet_name, a.description, a.status
        FROM appointments a
        JOIN clients c ON a.client_id = c.id
        WHERE a.appointment_date = ? AND a.status != 'cancelled'
        ORDER BY a.appointment_time
    ''', (date_str,))
    
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

# ============ 5. ОТПРАВКА НАПОМИНАНИЙ ============
def send_daily_reminders():
    """Отправить напоминания на завтра"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    appointments = get_appointments_for_date(tomorrow)
    
    if not appointments:
        send_telegram(ADMIN_ID, f"📭 На завтра ({tomorrow}) нет записей")
        return "📭 Нет записей"
    
    # Отправляем отчет администратору
    message = f"📅 <b>НАПОМИНАНИЯ НА ЗАВТРА ({tomorrow})</b>\n\n"
    message += f"<i>Всего записей: {len(appointments)}</i>\n\n"
    
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
    
    send_telegram(ADMIN_ID, message)
    
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
                    {"text": "📞 Позвонить", "callback_data": f"call_{app['id']}"},
                    {"text": "✅ Подтвердить", "callback_data": f"confirm_{app['id']}"}
                ],
                [
                    {"text": "❌ Отменить", "callback_data": f"cancel_{app['id']}"},
                    {"text": "✏️ Изменить", "callback_data": f"edit_{app['id']}"}
                ]
            ]
        }
        
        send_telegram(ADMIN_ID, detail_msg, buttons)
        time.sleep(0.3)
    
    return f"✅ Напоминания отправлены! Записей: {len(appointments)}"

# ============ 6. ВЕБ-ИНТЕРФЕЙС ДЛЯ РУЧНОГО УПРАВЛЕНИЯ ============
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>VetManager Manual System</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }
        h1 { color: #2c3e50; }
        .card { background: #f8f9fa; border-radius: 10px; padding: 20px; margin: 15px 0; }
        .btn { display: inline-block; background: #3498db; color: white; padding: 10px 20px; 
               text-decoration: none; border-radius: 5px; margin: 5px; }
        .btn:hover { background: #2980b9; }
        .btn-success { background: #27ae60; }
        .btn-warning { background: #f39c12; }
        .form-group { margin: 15px 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, select, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        .appointment-card { border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .status-confirmed { color: #27ae60; }
        .status-pending { color: #f39c12; }
        .status-cancelled { color: #e74c3c; }
    </style>
</head>
<body>
    <h1>🤖 VetManager Manual System</h1>
    
    <div class="card">
        <h2>📝 Добавить запись вручную</h2>
        <form method="POST" action="/add">
            <div class="form-group">
                <label>👤 Имя клиента:</label>
                <input type="text" name="client_name" required placeholder="Наталья Куликовская">
            </div>
            
            <div class="form-group">
                <label>📞 Телефон (опционально):</label>
                <input type="tel" name="phone" placeholder="+7XXX XXX-XX-XX">
            </div>
            
            <div class="form-group">
                <label>📅 Дата приема:</label>
                <input type="date" name="appointment_date" required value="{{ tomorrow }}">
            </div>
            
            <div class="form-group">
                <label>🕒 Время приема:</label>
                <select name="appointment_time" required>
                    <option value="08:00">08:00</option>
                    <option value="08:30">08:30</option>
                    <option value="09:00">09:00</option>
                    <option value="09:30">09:30</option>
                    <option value="10:00">10:00</option>
                    <option value="10:30">10:30</option>
                    <option value="11:00">11:00</option>
                    <option value="11:30">11:30</option>
                    <option value="12:00">12:00</option>
                    <option value="12:30">12:30</option>
                    <option value="13:00">13:00</option>
                    <option value="13:30">13:30</option>
                    <option value="14:00">14:00</option>
                    <option value="14:30">14:30</option>
                    <option value="15:00">15:00</option>
                    <option value="15:30">15:30</option>
                    <option value="16:00">16:00</option>
                    <option value="16:30">16:30</option>
                    <option value="17:00">17:00</option>
                    <option value="17:30">17:30</option>
                    <option value="18:00">18:00</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>👨‍⚕️ Врач:</label>
                <select name="doctor_name" required>
                    <option value="Базарнов">Базарнов</option>
                    <option value="Олексин">Олексин</option>
                    <option value="Другой">Другой врач</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>🐾 Имя питомца:</label>
                <input type="text" name="pet_name" required placeholder="Чупа">
            </div>
            
            <div class="form-group">
                <label>📝 Комментарий (опционально):</label>
                <textarea name="description" rows="3" placeholder="без обслед, будет..."></textarea>
            </div>
            
            <button type="submit" class="btn btn-success">✅ Добавить запись</button>
        </form>
    </div>
    
    <div class="card">
        <h2>📋 Записи на завтра ({{ tomorrow }})</h2>
        {% if appointments %}
            <p>Всего записей: {{ appointments|length }}</p>
            
            {% for app in appointments %}
            <div class="appointment-card">
                <h3>🕒 {{ app.time }} - {{ app.client_name }}</h3>
                <p>👨‍⚕️ Врач: {{ app.doctor }}</p>
                <p>🐾 Питомец: {{ app.pet }}</p>
                <p>📞 Телефон: {{ app.phone }}</p>
                {% if app.description %}
                <p>📝 Комментарий: {{ app.description }}</p>
                {% endif %}
                <p class="status-{{ app.status }}">Статус: 
                    {% if app.status == 'confirmed' %}✅ Подтверждено
                    {% elif app.status == 'cancelled' %}❌ Отменено
                    {% else %}⏳ Ожидает подтверждения{% endif %}
                </p>
                
                <div>
                    <a href="/confirm/{{ app.id }}" class="btn btn-success">✅ Подтвердить</a>
                    <a href="/cancel/{{ app.id }}" class="btn">❌ Отменить</a>
                    <a href="/delete/{{ app.id }}" class="btn">🗑️ Удалить</a>
                </div>
            </div>
            {% endfor %}
        {% else %}
            <p>📭 Записей на завтра нет</p>
        {% endif %}
        
        <a href="/remind" class="btn">🔔 Отправить напоминания</a>
        <a href="/view_all" class="btn">📊 Все записи</a>
    </div>
    
    <div class="card">
        <h2>⚡ Быстрые действия</h2>
        <a href="/remind" class="btn btn-warning">📨 Отправить напоминания</a>
        <a href="/add_sample" class="btn">➕ Добавить тестовые записи</a>
        <a href="/clear" class="btn">🗑️ Очистить все</a>
    </div>
</body>
</html>
'''

@app.route("/")
def home():
    """Главная страница"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    appointments = get_appointments_for_date(tomorrow)
    
    return render_template_string(
        HTML_TEMPLATE,
        tomorrow=tomorrow,
        appointments=appointments
    )

@app.route("/add", methods=["POST"])
def add_appointment():
    """Добавить запись через форму"""
    data = {
        'client_name': request.form['client_name'],
        'phone': request.form.get('phone', ''),
        'appointment_date': request.form['appointment_date'],
        'appointment_time': request.form['appointment_time'],
        'doctor_name': request.form['doctor_name'],
        'pet_name': request.form['pet_name'],
        'description': request.form.get('description', '')
    }
    
    success, result = add_manual_appointment(data)
    
    if success:
        return f'''
        <div style="font-family: Arial; padding: 20px;">
            <h2>✅ Запись добавлена!</h2>
            <p>ID записи: {result}</p>
            <p>Данные отправлены в Telegram</p>
            <a href="/" class="btn">← На главную</a>
        </div>
        '''
    else:
        return f'''
        <div style="font-family: Arial; padding: 20px;">
            <h2>❌ Ошибка!</h2>
            <p>{result}</p>
            <a href="/" class="btn">← Назад</a>
        </div>
        '''

@app.route("/remind")
def remind():
    """Отправить напоминания"""
    result = send_daily_reminders()
    return f'''
    <div style="font-family: Arial; padding: 20px;">
        <h2>🔔 Напоминания отправлены</h2>
        <p>{result}</p>
        <a href="/" class="btn">← На главную</a>
    </div>
    '''

@app.route("/confirm/<int:appointment_id>")
def confirm_appointment(appointment_id):
    """Подтвердить запись"""
    conn = sqlite3.connect('manual_appointments.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE appointments SET status = 'confirmed' WHERE id = ?",
        (appointment_id,)
    )
    
    conn.commit()
    
    # Получаем данные для уведомления
    cursor.execute('''
        SELECT c.name, a.appointment_date, a.appointment_time, a.doctor_name
        FROM appointments a
        JOIN clients c ON a.client_id = c.id
        WHERE a.id = ?
    ''', (appointment_id,))
    
    appointment = cursor.fetchone()
    conn.close()
    
    if appointment:
        send_telegram(
            ADMIN_ID,
            f"✅ <b>ЗАПИСЬ ПОДТВЕРЖДЕНА</b>\n\n"
            f"👤 Клиент: {appointment[0]}\n"
            f"📅 Дата: {appointment[1]}\n"
            f"🕒 Время: {appointment[2]}\n"
            f"👨‍⚕️ Врач: {appointment[3]}"
        )
    
    return f'''
    <div style="font-family: Arial; padding: 20px;">
        <h2>✅ Запись подтверждена</h2>
        <p>Запись #{appointment_id} отмечена как подтвержденная</p>
        <a href="/" class="btn">← На главную</a>
    </div>
    '''

@app.route("/add_sample")
def add_sample():
    """Добавить тестовые записи (как на скриншоте)"""
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
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    added_count = 0
    
    for app_data in sample_appointments:
        app_data['appointment_date'] = tomorrow
        success, _ = add_manual_appointment(app_data)
        if success:
            added_count += 1
        time.sleep(0.1)
    
    return f'''
    <div style="font-family: Arial; padding: 20px;">
        <h2>✅ Тестовые записи добавлены</h2>
        <p>Добавлено {added_count} записей на завтра ({tomorrow})</p>
        <p>Теперь можно протестировать систему напоминаний!</p>
        <a href="/" class="btn">← На главную</a>
    </div>
    '''

@app.route("/view_all")
def view_all():
    """Просмотреть все записи"""
    conn = sqlite3.connect('manual_appointments.db')
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
    
    html = "<h2>📊 Все записи</h2>"
    
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
        html += "<p>📭 Записей нет</p>"
    
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

# ============ 7. АВТОМАТИЧЕСКИЕ НАПОМИНАНИЯ ============
def auto_reminder():
    """Автоматическая отправка напоминаний"""
    while True:
        now = datetime.now()
        
        # Ежедневно в 18:00 - напоминания на завтра
        if now.hour == 18 and now.minute == 0:
            print(f"🕕 {now.strftime('%H:%M')} - Отправляю напоминания...")
            send_daily_reminders()
            time.sleep(61)
        
        time.sleep(30)

# ============ 8. ЗАПУСК ============
if __name__ == "__main__":
    # Инициализация базы
    init_db()
    
    # Запуск планировщика
    scheduler = threading.Thread(target=auto_reminder, daemon=True)
    scheduler.start()
    
    print("=" * 60)
    print("🤖 VETMANAGER MANUAL SYSTEM ЗАПУЩЕН!")
    print("=" * 60)
    print("🎯 РЕЖИМ: РУЧНОЕ УПРАВЛЕНИЕ")
    print("💾 База данных: manual_appointments.db")
    print(f"👤 Администратор: {ADMIN_ID}")
    print("=" * 60)
    print("🌐 Веб-интерфейс:")
    print("   https://vetmanager-bot-1.onrender.com/")
    print("=" * 60)
    print("🔄 Автоматические задачи:")
    print("   🕕 18:00 - Ежедневные напоминания")
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=5000, debug=False)
