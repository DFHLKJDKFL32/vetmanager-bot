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

# ============ 1. ПОЛУЧЕНИЕ РЕАЛЬНЫХ ДАННЫХ ИЗ VETMANAGER ============
def get_real_vetmanager_appointments():
    """Получаем НАСТОЯЩИЕ записи из VetManager API"""
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    # Получаем побольше записей
    all_appointments = []
    
    try:
        # Пробуем разные лимиты
        for limit in [100, 200, 500]:
            params = {"limit": limit, "active": 1}
            print(f"🔍 Запрос записей с limit={limit}...")
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success"):
                    appointments = data.get("data", {}).get("admission", [])
                    print(f"✅ Получено {len(appointments)} записей с limit={limit}")
                    all_appointments.extend(appointments)
                    
                    if len(appointments) < limit:
                        break  # Получили все записи
                else:
                    error_msg = data.get('error', {}).get('message', 'Unknown error')
                    print(f"❌ VetManager API ошибка: {error_msg}")
            else:
                print(f"❌ HTTP ошибка {response.status_code}")
                
    except Exception as e:
        print(f"❌ Ошибка при получении данных: {e}")
        return []
    
    return all_appointments

def get_appointments_for_date(target_date):
    """Получить записи на конкретную дату"""
    appointments = get_real_vetmanager_appointments()
    target_date_str = target_date.strftime("%Y-%m-%d")
    
    filtered = []
    
    for app in appointments:
        admission_date = app.get("admission_date", "")
        if admission_date.startswith(target_date_str):
            filtered.append(app)
    
    print(f"📅 На дату {target_date_str} найдено: {len(filtered)} записей")
    return filtered

# ============ 2. ОТПРАВКА В TELEGRAM ============
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

# ============ 3. ФОРМАТИРОВАНИЕ РЕАЛЬНЫХ ДАННЫХ ============
def format_appointment(appointment, index):
    """Отформатировать реальную запись из VetManager"""
    # ID записи
    appointment_id = appointment.get("id", "?")
    
    # Дата и время
    admission_date = appointment.get("admission_date", "")
    if " " in admission_date:
        date_part, time_part = admission_date.split(" ")
        time = time_part[:5]
    else:
        time = "??:??"
    
    # Клиент
    client_data = appointment.get("client", {})
    client_id = appointment.get("client_id", "")
    first_name = client_data.get("first_name", "").strip()
    last_name = client_data.get("last_name", "").strip()
    
    if first_name or last_name:
        client_name = f"{first_name} {last_name}".strip()
    else:
        client_name = f"Клиент ID:{client_id}"
    
    # Телефон
    phone = client_data.get("cell_phone", "")
    if not phone:
        phone = client_data.get("phone", "Не указан")
    
    # Питомец
    pet_data = appointment.get("pet", {})
    pet_name = pet_data.get("alias", "").strip()
    if not pet_name:
        pet_name = pet_data.get("pet_name", "питомец")
    
    # Врач
    doctor_data = appointment.get("user", {})
    doctor_name = doctor_data.get("last_name", "").strip()
    if not doctor_name:
        doctor_name = doctor_data.get("login", "Врач")
    
    # Описание
    description = appointment.get("description", "").strip()
    
    # Формируем сообщение
    message = f"📋 <b>Запись #{index}</b> (ID: {appointment_id})\n"
    message += f"🕒 <b>Время:</b> {time}\n"
    message += f"👤 <b>Клиент:</b> {client_name}\n"
    
    if phone and phone != "Не указан":
        message += f"📞 <b>Телефон:</b> {phone}\n"
    
    message += f"🐾 <b>Питомец:</b> {pet_name}\n"
    message += f"👨‍⚕️ <b>Врач:</b> {doctor_name}\n"
    
    if description:
        if len(description) > 50:
            description = description[:50] + "..."
        message += f"📝 <b>Примечание:</b> {description}\n"
    
    message += f"\n<b>Статус:</b> ⏳ Ожидает подтверждения"
    
    return message, appointment_id

def format_admin_summary(appointments):
    """Сводка для администратора"""
    if not appointments:
        return "Нет записей"
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    message = f"📅 <b>РЕАЛЬНЫЕ ЗАПИСИ НА ЗАВТРА {tomorrow}</b>\n"
    message += f"<i>Всего записей из VetManager: {len(appointments)}</i>\n\n"
    
    # Группируем по врачам
    doctors = {}
    for app in appointments:
        doctor_data = app.get("user", {})
        doctor_name = doctor_data.get("last_name", "Неизвестный врач")
        
        if doctor_name not in doctors:
            doctors[doctor_name] = []
        doctors[doctor_name].append(app)
    
    for doctor, apps in doctors.items():
        message += f"👨‍⚕️ <b>{doctor}:</b> {len(apps)} записей\n"
    
    message += f"\n<b>Список клиентов:</b>\n"
    
    for i, app in enumerate(appointments[:15], 1):
        client_data = app.get("client", {})
        first_name = client_data.get("first_name", "")
        last_name = client_data.get("last_name", "")
        client_name = f"{first_name} {last_name}".strip()
        
        if not client_name:
            client_name = f"Клиент ID:{app.get('client_id')}"
        
        admission_date = app.get("admission_date", "")
        time = admission_date.split(" ")[1][:5] if " " in admission_date else "??:??"
        
        message += f"{i}. {time} - {client_name}\n"
    
    if len(appointments) > 15:
        message += f"\n... и ещё {len(appointments) - 15} записей"
    
    return message

# ============ 4. КНОПКИ ДЛЯ УПРАВЛЕНИЯ ============
def get_appointment_buttons(appointment_id, client_phone=""):
    """Кнопки для управления записью"""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Подтвердить", "callback_data": f"confirm_{appointment_id}"},
                {"text": "❌ Отменить", "callback_data": f"cancel_{appointment_id}"}
            ],
            [
                {"text": "📞 Позвонить", "callback_data": f"call_{appointment_id}"},
                {"text": "✏️ Изменить", "callback_data": f"edit_{appointment_id}"}
            ],
            [
                {"text": "👤 Инфо о клиенте", "callback_data": f"info_{appointment_id}"}
            ]
        ]
    }

# ============ 5. ОСНОВНЫЕ ФУНКЦИИ ============
def send_real_tomorrow_appointments():
    """Отправить РЕАЛЬНЫЕ записи на завтра из VetManager"""
    tomorrow = datetime.now() + timedelta(days=1)
    appointments = get_appointments_for_date(tomorrow)
    
    if not appointments:
        tomorrow_str = tomorrow.strftime("%d.%m.%Y")
        send_telegram(ADMIN_ID, f"📭 На завтра ({tomorrow_str}) нет записей в VetManager")
        return "📭 Нет записей"
    
    # Отправляем сводку
    summary = format_admin_summary(appointments)
    send_telegram(ADMIN_ID, summary)
    
    # Отправляем каждую запись отдельно с кнопками
    for i, appointment in enumerate(appointments, 1):
        message, appointment_id = format_appointment(appointment, i)
        buttons = get_appointment_buttons(appointment_id)
        send_telegram(ADMIN_ID, message, buttons)
    
    # Тестовое сообщение о работе с реальными данными
    test_message = f"✅ <b>РЕАЛЬНЫЕ ДАННЫЕ ИЗ VETMANAGER</b>\n\n"
    test_message += f"📊 Всего записей на завтра: {len(appointments)}\n"
    test_message += f"👥 Уникальных клиентов: {len(set([a.get('client_id') for a in appointments]))}\n"
    test_message += f"👨‍⚕️ Врачей с записями: {len(set([a.get('user', {}).get('last_name', '') for a in appointments]))}\n\n"
    test_message += f"<i>Данные получены напрямую из VetManager API</i>"
    
    send_telegram(ADMIN_ID, test_message)
    
    return f"✅ Отправлено! РЕАЛЬНЫХ записей: {len(appointments)}"

def test_vetmanager_connection():
    """Тест подключения к VetManager"""
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    params = {"limit": 5}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                appointments = data.get("data", {}).get("admission", [])
                
                message = f"🔗 <b>ТЕСТ ПОДКЛЮЧЕНИЯ К VETMANAGER</b>\n\n"
                message += f"✅ Подключение успешно\n"
                message += f"📊 Записей в системе: {len(appointments)}\n\n"
                
                if appointments:
                    message += f"<b>Последние записи:</b>\n"
                    for i, app in enumerate(appointments[:3], 1):
                        date_str = app.get("admission_date", "??")
                        client = app.get("client", {})
                        name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
                        if not name:
                            name = f"Клиент ID:{app.get('client_id')}"
                        
                        message += f"{i}. {date_str} - {name}\n"
            else:
                error = data.get('error', {}).get('message', 'Unknown error')
                message = f"❌ VetManager ошибка: {error}"
        else:
            message = f"❌ HTTP ошибка: {response.status_code}"
            
    except Exception as e:
        message = f"❌ Ошибка подключения: {str(e)}"
    
    send_telegram(ADMIN_ID, message)
    return message

# ============ 6. ОБРАБОТКА КНОПОК ============
@app.route("/webhook", methods=["POST"])
def webhook():
    """Webhook для обработки кнопок"""
    try:
        data = request.json
        
        if "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["from"]["id"]
            callback_data = callback["data"]
            
            print(f"📲 Callback: {callback_data}")
            
            # Обработка действий администратора
            if callback_data.startswith("confirm_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"✅ Запись #{appointment_id} подтверждена администратором")
                
            elif callback_data.startswith("cancel_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"❌ Запись #{appointment_id} отменена администратором")
                send_telegram(ADMIN_ID, f"🚨 <b>ВНИМАНИЕ!</b> Запись #{appointment_id} отменена!\nНужно позвонить клиенту.")
                
            elif callback_data.startswith("call_"):
                appointment_id = callback_data.split("_")[1]
                # Получаем данные о записи
                tomorrow = datetime.now() + timedelta(days=1)
                appointments = get_appointments_for_date(tomorrow)
                
                for app in appointments:
                    if str(app.get("id")) == appointment_id:
                        client = app.get("client", {})
                        phone = client.get("cell_phone", client.get("phone", "Не указан"))
                        name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
                        
                        send_telegram(chat_id, f"📞 <b>Данные для звонка:</b>\n\n👤 Клиент: {name}\n📱 Телефон: {phone}\n⏰ Лучшее время для звонка: сейчас")
                        break
                        
            elif callback_data.startswith("edit_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"✏️ Для изменения записи #{appointment_id} зайдите в VetManager")
                
            elif callback_data.startswith("info_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"👤 Информация о записи #{appointment_id} будет загружена...")
            
            # Ответ на callback
            answer_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
            requests.post(answer_url, json={"callback_query_id": callback["id"]})
            
        return "OK"
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return "ERROR"

# ============ 7. ВЕБ-ИНТЕРФЕЙС ============
@app.route("/")
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>VetManager Real Data Bot</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            h1 { color: #2c3e50; }
            .card { background: #f8f9fa; border-radius: 10px; padding: 20px; margin: 15px 0; border-left: 4px solid #3498db; }
            .btn { display: inline-block; background: #3498db; color: white; padding: 12px 24px; 
                   text-decoration: none; border-radius: 5px; margin: 5px; font-weight: bold; }
            .btn:hover { background: #2980b9; }
            .btn-success { background: #27ae60; }
            .btn-success:hover { background: #219653; }
            .status { padding: 5px 10px; border-radius: 3px; font-size: 12px; }
            .status-success { background: #d4edda; color: #155724; }
            .status-error { background: #f8d7da; color: #721c24; }
        </style>
    </head>
    <body>
        <h1>🤖 VetManager Real Data Bot</h1>
        
        <div class="card">
            <h2>🎯 РЕЖИМ: РЕАЛЬНЫЕ ДАННЫЕ</h2>
            <p><b>Источник:</b> VetManager API (drug14.vetmanager2.ru)</p>
            <p><b>Администратор:</b> ID 921853682</p>
            <p><b>Telegram:</b> @Fulsim_bot</p>
        </div>
        
        <div class="card">
            <h3>📊 Действия с реальными данными</h3>
            <a class="btn btn-success" href="/remind">📅 Получить записи на завтра</a><br><br>
            <a class="btn" href="/test_api">🔗 Тест подключения к VetManager</a><br><br>
            <a class="btn" href="/debug">🐛 Отладка данных</a><br><br>
            <a class="btn" href="/stats">📈 Статистика</a>
        </div>
        
        <div class="card">
            <h3>⚙️ Как это работает:</h3>
            <p>1. <b>Подключается к реальному VetManager</b> через API ключ</p>
            <p>2. <b>Запрашивает все активные записи</b> из системы</p>
            <p>3. <b>Фильтрует записи на завтра</b> по дате</p>
            <p>4. <b>Отправляет тебе список</b> с реальными клиентами</p>
            <p>5. <b>Кнопки управления</b> для подтверждения/отмены</p>
        </div>
    </body>
    </html>
    '''

@app.route("/remind")
def remind():
    return send_real_tomorrow_appointments()

@app.route("/test_api")
def test_api():
    result = test_vetmanager_connection()
    return f'''
    <div style="font-family: Arial; padding: 20px;">
        <h2>🔗 Тест подключения к VetManager</h2>
        <pre>{result}</pre>
        <a href="/" class="btn">← Назад</a>
    </div>
    '''

@app.route("/debug")
def debug():
    """Страница отладки - показываем сырые данные"""
    appointments = get_real_vetmanager_appointments()
    
    html = "<h2>🐛 Отладка данных VetManager</h2>"
    html += f"<p><b>Всего записей получено:</b> {len(appointments)}</p>"
    
    if appointments:
        html += "<h3>Последние 5 записей:</h3>"
        
        for i, app in enumerate(appointments[:5], 1):
            html += f"<div style='border:1px solid #ccc; padding:10px; margin:10px 0;'>"
            html += f"<b>Запись #{i}:</b><br>"
            
            # Показываем все поля
            for key, value in app.items():
                if key == "client" and isinstance(value, dict):
                    html += f"<b>{key}:</b><br>"
                    for k, v in value.items():
                        if v and str(v).strip():
                            html += f"  • {k}: {v}<br>"
                elif key == "pet" and isinstance(value, dict):
                    html += f"<b>{key}:</b><br>"
                    for k, v in value.items():
                        if v and str(v).strip():
                            html += f"  • {k}: {v}<br>"
                elif value and str(value).strip():
                    html += f"<b>{key}:</b> {value}<br>"
            
            html += "</div>"
    
    html += '<a href="/" class="btn">← Назад</a>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial; padding: 20px; }}
            .btn {{ background: #3498db; color: white; padding: 10px; text-decoration: none; }}
        </style>
    </head>
    <body>{html}</body>
    </html>
    '''

@app.route("/stats")
def stats():
    """Статистика"""
    appointments = get_real_vetmanager_appointments()
    
    html = "<h2>📈 Статистика VetManager</h2>"
    html += f"<p><b>Всего записей в системе:</b> {len(appointments)}</p>"
    
    if appointments:
        # Группировка по датам
        dates = {}
        for app in appointments:
            date_str = app.get("admission_date", "").split(" ")[0] if app.get("admission_date") else "Без даты"
            if date_str not in dates:
                dates[date_str] = 0
            dates[date_str] += 1
        
        html += "<h3>Распределение по датам:</h3>"
        for date_str, count in sorted(dates.items())[:10]:  # 10 последних дат
            html += f"<p>📅 {date_str}: {count} записей</p>"
    
    html += '<a href="/" class="btn">← Назад</a>'
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head><style>body {{ font-family: Arial; padding: 20px; }}</style></head>
    <body>{html}</body>
    </html>
    '''

# ============ 8. АВТОМАТИЧЕСКИЕ НАПОМИНАНИЯ ============
def auto_reminder():
    """Автоматическая отправка напоминаний"""
    while True:
        now = datetime.now()
        
        # Каждый день в 18:00 - отправляем реальные записи на завтра
        if now.hour == 18 and now.minute == 0:
            print(f"🕕 {now.strftime('%H:%M')} - Отправляю реальные записи на завтра...")
            send_real_tomorrow_appointments()
            time.sleep(61)  # Ждём минуту
        
        time.sleep(30)

# Запускаем планировщик
scheduler = threading.Thread(target=auto_reminder, daemon=True)
scheduler.start()

# ============ 9. ЗАПУСК ============
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 VETMANAGER REAL DATA BOT ЗАПУЩЕН!")
    print("=" * 60)
    print("🎯 ИСТОЧНИК: РЕАЛЬНЫЕ ДАННЫЕ ИЗ VETMANAGER")
    print(f"🔑 API ключ: {VETMANAGER_KEY[:10]}...")
    print(f"👤 Администратор: {ADMIN_ID}")
    print("🏥 Клиника: drug14.vetmanager2.ru")
    print("=" * 60)
    print("🌐 Веб-интерфейс:")
    print("   https://vetmanager-bot-1.onrender.com/")
    print("   https://vetmanager-bot-1.onrender.com/remind")
    print("=" * 60)
    
    # Тестовый запуск
    print("\n🔍 Тестирую подключение к VetManager...")
    test_result = test_vetmanager_connection()
    print(f"Результат теста: {test_result}")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
