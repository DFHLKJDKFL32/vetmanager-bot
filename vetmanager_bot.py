from flask import Flask, request
import requests
from datetime import datetime, timedelta
import json
import threading
import time

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
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    if reply_markup:
        data["reply_markup"] = reply_markup
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")
        return False

# ============ 2. РЕАЛЬНЫЕ ЗАПИСИ ИЗ СКРИНШОТА ============
def get_tomorrow_appointments():
    """ВОЗВРАЩАЕМ РЕАЛЬНЫЕ ЗАПИСИ ИЗ СКРИНШОТА НА ЗАВТРА"""
    
    tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    # РЕАЛЬНЫЕ ЗАПИСИ ИЗ СКРИНШОТА:
    appointments = [
        # Врач Базарнов
        {
            "id": 1,
            "time": "08:00",
            "client": "Наталья Куликовская",
            "pet": "Чупа",
            "doctor": "Базарнов",
            "phone": "+7XXX-XXX-XX-XX",
            "comment": "без обслед, будет..."
        },
        {
            "id": 2,
            "time": "09:00",
            "client": "Галина Губанова", 
            "pet": "Бусинка",
            "doctor": "Базарнов",
            "phone": "+7XXX-XXX-XX-XX",
            "comment": "без обсл, будет..."
        },
        {
            "id": 3,
            "time": "09:15",
            "client": "Дарья Никитина",
            "pet": "Кетти",
            "doctor": "Базарнов",
            "phone": "+7XXX-XXX-XX-XX",
            "comment": ""
        },
        {
            "id": 4,
            "time": "09:30",
            "client": "Ольга Топольская",
            "pet": "Изида",
            "doctor": "Базарнов", 
            "phone": "+7XXX-XXX-XX-XX",
            "comment": ""
        },
        {
            "id": 5,
            "time": "09:45",
            "client": "Ольга Писанко",
            "pet": "Фил",
            "doctor": "Базарнов",
            "phone": "+7XXX-XXX-XX-XX",
            "comment": "без обслед, будут..."
        },
        {
            "id": 6,
            "time": "10:00",
            "client": "Виктор Максимов",
            "pet": "Котенок",
            "doctor": "Базарнов",
            "phone": "+7XXX-XXX-XX-XX",
            "comment": "две стерилки+1 кастрация выше+уд зубов..."
        },
        
        # Врач Олексин
        {
            "id": 7, 
            "time": "09:00",
            "client": "Алена Бут",
            "pet": "Леди",
            "doctor": "Олексин",
            "phone": "+7XXX-XXX-XX-XX",
            "comment": ""
        },
        {
            "id": 8,
            "time": "12:00", 
            "client": "Елена Зинченко",
            "pet": "Спартак",
            "doctor": "Олексин",
            "phone": "+7XXX-XXX-XX-XX",
            "comment": "будет, у обоих животных будто лихорадка..."
        },
        {
            "id": 9,
            "time": "12:30",
            "client": "Елена Зинченко",
            "pet": "Форти", 
            "doctor": "Олексин",
            "phone": "+7XXX-XXX-XX-XX",
            "comment": "будет..."
        },
        {
            "id": 10,
            "time": "13:30",
            "client": "Дмитриенко",
            "pet": "Гера",
            "doctor": "Олексин",
            "phone": "+7XXX-XXX-XX-XX",
            "comment": ""
        },
        {
            "id": 11,
            "time": "14:00",
            "client": "Тигра",
            "pet": "питомец",
            "doctor": "Олексин",
            "phone": "+7XXX-XXX-XX-XX", 
            "comment": ""
        },
        {
            "id": 12,
            "time": "15:00",
            "client": "Лист",
            "pet": "питомец",
            "doctor": "Олексин",
            "phone": "+7XXX-XXX-XX-XX",
            "comment": ""
        }
    ]
    
    # Добавляем дату завтра к каждой записи
    for app in appointments:
        app["date"] = tomorrow_date
    
    return appointments

# ============ 3. ФОРМАТИРОВАНИЕ СООБЩЕНИЙ ============
def format_admin_summary(appointments):
    """Сводка для администратора"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    message = f"📅 <b>НА ЗАВТРА {tomorrow}</b>\n"
    message += f"<i>Обнаружено {len(appointments)} записей</i>\n\n"
    
    # Группируем по врачам
    doctors = {}
    for app in appointments:
        doctor = app["doctor"]
        if doctor not in doctors:
            doctors[doctor] = []
        doctors[doctor].append(app)
    
    for doctor, apps in doctors.items():
        message += f"👨‍⚕️ <b>{doctor}:</b> {len(apps)} записей\n"
        for app in apps:
            message += f"   🕒 {app['time']} - {app['client']} ({app['pet']})\n"
        message += "\n"
    
    message += "🔔 <b>Напоминания будут отправлены клиентам:</b>\n"
    message += "   🕕 18:00 - Напоминание за день\n"
    message += "   🕙 10:00 - Напоминание за 1 час\n\n"
    
    message += "📊 <i>Отслеживайте подтверждения в реальном времени</i>"
    
    return message

def format_client_reminder(appointment):
    """Напоминание для клиента"""
    message = f"🐾 <b>Напоминание о визите к ветеринару</b>\n\n"
    message += f"📅 <b>Дата:</b> {appointment['date']}\n"
    message += f"🕒 <b>Время:</b> {appointment['time']}\n" 
    message += f"👨‍⚕️ <b>Врач:</b> {appointment['doctor']}\n"
    message += f"🐶 <b>Питомец:</b> {appointment['pet']}\n"
    
    if appointment['comment']:
        message += f"📝 <b>Примечание:</b> {appointment['comment']}\n"
    
    message += f"\n<i>Пожалуйста, подтвердите, что придёте:</i>"
    
    return message

# ============ 4. КНОПКИ ДЛЯ ПОДТВЕРЖДЕНИЯ ============
def get_client_buttons(appointment_id):
    """Кнопки для клиента"""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Да, приду", "callback_data": f"yes_{appointment_id}"},
                {"text": "❌ Не смогу", "callback_data": f"no_{appointment_id}"}
            ],
            [
                {"text": "📞 Перенести время", "callback_data": f"reschedule_{appointment_id}"},
                {"text": "ℹ️ Инфо о клинике", "callback_data": f"info_{appointment_id}"}
            ]
        ]
    }

def get_admin_buttons(appointment_id):
    """Кнопки для администратора"""
    return {
        "inline_keyboard": [
            [
                {"text": "📞 Позвонить", "callback_data": f"call_{appointment_id}"},
                {"text": "✅ Подтв.", "callback_data": f"confirm_{appointment_id}"}
            ],
            [
                {"text": "❌ Отмена", "callback_data": f"cancel_{appointment_id}"},
                {"text": "✏️ Изм.", "callback_data": f"edit_{appointment_id}"}
            ]
        ]
    }

# ============ 5. ОСНОВНЫЕ ФУНКЦИИ ============
def send_daily_report_to_admin():
    """Отправить ежедневный отчёт администратору"""
    appointments = get_tomorrow_appointments()
    
    if not appointments:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
        send_telegram(ADMIN_ID, f"📭 На завтра ({tomorrow}) нет записей")
        return "📭 Нет записей на завтра"
    
    # Отправляем общую сводку
    summary = format_admin_summary(appointments)
    send_telegram(ADMIN_ID, summary)
    
    # Отправляем каждую запись отдельно с кнопками
    for appointment in appointments:
        message = f"📋 <b>Запись #{appointment['id']}</b>\n"
        message += f"👤 <b>Клиент:</b> {appointment['client']}\n"
        message += f"📞 <b>Телефон:</b> {appointment['phone']}\n"
        message += f"🕒 <b>Время:</b> {appointment['time']}\n"
        message += f"👨‍⚕️ <b>Врач:</b> {appointment['doctor']}\n"
        message += f"🐾 <b>Питомец:</b> {appointment['pet']}\n"
        
        if appointment['comment']:
            message += f"📝 <b>Комментарий:</b> {appointment['comment']}\n"
        
        message += f"\n<b>Статус:</b> ⏳ Ожидает подтверждения"
        
        buttons = get_admin_buttons(appointment['id'])
        send_telegram(ADMIN_ID, message, buttons)
    
    # Тестовая отправка "клиенту" (на самом деле тебе)
    test_appointment = appointments[0]
    client_message = format_client_reminder(test_appointment)
    client_buttons = get_client_buttons(test_appointment['id'])
    send_telegram(ADMIN_ID, f"👤 <b>ТЕСТ:</b> Сообщение для клиента {test_appointment['client']}\n\n{client_message}", client_buttons)
    
    return f"✅ Отчёт отправлен! Записей: {len(appointments)}"

def send_test_to_clients():
    """Тестовая отправка всем клиентам (симуляция)"""
    appointments = get_tomorrow_appointments()
    
    if not appointments:
        return "❌ Нет записей для тестирования"
    
    message = f"🤖 <b>ТЕСТ РАССЫЛКИ КЛИЕНТАМ</b>\n\n"
    message += f"📅 Дата: {(datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')}\n"
    message += f"👥 Клиентов: {len(appointments)}\n\n"
    message += "<b>Список клиентов:</b>\n"
    
    for i, app in enumerate(appointments, 1):
        message += f"{i}. {app['client']} - {app['time']} ({app['doctor']})\n"
    
    message += f"\n<i>В реальной работе клиенты получат:\n"
    message += f"1. Напоминание за день (18:00)\n"
    message += f"2. Напоминание за час (за 1 час до визита)\n"
    message += f"3. Кнопки для подтверждения</i>"
    
    send_telegram(ADMIN_ID, message)
    
    # Отправляем тестовое сообщение "клиенту"
    for i, appointment in enumerate(appointments[:3], 1):  # Первые 3 для теста
        client_message = format_client_reminder(appointment)
        client_buttons = get_client_buttons(appointment['id'])
        
        test_message = f"👤 <b>ТЕСТ #{i}:</b> Клиент {appointment['client']}\n\n{client_message}"
        send_telegram(ADMIN_ID, test_message, client_buttons)
        time.sleep(1)  # Пауза между сообщениями
    
    return f"✅ Тест рассылки завершён! Протестировано: 3 клиента"

# ============ 6. ОБРАБОТКА КНОПОК ============
@app.route("/webhook", methods=["POST"])
def webhook():
    """Webhook для обработки кнопок Telegram"""
    try:
        data = request.json
        
        if "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["from"]["id"]
            callback_data = callback["data"]
            
            print(f"📲 Получен callback: {callback_data} от chat_id: {chat_id}")
            
            # Обработка нажатий
            if callback_data.startswith("yes_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"✅ Отлично! Ждём вас завтра.\n\n<i>Не забудьте взять с собой паспорт питомца</i>")
                
                # Уведомление администратору
                appointments = get_tomorrow_appointments()
                appointment = next((a for a in appointments if str(a['id']) == appointment_id), None)
                if appointment:
                    send_telegram(ADMIN_ID, f"✅ <b>КЛИЕНТ ПОДТВЕРДИЛ</b>\n\n👤 {appointment['client']}\n🕒 {appointment['time']}\n👨‍⚕️ {appointment['doctor']}")
            
            elif callback_data.startswith("no_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"❌ Жаль, что вы не сможете прийти.\n\n📞 Пожалуйста, свяжитесь с клиникой для переноса:\n+7 (XXX) XXX-XX-XX")
                
                # СРОЧНОЕ уведомление администратору
                appointments = get_tomorrow_appointments()
                appointment = next((a for a in appointments if str(a['id']) == appointment_id), None)
                if appointment:
                    send_telegram(ADMIN_ID, f"🚨 <b>СРОЧНО! КЛИЕНТ НЕ ПРИДЁТ</b>\n\n👤 {appointment['client']}\n🕒 {appointment['time']}\n👨‍⚕️ {appointment['doctor']}\n📞 {appointment['phone']}")
            
            elif callback_data.startswith("reschedule_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"📅 Для переноса записи позвоните:\n\n📱 +7 (XXX) XXX-XX-XX\n🕒 8:00 - 20:00")
            
            elif callback_data.startswith("info_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"🏥 <b>Ветеринарная клиника</b>\n\n📍 Адрес: ул. Примерная, д. 1\n📱 Телефон: +7 (XXX) XXX-XX-XX\n🕒 Часы работы: 8:00-20:00\n🚗 Парковка: бесплатная")
            
            elif callback_data.startswith("call_"):
                appointment_id = callback_data.split("_")[1]
                appointments = get_tomorrow_appointments()
                appointment = next((a for a in appointments if str(a['id']) == appointment_id), None)
                if appointment:
                    send_telegram(ADMIN_ID, f"📞 <b>ДАННЫЕ ДЛЯ ЗВОНКА</b>\n\n👤 {appointment['client']}\n📱 {appointment['phone']}\n🕒 Лучшее время: {appointment['time']}\n🐾 {appointment['pet']}")
            
            elif callback_data.startswith("confirm_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(ADMIN_ID, f"✅ Запись #{appointment_id} отмечена как подтверждённая администратором")
            
            elif callback_data.startswith("cancel_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(ADMIN_ID, f"❌ Запись #{appointment_id} отменена администратором")
            
            # Ответ на callback query (убираем часики загрузки)
            answer_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
            requests.post(answer_url, json={"callback_query_id": callback["id"]})
            
        return "OK"
    except Exception as e:
        print(f"❌ Ошибка в webhook: {e}")
        return "ERROR", 500

# ============ 7. ВЕБ-ИНТЕРФЕЙС ============
@app.route("/")
def home():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>VetManager Smart Bot</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #2c3e50; }}
            .card {{ background: #f8f9fa; border-radius: 10px; padding: 20px; margin: 15px 0; border-left: 4px solid #3498db; }}
            .btn {{ display: inline-block; background: #3498db; color: white; padding: 12px 24px; 
                   text-decoration: none; border-radius: 5px; margin: 5px; font-weight: bold; }}
            .btn:hover {{ background: #2980b9; transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
            .btn-success {{ background: #27ae60; }}
            .btn-success:hover {{ background: #219653; }}
            .btn-warning {{ background: #f39c12; }}
            .btn-warning:hover {{ background: #e67e22; }}
            .doctor {{ color: #e74c3c; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>🤖 VetManager Smart Reminder Bot</h1>
        
        <div class="card">
            <h2>📅 Завтра: {tomorrow}</h2>
            <p><b>Режим:</b> 🧪 Тестирование с реальными данными</p>
            <p><b>Записей на завтра:</b> 12 (из скриншота)</p>
            <p><b>Врачи:</b> <span class="doctor">Базарнов</span> и <span class="doctor">Олексин</span></p>
            <p><b>Администратор:</b> ID {ADMIN_ID}</p>
        </div>
        
        <div class="card">
            <h3>🎯 Тестирование функций</h3>
            <a class="btn btn-success" href="/remind">📊 Отчёт администратору</a><br><br>
            <a class="btn" href="/test_clients">👥 Тест рассылки клиентам</a><br><br>
            <a class="btn" href="/setup_webhook">🔗 Настройка Webhook</a><br><br>
            <a class="btn btn-warning" href="/simulate_calls">📞 Тест звонков</a>
        </div>
        
        <div class="card">
            <h3>📋 Реальные записи на завтра:</h3>
            <p><b>Базарнов:</b> 6 записей (08:00-10:00)</p>
            <p><b>Олексин:</b> 6 записей (09:00-15:00)</p>
            <p><b>Клиенты:</b> Дарья Никитина, Галина Губанова, Елена Зинченко и др.</p>
        </div>
        
        <div class="card">
            <h3>🔧 Как работает:</h3>
            <p>1. <b>18:00</b> - Отправляет тебе сводку на завтра</p>
            <p>2. <b>Клиенты</b> - Получают напоминания с кнопками</p>
            <p>3. <b>Ответы</b> - Обрабатываются автоматически</p>
            <p>4. <b>Администратор</b> - Получает уведомления о проблемах</p>
        </div>
    </body>
    </html>
    '''

@app.route("/remind")
def remind():
    return send_daily_report_to_admin()

@app.route("/test_clients")
def test_clients():
    return send_test_to_clients()

@app.route("/setup_webhook")
def setup_webhook():
    """Настройка Webhook Telegram"""
    webhook_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url=https://vetmanager-bot-1.onrender.com/webhook"
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head><style>body {{ font-family: Arial; padding: 20px; }}</style></head>
    <body>
        <h2>🔗 Настройка Telegram Webhook</h2>
        <p>1. Открой эту ссылку в браузере:</p>
        <p><a href="{webhook_url}" target="_blank">{webhook_url[:50]}...</a></p>
        
        <p>2. Должно появиться:</p>
        <pre>{{"ok":true,"result":true,"description":"Webhook was set"}}</pre>
        
        <p>3. После этого кнопки в Telegram будут работать!</p>
        
        <br>
        <a href="/">← Назад</a>
    </body>
    </html>
    '''

@app.route("/simulate_calls")
def simulate_calls():
    """Симуляция работы с клиентами"""
    appointments = get_tomorrow_appointments()
    
    html = "<h2>📞 Симуляция работы с клиентами</h2>"
    html += "<div class='card'>"
    
    for appointment in appointments[:5]:
        html += f"""
        <div style='border: 1px solid #ddd; padding: 10px; margin: 10px 0; border-radius: 5px;'>
            <b>{appointment['time']} - {appointment['client']}</b><br>
            Питомец: {appointment['pet']} | Врач: {appointment['doctor']}<br>
            Телефон: {appointment['phone']}<br>
            <button onclick='alert("Звонок {appointment['client']}")'>📞 Позвонить</button>
            <button onclick='alert("Подтверждено")'>✅ Подтвердить</button>
        </div>
        """
    
    html += "</div>"
    html += '<a href="/" class="btn">← Назад</a>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            .card {{ background: #f8f9fa; padding: 20px; }}
            button {{ background: #3498db; color: white; border: none; padding: 5px 10px; margin: 2px; cursor: pointer; }}
        </style>
    </head>
    <body>
        {html}
    </body>
    </html>
    '''

# ============ 8. АВТОМАТИЧЕСКИЕ НАПОМИНАНИЯ ============
def auto_scheduler():
    """Планировщик автоматических напоминаний"""
    while True:
        now = datetime.now()
        
        # Каждый день в 18:00 - отчёт администратору
        if now.hour == 18 and now.minute == 0:
            print(f"🕕 {now.strftime('%H:%M')} - Отправляю отчёт администратору...")
            send_daily_report_to_admin()
            time.sleep(61)  # Ждём минуту
        
        time.sleep(30)

# Запускаем планировщик в отдельном потоке
scheduler = threading.Thread(target=auto_scheduler, daemon=True)
scheduler.start()

# ============ 9. ЗАПУСК СЕРВЕРА ============
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 VETMANAGER SMART BOT ЗАПУЩЕН!")
    print("=" * 60)
    print("🎯 РЕЖИМ: ТЕСТИРОВАНИЕ С РЕАЛЬНЫМИ ДАННЫМИ")
    print(f"👤 Администратор: {ADMIN_ID}")
    print("📅 Тестовые записи на завтра: 12")
    print("👨‍⚕️ Врачи: Базарнов (6 записей), Олексин (6 записей)")
    print("=" * 60)
    print("🌐 Веб-интерфейс:")
    print("   https://vetmanager-bot-1.onrender.com/")
    print("   https://vetmanager-bot-1.onrender.com/remind")
    print("=" * 60)
    print("🔗 Для работы кнопок настройте Webhook:")
    print("   https://vetmanager-bot-1.onrender.com/setup_webhook")
    print("=" * 60)
    
    # Тестовый запуск при старте
    print("\n🚀 Отправляю тестовый отчёт...")
    send_telegram(ADMIN_ID, "🤖 <b>Бот перезапущен!</b>\n\nСистема готова к тестированию напоминаний.")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
