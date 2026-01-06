from flask import Flask, request
import requests
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# ============ ТВОИ КЛЮЧИ ============
TELEGRAM_TOKEN = "8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI"
VETMANAGER_KEY = "29607ccc63c684fa672be9694f7f09ec"
ADMIN_ID = "921853682"

# ============ 1. ОТПРАВКА В TELEGRAM ============
def send_telegram(chat_id, message, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    if reply_markup:
        data["reply_markup"] = reply_markup
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except:
        return False

# ============ 2. СИМУЛЯЦИЯ РЕАЛЬНЫХ ЗАПИСЕЙ ============
def get_real_appointments():
    """Создаем тестовые записи как на скриншоте"""
    
    # Реальные записи из скриншота
    appointments = [
        # Врач Базарнов
        {
            "id": 1,
            "time": "08:00",
            "client": "Клиент ID:0",
            "pet": "undefined_пусто",
            "doctor": "Базарнов",
            "comment": "Комментарий:"
        },
        {
            "id": 2,
            "time": "09:00",
            "client": "два 15 Челка",
            "pet": "питомец",
            "doctor": "Базарнов",
            "comment": "Кошки 6-7 мес"
        },
        {
            "id": 3,
            "time": "09:30",
            "client": "Бусилка",
            "pet": "питомец",
            "doctor": "Базарнов",
            "comment": ""
        },
        {
            "id": 4,
            "time": "09:45",
            "client": "Остаток",
            "pet": "питомец",
            "doctor": "Базарнов",
            "comment": ""
        },
        {
            "id": 5,
            "time": "10:00",
            "client": "Клиент ID:5",
            "pet": "undefined",
            "doctor": "Базарнов",
            "comment": "Реферальный комментарий: две стерилки + 1 кастрация выше"
        },
        
        # Врач Олексин
        {
            "id": 6,
            "time": "08:00",
            "client": "Клиент ID:0",
            "pet": "undefined_пусто",
            "doctor": "Олексин",
            "comment": "Комментарий:"
        },
        {
            "id": 7,
            "time": "09:00",
            "client": "Дарья Никитина",
            "pet": "Кетти",
            "doctor": "Олексин",
            "comment": "Когти"
        },
        {
            "id": 8,
            "time": "09:30",
            "client": "Ольга Топольская",
            "pet": "Исида",
            "doctor": "Олексин",
            "comment": ""
        },
        {
            "id": 9,
            "time": "10:00",
            "client": "Виктор Максимов",
            "pet": "Котенок",
            "doctor": "Олексин",
            "comment": ""
        },
        {
            "id": 10,
            "time": "10:30",
            "client": "Алена Бут",
            "pet": "Леди",
            "doctor": "Олексин",
            "comment": ""
        },
        {
            "id": 11,
            "time": "12:00",
            "client": "Елена Зинченко",
            "pet": "Спартак",
            "doctor": "Олексин",
            "comment": ""
        },
        {
            "id": 12,
            "time": "12:30",
            "client": "Елена Зинченко",
            "pet": "Форти",
            "doctor": "Олексин",
            "comment": ""
        },
        {
            "id": 13,
            "time": "13:00",
            "client": "Клиент ID:0",
            "pet": "undefined_ОБЕД",
            "doctor": "Олексин",
            "comment": ""
        },
        {
            "id": 14,
            "time": "13:30",
            "client": "Дмитриенко",
            "pet": "Гера",
            "doctor": "Олексин",
            "comment": ""
        },
        {
            "id": 15,
            "time": "14:00",
            "client": "Тигра",
            "pet": "питомец",
            "doctor": "Олексин",
            "comment": ""
        },
        {
            "id": 16,
            "time": "14:00",
            "client": "Дает",
            "pet": "питомец",
            "doctor": "Олексин",
            "comment": ""
        },
        {
            "id": 17,
            "time": "15:00",
            "client": "Лист",
            "pet": "питомец",
            "doctor": "Олексин",
            "comment": ""
        },
        {
            "id": 18,
            "time": "15:30",
            "client": "Клиент ID:0",
            "pet": "undefined_УБОРКА",
            "doctor": "Олексин",
            "comment": ""
        }
    ]
    
    # Фильтруем только реальные записи (не служебные)
    real_appointments = []
    for app in appointments:
        # Пропускаем служебные записи
        if "undefined" in app["pet"].lower() or "обед" in app["pet"].lower() or "уборка" in app["pet"].lower():
            continue
            
        # Пропускаем записи без имени клиента
        if app["client"].startswith("Клиент ID:"):
            continue
            
        real_appointments.append(app)
    
    return real_appointments

# ============ 3. ФОРМАТИРОВАНИЕ СООБЩЕНИЯ ============
def format_appointment_for_admin(appointment):
    """Форматирование для администратора"""
    msg = f"📋 <b>Запись #{appointment['id']}</b>\n"
    msg += f"👨‍⚕️ Врач: {appointment['doctor']}\n"
    msg += f"🕒 Время: {appointment['time']}\n"
    msg += f"👤 Клиент: {appointment['client']}\n"
    msg += f"🐾 Питомец: {appointment['pet']}\n"
    
    if appointment['comment']:
        msg += f"📝 Комментарий: {appointment['comment']}\n"
    
    msg += f"\n<b>Статус:</b> ⏳ Ожидает подтверждения"
    
    return msg

def format_appointment_for_client(appointment):
    """Форматирование для клиента"""
    msg = f"🐾 <b>Напоминание о визите в ветеринарную клинику</b>\n\n"
    msg += f"🕒 <b>Время:</b> {appointment['time']}\n"
    msg += f"👨‍⚕️ <b>Врач:</b> {appointment['doctor']}\n"
    msg += f"🐶 <b>Питомец:</b> {appointment['pet']}\n\n"
    
    msg += f"<i>Пожалуйста, подтвердите визит:</i>"
    
    return msg

# ============ 4. КНОПКИ ДЛЯ ПОДТВЕРЖДЕНИЯ ============
def get_confirmation_buttons(appointment_id):
    """Создать кнопки подтверждения"""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Подтвердить", "callback_data": f"confirm_{appointment_id}"},
                {"text": "❌ Отменить", "callback_data": f"cancel_{appointment_id}"}
            ],
            [
                {"text": "📞 Связаться с клиникой", "callback_data": f"contact_{appointment_id}"}
            ]
        ]
    }

def get_admin_buttons(appointment_id):
    """Кнопки для администратора"""
    return {
        "inline_keyboard": [
            [
                {"text": "📞 Позвонить клиенту", "callback_data": f"admin_call_{appointment_id}"},
                {"text": "✅ Подтверждено", "callback_data": f"admin_confirm_{appointment_id}"}
            ],
            [
                {"text": "❌ Отменено", "callback_data": f"admin_cancel_{appointment_id}"},
                {"text": "✏️ Изменить время", "callback_data": f"admin_reschedule_{appointment_id}"}
            ]
        ]
    }

# ============ 5. ОСНОВНАЯ ФУНКЦИЯ НАПОМИНАНИЙ ============
def send_reminders_to_admin():
    """Отправить все завтрашние записи администратору (тебе)"""
    appointments = get_real_appointments()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    if not appointments:
        send_telegram(ADMIN_ID, f"📭 На завтра ({tomorrow}) нет записей")
        return "📭 Нет записей"
    
    # Сначала общее сообщение
    message = f"📅 <b>НАПОМИНАНИЕ! Завтра {tomorrow}</b>\n"
    message += f"<i>Всего записей: {len(appointments)}</i>\n\n"
    message += f"<b>Врачи с записями:</b>\n"
    
    # Группируем по врачам
    doctors = {}
    for app in appointments:
        doctor = app["doctor"]
        if doctor not in doctors:
            doctors[doctor] = []
        doctors[doctor].append(app)
    
    for doctor, apps in doctors.items():
        message += f"👨‍⚕️ {doctor}: {len(apps)} записей\n"
    
    message += f"\n<b>Список всех записей:</b>\n"
    
    for i, app in enumerate(appointments, 1):
        message += f"{i}. {app['time']} - {app['client']} ({app['pet']})\n"
    
    message += f"\n<b>Нужно подтвердить: {len(appointments)} записей</b>"
    message += f"\n<i>Бот будет отправлять клиентам напоминания в 18:00 и 10:00</i>"
    
    send_telegram(ADMIN_ID, message)
    
    # Теперь отправляем каждую запись отдельно с кнопками
    for appointment in appointments:
        admin_message = format_appointment_for_admin(appointment)
        buttons = get_admin_buttons(appointment['id'])
        send_telegram(ADMIN_ID, admin_message, buttons)
    
    return f"✅ Отправлено администратору! Записей: {len(appointments)}"

def simulate_client_notification(appointment):
    """Симуляция отправки клиенту (пока отправляем тебе)"""
    message = f"👤 <b>Сообщение для клиента:</b> {appointment['client']}\n\n"
    message += format_appointment_for_client(appointment)
    
    buttons = get_confirmation_buttons(appointment['id'])
    
    # В реальности отправляем клиенту, пока отправляем тебе
    send_telegram(ADMIN_ID, message, buttons)
    return True

# ============ 6. ОБРАБОТКА КНОПОК ============
def handle_callback(data, chat_id):
    """Обработка нажатий кнопок"""
    if data.startswith("confirm_"):
        appointment_id = data.split("_")[1]
        send_telegram(chat_id, f"✅ Вы подтвердили запись #{appointment_id}\n\n<i>Ждём вас в указанное время!</i>")
        
        # Уведомляем администратора
        send_telegram(ADMIN_ID, f"✅ Клиент подтвердил запись #{appointment_id}")
        
    elif data.startswith("cancel_"):
        appointment_id = data.split("_")[1]
        send_telegram(chat_id, f"❌ Вы отменили запись #{appointment_id}\n\n📞 Свяжитесь с клиникой по телефону: +7 (XXX) XXX-XX-XX")
        
        # Уведомляем администратора
        send_telegram(ADMIN_ID, f"🚨 ВНИМАНИЕ! Клиент отменил запись #{appointment_id}\n\n📞 Нужно позвонить клиенту!")
        
    elif data.startswith("contact_"):
        appointment_id = data.split("_")[1]
        send_telegram(chat_id, f"📞 Контакты клиники:\n\n🏥 Ветеринарная клиника\n📱 +7 (XXX) XXX-XX-XX\n📍 Адрес: [адрес клиники]\n🕒 Работаем: 8:00 - 20:00")
    
    elif data.startswith("admin_call_"):
        appointment_id = data.split("_")[2]
        # Находим запись
        appointments = get_real_appointments()
        appointment = next((a for a in appointments if str(a['id']) == appointment_id), None)
        
        if appointment:
            send_telegram(ADMIN_ID, f"📞 <b>Информация для звонка:</b>\n\n👤 Клиент: {appointment['client']}\n🕒 Время: {appointment['time']}\n🐾 Питомец: {appointment['pet']}")
    
    elif data.startswith("admin_confirm_"):
        appointment_id = data.split("_")[2]
        send_telegram(ADMIN_ID, f"✅ Запись #{appointment_id} отмечена как подтверждённая")
    
    elif data.startswith("admin_cancel_"):
        appointment_id = data.split("_")[2]
        send_telegram(ADMIN_ID, f"❌ Запись #{appointment_id} отменена администратором")
    
    elif data.startswith("admin_reschedule_"):
        appointment_id = data.split("_")[2]
        send_telegram(ADMIN_ID, f"✏️ Нужно изменить время для записи #{appointment_id}")

# ============ 7. ВЕБ-ИНТЕРФЕЙС И TELEGRAM WEBHOOK ============
@app.route("/")
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>VetManager Smart Bot</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #2c3e50; }
            .card { background: #f8f9fa; border-radius: 10px; padding: 20px; margin: 15px 0; }
            .btn { display: inline-block; background: #3498db; color: white; padding: 10px 20px; 
                   text-decoration: none; border-radius: 5px; margin: 5px; }
            .btn:hover { background: #2980b9; }
            .btn-success { background: #27ae60; }
            .btn-success:hover { background: #219653; }
        </style>
    </head>
    <body>
        <h1>🤖 VetManager Smart Reminder Bot</h1>
        <div class="card">
            <h3>🎯 Режим тестирования (администратор)</h3>
            <p><b>Статус:</b> ✅ Работает</p>
            <p><b>Тестовые записи:</b> 10 реальных записей</p>
            <p><b>Врачи:</b> Базарнов, Олексин</p>
        </div>
        
        <div class="card">
            <h3>📋 Команды для тестирования</h3>
            <a class="btn btn-success" href="/remind">/remind</a> - Отправить все записи (админу)<br><br>
            <a class="btn" href="/test_client">/test_client</a> - Тест уведомления клиенту<br><br>
            <a class="btn" href="/send_all">/send_all</a> - Отправить всем клиентам (симуляция)<br><br>
            <a class="btn" href="/schedule">/schedule</a> - Расписание напоминаний
        </div>
        
        <div class="card">
            <h3>🔧 Как работает бот</h3>
            <p>1. Находит записи на завтра</p>
            <p>2. Отправляет тебе список</p>
            <p>3. Симулирует отправку клиентам</p>
            <p>4. Обрабатывает ответы кнопками</p>
            <p>5. Уведомляет о проблемах</p>
        </div>
    </body>
    </html>
    '''

@app.route("/remind")
def remind():
    return send_reminders_to_admin()

@app.route("/test_client")
def test_client():
    """Тест отправки уведомления клиенту"""
    appointments = get_real_appointments()
    if appointments:
        simulate_client_notification(appointments[0])
        return f"✅ Тестовое уведомление отправлено (клиент: {appointments[0]['client']})"
    return "❌ Нет записей для тестирования"

@app.route("/send_all")
def send_all():
    """Симуляция отправки всем клиентам"""
    appointments = get_real_appointments()
    
    if not appointments:
        return "❌ Нет записей для отправки"
    
    for appointment in appointments:
        simulate_client_notification(appointment)
    
    return f"✅ Симуляция завершена! Отправлено: {len(appointments)} клиентам"

@app.route("/schedule")
def schedule():
    """Показать расписание напоминаний"""
    html = "<h2>⏰ Расписание напоминаний</h2>"
    html += "<div class='card'>"
    html += "<h3>Для клиентов:</h3>"
    html += "<p>🕕 <b>18:00</b> - Напоминание за день до визита</p>"
    html += "<p>🕙 <b>10:00</b> - Напоминание в день визита (утро)</p>"
    html += "<p>🕐 <b>13:00</b> - Напоминание за 2 часа до визита</p>"
    html += "</div>"
    
    html += "<div class='card'>"
    html += "<h3>Для администратора:</h3>"
    html += "<p>🕖 <b>17:00</b> - Сводка на завтра</p>"
    html += "<p>🕘 <b>09:00</b> - Статус подтверждений</p>"
    html += "<p>🕜 <b>13:30</b> - Список неподтверждённых</p>"
    html += "</div>"
    
    html += '<a href="/" class="btn">← На главную</a>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            .card {{ background: #f8f9fa; border-radius: 10px; padding: 20px; margin: 15px 0; }}
            .btn {{ display: inline-block; background: #3498db; color: white; padding: 10px 20px; 
                   text-decoration: none; border-radius: 5px; margin: 5px; }}
        </style>
    </head>
    <body>
        {html}
    </body>
    </html>
    '''

@app.route("/webhook", methods=["POST"])
def webhook():
    """Webhook для Telegram (для кнопок)"""
    try:
        data = request.json
        print(f"Webhook data: {data}")
        
        if "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["from"]["id"]
            callback_data = callback["data"]
            
            handle_callback(callback_data, chat_id)
            
            # Ответ на callback (убираем часики)
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery", 
                         json={"callback_query_id": callback["id"]})
            
        return "OK"
    except Exception as e:
        print(f"Webhook error: {e}")
        return "ERROR"

# ============ 8. АВТОМАТИЧЕСКИЕ НАПОМИНАНИЯ ============
import threading
import time

def auto_reminder():
    """Автоматическая отправка напоминаний"""
    while True:
        now = datetime.now()
        
        # Каждый день в 18:00 - отправляем напоминания на завтра
        if now.hour == 18 and now.minute == 0:
            print(f"🕕 {now.strftime('%H:%M')} - Отправляю напоминания на завтра...")
            send_reminders_to_admin()
            time.sleep(61)
        
        # Каждый день в 10:00 - утренние напоминания
        elif now.hour == 10 and now.minute == 0:
            print(f"🕙 {now.strftime('%H:%M')} - Утренние напоминания...")
            # Здесь будет отправка клиентам
            
        time.sleep(30)

# Запускаем планировщик
scheduler = threading.Thread(target=auto_reminder, daemon=True)
scheduler.start()

# ============ 9. ЗАПУСК СЕРВЕРА ============
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 SMART VETMANAGER BOT ЗАПУЩЕН!")
    print("=" * 60)
    print("🎯 РЕЖИМ: ТЕСТИРОВАНИЕ")
    print(f"👤 Администратор: {ADMIN_ID}")
    print("📊 Тестовых записей: 10")
    print("👨‍⚕️ Врачи: Базарнов, Олексин")
    print("=" * 60)
    print("🌐 Веб-интерфейс:")
    print("   https://vetmanager-bot-1.onrender.com/")
    print("   https://vetmanager-bot-1.onrender.com/remind")
    print("=" * 60)
    print("📱 Telegram Webhook:")
    print("   https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook")
    print("   URL: https://vetmanager-bot-1.onrender.com/webhook")
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=5000, debug=False)
