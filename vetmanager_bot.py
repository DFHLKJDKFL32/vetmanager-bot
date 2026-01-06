from flask import Flask, request
import requests
from datetime import datetime, timedelta
import sqlite3
import threading
import time
import json

app = Flask(__name__)

# ============ ТВОИ КЛЮЧИ ============
TELEGRAM_TOKEN = "8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI"
ADMIN_ID = "921853682"

# ============ 1. БАЗА ДАННЫХ ============
def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('vet_clinic.db')
    cursor = conn.cursor()
    
    # Клиенты
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            telegram_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(phone)
        )
    ''')
    
    # Питомцы
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            animal_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
    ''')
    
    # Записи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            pet_id INTEGER NOT NULL,
            appointment_date DATE NOT NULL,
            appointment_time TIME NOT NULL,
            doctor TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending', -- pending, confirmed, cancelled, completed
            reminder_1_sent BOOLEAN DEFAULT 0, -- За день
            reminder_2_sent BOOLEAN DEFAULT 0, -- За 2 часа
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id),
            FOREIGN KEY (pet_id) REFERENCES pets (id)
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

# ============ 3. ДОБАВЛЕНИЕ КЛИЕНТОВ И ЗАПИСЕЙ ============
def add_client(first_name, last_name, phone):
    """Добавить клиента"""
    conn = sqlite3.connect('vet_clinic.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO clients (first_name, last_name, phone)
            VALUES (?, ?, ?)
        ''', (first_name, last_name, phone))
        
        client_id = cursor.lastrowid
        conn.commit()
        
        return True, client_id
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def add_pet(client_id, name, animal_type="кошка/собака"):
    """Добавить питомца"""
    conn = sqlite3.connect('vet_clinic.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO pets (client_id, name, animal_type)
            VALUES (?, ?, ?)
        ''', (client_id, name, animal_type))
        
        pet_id = cursor.lastrowid
        conn.commit()
        
        return True, pet_id
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def add_appointment(client_id, pet_id, appointment_date, appointment_time, doctor, description=""):
    """Добавить запись"""
    conn = sqlite3.connect('vet_clinic.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO appointments 
            (client_id, pet_id, appointment_date, appointment_time, doctor, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, pet_id, appointment_date, appointment_time, doctor, description, 'pending'))
        
        appointment_id = cursor.lastrowid
        conn.commit()
        
        return True, appointment_id
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

# ============ 4. ПОЛУЧЕНИЕ ДАННЫХ ============
def get_tomorrow_appointments():
    """Получить все записи на завтра"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect('vet_clinic.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            a.id,
            c.first_name || ' ' || c.last_name as client_name,
            c.phone,
            p.name as pet_name,
            a.appointment_time,
            a.doctor,
            a.description,
            a.status
        FROM appointments a
        JOIN clients c ON a.client_id = c.id
        JOIN pets p ON a.pet_id = p.id
        WHERE a.appointment_date = ? 
        AND a.status != 'cancelled'
        ORDER BY a.appointment_time, a.doctor
    ''', (tomorrow,))
    
    appointments = cursor.fetchall()
    conn.close()
    
    result = []
    for app in appointments:
        result.append({
            'id': app[0],
            'client_name': app[1],
            'phone': app[2],
            'pet_name': app[3],
            'time': app[4],
            'doctor': app[5],
            'description': app[6] or '',
            'status': app[7]
        })
    
    return result

def get_all_clients():
    """Получить всех клиентов"""
    conn = sqlite3.connect('vet_clinic.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, first_name, last_name, phone, 
               (SELECT COUNT(*) FROM pets WHERE client_id = clients.id) as pet_count,
               (SELECT COUNT(*) FROM appointments WHERE client_id = clients.id) as appointment_count
        FROM clients
        ORDER BY last_name, first_name
    ''')
    
    clients = cursor.fetchall()
    conn.close()
    
    return clients

# ============ 5. ОТПРАВКА НАПОМИНАНИЙ ============
def send_reminder_to_admin():
    """Отправить напоминание администратору"""
    appointments = get_tomorrow_appointments()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    if not appointments:
        send_telegram(ADMIN_ID, f"📭 На завтра ({tomorrow}) нет записей")
        return "📭 Нет записей"
    
    # Общая сводка
    message = f"📅 <b>ЗАВТРА {tomorrow} - {len(appointments)} ЗАПИСЕЙ</b>\n\n"
    
    # Группируем по врачам
    doctors = {}
    for app in appointments:
        doctor = app['doctor']
        if doctor not in doctors:
            doctors[doctor] = []
        doctors[doctor].append(app)
    
    total_confirmed = sum(1 for app in appointments if app['status'] == 'confirmed')
    
    for doctor, apps in doctors.items():
        confirmed = sum(1 for app in apps if app['status'] == 'confirmed')
        message += f"👨‍⚕️ <b>{doctor}:</b> {len(apps)} записей ({confirmed} подтверждено)\n"
        
        for app in apps:
            status_icon = "✅" if app['status'] == 'confirmed' else "⏳"
            message += f"   {status_icon} {app['time']} - {app['client_name']}\n"
            message += f"      🐾 {app['pet_name']}"
            if app['description']:
                message += f" | 📝 {app['description'][:30]}..."
            message += f"\n"
        
        message += "\n"
    
    message += f"📊 <b>Итого:</b> {len(appointments)} записей, {total_confirmed} подтверждено\n\n"
    message += "🔔 <b>Что делать:</b>\n"
    message += "1. Позвоните клиентам для подтверждения\n"
    message += "2. Нажмите ✅ чтобы отметить подтверждение\n"
    message += "3. Нажмите ❌ чтобы отменить запись\n"
    message += "4. Нажмите 📞 чтобы увидеть телефон"
    
    send_telegram(ADMIN_ID, message)
    
    # Отправляем детали по каждой записи с кнопками
    for app in appointments:
        detail_msg = f"📋 <b>Запись #{app['id']}</b>\n"
        detail_msg += f"👤 <b>Клиент:</b> {app['client_name']}\n"
        detail_msg += f"📞 <b>Телефон:</b> {app['phone']}\n"
        detail_msg += f"🕒 <b>Время:</b> {app['time']}\n"
        detail_msg += f"👨‍⚕️ <b>Врач:</b> {app['doctor']}\n"
        detail_msg += f"🐾 <b>Питомец:</b> {app['pet_name']}\n"
        
        if app['description']:
            detail_msg += f"📝 <b>Примечание:</b> {app['description']}\n"
        
        status_text = "✅ Подтверждено" if app['status'] == 'confirmed' else "⏳ Ожидает подтверждения"
        detail_msg += f"\n<b>Статус:</b> {status_text}"
        
        # Кнопки
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
        
        send_telegram(ADMIN_ID, detail_msg, buttons)
        time.sleep(0.2)
    
    return f"✅ Напоминания отправлены! Записей: {len(appointments)}"

def send_reminder_to_clients():
    """Отправить напоминания клиентам (пока тест - отправляем администратору)"""
    appointments = get_tomorrow_appointments()
    
    if not appointments:
        return "📭 Нет записей для отправки клиентам"
    
    message = f"🤖 <b>ТЕСТ РАССЫЛКИ КЛИЕНТАМ</b>\n\n"
    message += f"📅 Завтра: {(datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')}\n"
    message += f"👥 Клиентов: {len(appointments)}\n\n"
    message += "<b>Пример сообщения для клиента:</b>\n\n"
    
    for app in appointments[:2]:  # Показываем 2 примера
        client_message = f"🐾 <b>Напоминание о визите в ветеринарную клинику</b>\n\n"
        client_message += f"📅 <b>Дата:</b> {(datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')}\n"
        client_message += f"🕒 <b>Время:</b> {app['time']}\n"
        client_message += f"👨‍⚕️ <b>Врач:</b> {app['doctor']}\n"
        client_message += f"🐶 <b>Питомец:</b> {app['pet_name']}\n\n"
        client_message += f"<i>Пожалуйста, подтвердите визит:</i>"
        
        # Кнопки для клиента
        client_buttons = {
            "inline_keyboard": [
                [
                    {"text": "✅ Да, приду", "callback_data": f"client_yes_{app['id']}"},
                    {"text": "❌ Не смогу", "callback_data": f"client_no_{app['id']}"}
                ],
                [
                    {"text": "📞 Связаться", "callback_data": f"client_call_{app['id']}"}
                ]
            ]
        }
        
        # Отправляем тебе как пример
        test_msg = f"👤 <b>Пример для клиента {app['client_name']}:</b>\n\n{client_message}"
        send_telegram(ADMIN_ID, test_msg, client_buttons)
        time.sleep(1)
    
    message += f"\n<i>В реальной работе:</i>\n"
    message += f"• Клиенты получат такое сообщение\n"
    message += f"• Могут подтвердить или отменить\n"
    message += f"• Вы получите уведомление об ответе"
    
    send_telegram(ADMIN_ID, message)
    
    return f"✅ Тест рассылки завершен. Примеры отправлены."

# ============ 6. ВЕБ-ИНТЕРФЕЙС ============
@app.route("/")
def home():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    appointments = get_tomorrow_appointments()
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ветеринарная клиника - система напоминаний</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #2c3e50; }}
            .card {{ background: #f8f9fa; border-radius: 10px; padding: 25px; margin: 20px 0; border-left: 5px solid #3498db; }}
            .btn {{ display: inline-block; background: #3498db; color: white; padding: 12px 25px; 
                   text-decoration: none; border-radius: 6px; margin: 8px; font-weight: bold; font-size: 16px; }}
            .btn:hover {{ background: #2980b9; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
            .btn-success {{ background: #27ae60; }}
            .btn-success:hover {{ background: #219653; }}
            .btn-warning {{ background: #f39c12; }}
            .btn-warning:hover {{ background: #e67e22; }}
            .appointment {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .status-confirmed {{ color: #27ae60; font-weight: bold; }}
            .status-pending {{ color: #f39c12; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f8f9fa; }}
        </style>
    </head>
    <body>
        <h1>🏥 Ветеринарная клиника - система напоминаний</h1>
        
        <div class="card">
            <h2>📅 Завтра: {tomorrow}</h2>
            <p><b>Статус системы:</b> ✅ Активна</p>
            <p><b>Записей на завтра:</b> {len(appointments)}</p>
            <p><b>Администратор:</b> Telegram ID {ADMIN_ID}</p>
            <p><b>Автоматические напоминания:</b> Ежедневно в 18:00</p>
        </div>
        
        <div class="card">
            <h3>🎯 Основные действия</h3>
            <a class="btn btn-success" href="/remind">🔔 Отправить напоминания сейчас</a>
            <a class="btn" href="/add_client">➕ Добавить клиента</a>
            <a class="btn" href="/add_appointment">📝 Добавить запись</a>
            <a class="btn btn-warning" href="/test_clients">👥 Тест рассылки клиентам</a>
        </div>
        
        <div class="card">
            <h3>📋 Записи на завтра ({tomorrow})</h3>
            {f'''
            <table>
                <tr>
                    <th>Время</th>
                    <th>Клиент</th>
                    <th>Питомец</th>
                    <th>Врач</th>
                    <th>Телефон</th>
                    <th>Статус</th>
                </tr>
                {''.join([f'''
                <tr>
                    <td>{app['time']}</td>
                    <td>{app['client_name']}</td>
                    <td>{app['pet_name']}</td>
                    <td>{app['doctor']}</td>
                    <td>{app['phone']}</td>
                    <td class="{'status-confirmed' if app['status'] == 'confirmed' else 'status-pending'}">
                        {'✅ Подтверждено' if app['status'] == 'confirmed' else '⏳ Ожидает'}
                    </td>
                </tr>
                ''' for app in appointments])}
            </table>
            ''' if appointments else '<p>📭 Записей на завтра нет</p>'}
        </div>
        
        <div class="card">
            <h3>📊 Статистика</h3>
            <a class="btn" href="/clients">👥 Все клиенты ({len(get_all_clients())})</a>
            <a class="btn" href="/add_sample">➕ Тестовые данные</a>
            <a class="btn" href="/webhook_status">🔗 Статус Webhook</a>
        </div>
    </body>
    </html>
    '''

@app.route("/remind")
def remind():
    return send_reminder_to_admin()

@app.route("/test_clients")
def test_clients():
    return send_reminder_to_clients()

@app.route("/add_client")
def add_client_page():
    return '''
    <div style="font-family: Arial; padding: 20px; max-width: 600px; margin: 0 auto;">
        <h2>➕ Добавить нового клиента</h2>
        <form method="POST" action="/add_client_action">
            <div style="margin: 15px 0;">
                <label><b>Имя:</b></label><br>
                <input type="text" name="first_name" required style="width: 100%; padding: 10px; margin: 5px 0;">
            </div>
            <div style="margin: 15px 0;">
                <label><b>Фамилия:</b></label><br>
                <input type="text" name="last_name" required style="width: 100%; padding: 10px; margin: 5px 0;">
            </div>
            <div style="margin: 15px 0;">
                <label><b>Телефон:</b></label><br>
                <input type="tel" name="phone" required placeholder="+7XXX XXX-XX-XX" style="width: 100%; padding: 10px; margin: 5px 0;">
            </div>
            <button type="submit" style="background: #27ae60; color: white; padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer;">
                ✅ Добавить клиента
            </button>
            <a href="/" style="margin-left: 20px;">← Отмена</a>
        </form>
    </div>
    '''

@app.route("/add_client_action", methods=["POST"])
def add_client_action():
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    phone = request.form['phone']
    
    success, result = add_client(first_name, last_name, phone)
    
    if success:
        send_telegram(ADMIN_ID, f"✅ <b>Добавлен новый клиент</b>\n\n👤 {first_name} {last_name}\n📞 {phone}\n🆔 ID: {result}")
        
        return f'''
        <div style="font-family: Arial; padding: 20px;">
            <h2>✅ Клиент добавлен!</h2>
            <p>Имя: {first_name} {last_name}</p>
            <p>Телефон: {phone}</p>
            <p>ID клиента: {result}</p>
            <a href="/add_appointment?client_id={result}" class="btn">📝 Добавить запись для этого клиента</a><br><br>
            <a href="/" class="btn">← На главную</a>
        </div>
        '''
    else:
        return f'''
        <div style="font-family: Arial; padding: 20px;">
            <h2>❌ Ошибка!</h2>
            <p>{result}</p>
            <a href="/add_client" class="btn">← Попробовать снова</a>
        </div>
        '''

@app.route("/add_appointment")
def add_appointment_page():
    clients = get_all_clients()
    
    clients_html = ""
    for client in clients:
        clients_html += f'<option value="{client[0]}">{client[2]} {client[1]} - {client[3]}</option>'
    
    return f'''
    <div style="font-family: Arial; padding: 20px; max-width: 600px; margin: 0 auto;">
        <h2>📝 Добавить новую запись</h2>
        <form method="POST" action="/add_appointment_action">
            <div style="margin: 15px 0;">
                <label><b>Клиент:</b></label><br>
                <select name="client_id" required style="width: 100%; padding: 10px; margin: 5px 0;">
                    <option value="">Выберите клиента</option>
                    {clients_html}
                </select>
            </div>
            <div style="margin: 15px 0;">
                <label><b>Имя питомца:</b></label><br>
                <input type="text" name="pet_name" required style="width: 100%; padding: 10px; margin: 5px 0;">
            </div>
            <div style="margin: 15px 0;">
                <label><b>Тип животного:</b></label><br>
                <select name="animal_type" style="width: 100%; padding: 10px; margin: 5px 0;">
                    <option value="кошка">Кошка</option>
                    <option value="собака">Собака</option>
                    <option value="другое">Другое</option>
                </select>
            </div>
            <div style="margin: 15px 0;">
                <label><b>Дата приема:</b></label><br>
                <input type="date" name="appointment_date" required value="{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}" style="width: 100%; padding: 10px; margin: 5px 0;">
            </div>
            <div style="margin: 15px 0;">
                <label><b>Время приема:</b></label><br>
                <select name="appointment_time" required style="width: 100%; padding: 10px; margin: 5px 0;">
                    <option value="08:00">08:00</option>
                    <option value="09:00">09:00</option>
                    <option value="10:00">10:00</option>
                    <option value="11:00">11:00</option>
                    <option value="12:00">12:00</option>
                    <option value="13:00">13:00</option>
                    <option value="14:00">14:00</option>
                    <option value="15:00">15:00</option>
                    <option value="16:00">16:00</option>
                    <option value="17:00">17:00</option>
                </select>
            </div>
            <div style="margin: 15px 0;">
                <label><b>Врач:</b></label><br>
                <select name="doctor" required style="width: 100%; padding: 10px; margin: 5px 0;">
                    <option value="Базарнов">Базарнов</option>
                    <option value="Олексин">Олексин</option>
                    <option value="Другой">Другой врач</option>
                </select>
            </div>
            <div style="margin: 15px 0;">
                <label><b>Комментарий (опционально):</b></label><br>
                <textarea name="description" rows="3" style="width: 100%; padding: 10px; margin: 5px 0;"></textarea>
            </div>
            <button type="submit" style="background: #27ae60; color: white; padding: 12px 25px; border: none; border-radius: 5px; cursor: pointer;">
                ✅ Добавить запись
            </button>
            <a href="/" style="margin-left: 20px;">← Отмена</a>
        </form>
    </div>
    '''

@app.route("/add_appointment_action", methods=["POST"])
def add_appointment_action():
    client_id = request.form['client_id']
    pet_name = request.form['pet_name']
    animal_type = request.form['animal_type']
    appointment_date = request.form['appointment_date']
    appointment_time = request.form['appointment_time']
    doctor = request.form['doctor']
    description = request.form.get('description', '')
    
    # Добавляем питомца
    success1, pet_id = add_pet(client_id, pet_name, animal_type)
    
    if not success1:
        return f"❌ Ошибка добавления питомца: {pet_id}"
    
    # Добавляем запись
    success2, appointment_id = add_appointment(client_id, pet_id, appointment_date, appointment_time, doctor, description)
    
    if success2:
        # Получаем данные клиента
        conn = sqlite3.connect('vet_clinic.db')
        cursor = conn.cursor()
        cursor.execute("SELECT first_name, last_name, phone FROM clients WHERE id = ?", (client_id,))
        client = cursor.fetchone()
        conn.close()
        
        if client:
            send_telegram(
                ADMIN_ID,
                f"✅ <b>Добавлена новая запись</b>\n\n"
                f"👤 Клиент: {client[0]} {client[1]}\n"
                f"📞 Телефон: {client[2]}\n"
                f"🐾 Питомец: {pet_name}\n"
                f"📅 Дата: {appointment_date}\n"
                f"🕒 Время: {appointment_time}\n"
                f"👨‍⚕️ Врач: {doctor}\n"
                f"📝 ID записи: {appointment_id}"
            )
        
        return f'''
        <div style="font-family: Arial; padding: 20px;">
            <h2>✅ Запись добавлена!</h2>
            <p>ID записи: {appointment_id}</p>
            <p>Данные отправлены в Telegram</p>
            <a href="/" class="btn">← На главную</a>
        </div>
        '''
    else:
        return f'''
        <div style="font-family: Arial; padding: 20px;">
            <h2>❌ Ошибка!</h2>
            <p>{appointment_id}</p>
            <a href="/add_appointment" class="btn">← Попробовать снова</a>
        </div>
        '''

@app.route("/add_sample")
def add_sample():
    """Добавить тестовые данные"""
    # Добавляем клиентов как на скриншоте
    sample_clients = [
        ("Наталья", "Куликовская", "+7XXX-XXX-XX-XX"),
        ("Галина", "Губанова", "+7XXX-XXX-XX-XX"),
        ("Дарья", "Никитина", "+7XXX-XXX-XX-XX"),
        ("Ольга", "Топольская", "+7XXX-XXX-XX-XX"),
        ("Ольга", "Писанко", "+7XXX-XXX-XX-XX"),
        ("Виктор", "Максимов", "+7XXX-XXX-XX-XX"),
        ("Алена", "Бут", "+7XXX-XXX-XX-XX"),
        ("Елена", "Зинченко", "+7XXX-XXX-XX-XX"),
        ("Дмитриенко", "", "+7XXX-XXX-XX-XX"),
    ]
    
    added_clients = {}
    for first_name, last_name, phone in sample_clients:
        success, client_id = add_client(first_name, last_name, phone)
        if success:
            added_clients[f"{first_name} {last_name}".strip()] = client_id
    
    # Добавляем питомцев и записи на завтра
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    sample_appointments = [
        ("Наталья Куликовская", "Чупа", "08:00", "Базарнов", "без обслед, будет..."),
        ("Галина Губанова", "Бусинка", "09:00", "Базарнов", "без обсл, будет..."),
        ("Дарья Никитина", "Кетти", "09:15", "Базарнов", ""),
        ("Ольга Топольская", "Изида", "09:30", "Базарнов", ""),
        ("Ольга Писанко", "Фил", "09:45", "Базарнов", "без обслед, будут..."),
        ("Виктор Максимов", "Котенок", "10:00", "Базарнов", "две стерилки+1 кастрация выше+уд зубов..."),
        ("Алена Бут", "Леди", "09:00", "Олексин", ""),
        ("Елена Зинченко", "Спартак", "12:00", "Олексин", "будет, у обоих животных будто лихорадка..."),
        ("Елена Зинченко", "Форти", "12:30", "Олексин", "будет..."),
        ("Дмитриенко", "Гера", "13:30", "Олексин", ""),
    ]
    
    added_count = 0
    for client_name, pet_name, time, doctor, description in sample_appointments:
        if client_name in added_clients:
            client_id = added_clients[client_name]
            
            # Добавляем питомца
            success1, pet_id = add_pet(client_id, pet_name)
            
            if success1:
                # Добавляем запись
                success2, _ = add_appointment(client_id, pet_id, tomorrow, time, doctor, description)
                if success2:
                    added_count += 1
    
    send_telegram(ADMIN_ID, f"✅ Добавлено {added_count} тестовых записей на завтра")
    
    return f'''
    <div style="font-family: Arial; padding: 20px;">
        <h2>✅ Тестовые данные добавлены!</h2>
        <p>Добавлено клиентов: {len(added_clients)}</p>
        <p>Добавлено записей на завтра: {added_count}</p>
        <p>Теперь нажмите "Отправить напоминания" чтобы увидеть полный отчет</p>
        <a href="/remind" class="btn btn-success">🔔 Отправить напоминания</a><br><br>
        <a href="/" class="btn">← На главную</a>
    </div>
    '''

@app.route("/clients")
def clients_page():
    clients = get_all_clients()
    
    html = "<h2>👥 Все клиенты</h2>"
    
    if clients:
        html += f"<p>Всего клиентов: {len(clients)}</p>"
        html += "<table>"
        html += "<tr><th>ID</th><th>Имя</th><th>Телефон</th><th>Питомцев</th><th>Записей</th><th>Действия</th></tr>"
        
        for client in clients:
            html += f"<tr>"
            html += f"<td>{client[0]}</td>"
            html += f"<td><b>{client[2]} {client[1]}</b></td>"
            html += f"<td>{client[3]}</td>"
            html += f"<td>{client[4]}</td>"
            html += f"<td>{client[5]}</td>"
            html += f'<td><a href="/add_appointment?client_id={client[0]}">📝 Добавить запись</a></td>'
            html += f"</tr>"
        
        html += "</table>"
    else:
        html += "<p>📭 Клиентов нет</p>"
    
    html += '<br><a href="/" class="btn">← На главную</a>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head><style>
        body {{ font-family: Arial; padding: 20px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        .btn {{ background: #3498db; color: white; padding: 10px; text-decoration: none; }}
    </style></head>
    <body>{html}</body>
    </html>
    '''

# ============ 7. WEBHOOK ============
@app.route("/webhook", methods=["POST"])
def webhook():
    """Обработка кнопок Telegram"""
    try:
        data = request.json
        
        if "callback_query" in data:
            callback = data["callback_query"]
            callback_data = callback["data"]
            chat_id = callback["from"]["id"]
            
            print(f"📲 Callback: {callback_data}")
            
            # Обработка кнопок администратора
            if callback_data.startswith("confirm_"):
                appointment_id = callback_data.split("_")[1]
                
                # Обновляем статус в базе
                conn = sqlite3.connect('vet_clinic.db')
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE appointments SET status = 'confirmed' WHERE id = ?",
                    (appointment_id,)
                )
                conn.commit()
                conn.close()
                
                send_telegram(chat_id, f"✅ Запись #{appointment_id} подтверждена")
                
            elif callback_data.startswith("cancel_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"❌ Запись #{appointment_id} отменена")
                
            elif callback_data.startswith("call_"):
                appointment_id = callback_data.split("_")[1]
                # Получаем телефон из базы
                conn = sqlite3.connect('vet_clinic.db')
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT c.phone, c.first_name, c.last_name 
                    FROM appointments a
                    JOIN clients c ON a.client_id = c.id
                    WHERE a.id = ?
                ''', (appointment_id,))
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    send_telegram(chat_id, f"📞 <b>Телефон клиента:</b>\n\n👤 {result[1]} {result[2]}\n📱 {result[0]}")
                else:
                    send_telegram(chat_id, f"❌ Не удалось найти телефон для записи #{appointment_id}")
            
            # Ответ на callback
            answer_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
            requests.post(answer_url, json={"callback_query_id": callback["id"]})
            
        return "OK"
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return "ERROR"

@app.route("/webhook_status")
def webhook_status():
    """Проверка статуса webhook"""
    webhook_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url=https://vetmanager-bot-1.onrender.com/webhook"
    
    return f'''
    <div style="font-family: Arial; padding: 20px;">
        <h2>🔗 Статус Webhook</h2>
        <p>Для работы кнопок в Telegram должен быть настроен webhook.</p>
        <p>Открой эту ссылку в браузере:</p>
        <p><a href="{webhook_url}" target="_blank">{webhook_url}</a></p>
        <p>Должно появиться: {{"ok":true,"result":true,"description":"Webhook was set"}}</p>
        <a href="/" class="btn">← На главную</a>
    </div>
    '''

# ============ 8. АВТОМАТИЧЕСКИЕ НАПОМИНАНИЯ ============
def auto_scheduler():
    """Автоматическая отправка напоминаний"""
    while True:
        now = datetime.now()
        
        # Ежедневно в 18:00
        if now.hour == 18 and now.minute == 0:
            print(f"🕕 {now.strftime('%H:%M')} - Отправка ежедневных напоминаний...")
            send_reminder_to_admin()
            time.sleep(61)
        
        time.sleep(30)

# ============ 9. ЗАПУСК ============
if __name__ == "__main__":
    # Инициализация базы
    init_db()
    
    # Запуск планировщика
    scheduler = threading.Thread(target=auto_scheduler, daemon=True)
    scheduler.start()
    
    print("=" * 70)
    print("🏥 ВЕТЕРИНАРНАЯ КЛИНИКА - СИСТЕМА НАПОМИНАНИЙ")
    print("=" * 70)
    print("✅ СИСТЕМА ЗАПУЩЕНА И РАБОТАЕТ АВТОНОМНО")
    print(f"👤 Администратор: {ADMIN_ID}")
    print("💾 База данных: vet_clinic.db")
    print("🤖 Telegram: @Fulsim_bot")
    print("=" * 70)
    print("🌐 Веб-интерфейс:")
    print("   https://vetmanager-bot-1.onrender.com/")
    print("   https://vetmanager-bot-1.onrender.com/remind")
    print("=" * 70)
    print("🎯 Основные функции:")
    print("   1. Добавление клиентов и записей")
    print("   2. Автоматические напоминания в 18:00")
    print("   3. Управление через кнопки в Telegram")
    print("   4. Тест рассылки клиентам")
    print("=" * 70)
    
    # Тестовое сообщение
    send_telegram(ADMIN_ID, "🏥 <b>Система напоминаний ветеринарной клиники запущена!</b>\n\n✅ Готова к работе.")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
