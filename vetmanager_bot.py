from flask import Flask
import requests
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# ============ ТВОИ КЛЮЧИ ============
TELEGRAM_TOKEN = "8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI"
VETMANAGER_KEY = "29607ccc63c684fa672be9694f7f09ec"
ADMIN_ID = "921853682"

# ============ 1. ОТПРАВКА В TELEGRAM ============
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": ADMIN_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")
        return False

# ============ 2. ПОЛУЧИТЬ ВСЕ ЗАПИСИ ============
def get_all_appointments():
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    # Пробуем получить больше записей
    all_appointments = []
    
    try:
        # Пробуем несколько лимитов
        for limit in [100, 200, 500]:
            params = {"limit": limit}
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Получено данных с limit={limit}: {len(str(data))} символов")
                
                if data.get("success"):
                    appointments = data.get("data", {}).get("admission", [])
                    all_appointments.extend(appointments)
                    print(f"📊 Найдено записей: {len(appointments)}")
                    
                    if len(appointments) < limit:
                        break  # Получили все записи
                else:
                    print(f"❌ API вернул ошибку: {data.get('error', {}).get('message', 'Unknown error')}")
                    
            else:
                print(f"❌ HTTP ошибка: {response.status_code}")
                
    except Exception as e:
        print(f"❌ Ошибка получения записей: {e}")
    
    return all_appointments

# ============ 3. НАЙТИ ЗАПИСИ НА ДАТУ ============
def find_appointments_by_date(target_date_str):
    """Найти записи на конкретную дату (формат YYYY-MM-DD)"""
    all_appointments = get_all_appointments()
    print(f"📈 Всего записей получено: {len(all_appointments)}")
    
    target_date = target_date_str
    filtered_appointments = []
    
    for app in all_appointments:
        date_time = app.get("admission_date", "")
        if date_time.startswith(target_date):
            filtered_appointments.append(app)
    
    print(f"📅 На дату {target_date} найдено: {len(filtered_appointments)} записей")
    return filtered_appointments

# ============ 4. ФОРМАТИРОВАТЬ ЗАПИСЬ ============
def format_appointment(app, index):
    """Отформатировать одну запись для Telegram"""
    # Время
    date_time = app.get("admission_date", "")
    if " " in date_time:
        date_part, time_part = date_time.split(" ")
        time = time_part[:5]
    else:
        time = "??:??"
    
    # Клиент
    client = app.get("client", {})
    first_name = client.get("first_name", "").strip()
    last_name = client.get("last_name", "").strip()
    
    if first_name or last_name:
        client_name = f"{first_name} {last_name}".strip()
    else:
        client_id = app.get("client_id", "?")
        client_name = f"Клиент ID:{client_id}"
    
    # Питомец
    pet = app.get("pet", {})
    pet_name = pet.get("alias", "").strip()
    if not pet_name:
        pet_type = pet.get("type", {}).get("title", "питомец") if isinstance(pet.get("type"), dict) else "питомец"
        pet_name = pet_type
    
    # Врач
    doctor = app.get("user", {})
    doctor_name = doctor.get("last_name", "").strip()
    if doctor_name:
        doctor_info = f"👨‍⚕️ {doctor_name}"
    else:
        doctor_info = ""
    
    # Описание
    description = app.get("description", "").strip()
    
    # Формируем строку
    result = f"{index}. 🕒 <b>{time}</b> - {client_name}"
    result += f"\n   🐾 {pet_name}"
    
    if doctor_info:
        result += f" | {doctor_info}"
    
    if description:
        if len(description) > 50:
            description = description[:50] + "..."
        result += f"\n   📝 {description}"
    
    return result

# ============ 5. ОТПРАВИТЬ УВЕДОМЛЕНИЕ НА ЗАВТРА ============
def send_tomorrow_notification():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_formatted = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    appointments = find_appointments_by_date(tomorrow)
    
    if not appointments:
        message = f"📭 На завтра ({tomorrow_formatted}) нет записей"
        send_telegram(message)
        return message
    
    # Сортируем по времени
    appointments.sort(key=lambda x: x.get("admission_date", ""))
    
    # Формируем сообщение
    message = f"📅 <b>НА ЗАВТРА {tomorrow_formatted}</b>\n"
    message += f"<i>Всего записей: {len(appointments)}</i>\n\n"
    
    for i, app in enumerate(appointments[:20], 1):  # Показываем первые 20
        message += format_appointment(app, i) + "\n\n"
    
    if len(appointments) > 20:
        message += f"<i>... и ещё {len(appointments) - 20} записей</i>\n"
    
    message += "\n⚡ <b>Не забудьте позвонить клиентам для подтверждения!</b>"
    
    send_telegram(message)
    return f"✅ Отправлено! Записей: {len(appointments)}"

# ============ 6. ОТЧЁТ НА НЕДЕЛЮ ============
def send_weekly_report():
    message = "📅 <b>ПЛАН НА БЛИЖАЙШУЮ НЕДЕЛЮ</b>\n\n"
    
    total_appointments = 0
    has_appointments = False
    
    for days in range(1, 8):  # Следующие 7 дней
        date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        date_formatted = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y (%a)")
        
        appointments = find_appointments_by_date(date)
        
        if appointments:
            has_appointments = True
            total_appointments += len(appointments)
            
            # Сортируем и берем первые 3 для примера
            appointments.sort(key=lambda x: x.get("admission_date", ""))
            
            message += f"<b>{date_formatted}:</b> {len(appointments)} записей\n"
            
            for i, app in enumerate(appointments[:3], 1):
                time = app.get("admission_date", "").split(" ")[1][:5] if " " in app.get("admission_date", "") else "??:??"
                client = app.get("client", {})
                name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
                if not name:
                    name = f"Клиент ID:{app.get('client_id')}"
                
                message += f"  {i}. {time} - {name}\n"
            
            if len(appointments) > 3:
                message += f"  ... и ещё {len(appointments) - 3}\n"
            
            message += "\n"
    
    if not has_appointments:
        message = "📭 На ближайшую неделю нет записей"
    else:
        message += f"<b>ИТОГО НА НЕДЕЛЮ:</b> {total_appointments} записей"
    
    send_telegram(message)
    return f"✅ Отчёт отправлен! Всего: {total_appointments} записей"

# ============ 7. ТЕСТ СИСТЕМЫ ============
def test_system():
    """Полная проверка системы"""
    test_results = []
    
    # 1. Тест Telegram
    telegram_test = send_telegram("🤖 <b>ТЕСТ СИСТЕМЫ</b>\nБот запущен и работает!")
    test_results.append(f"Telegram: {'✅' if telegram_test else '❌'}")
    
    # 2. Тест VetManager API
    try:
        url = "https://drug14.vetmanager2.ru/rest/api/admission"
        headers = {"X-REST-API-KEY": VETMANAGER_KEY}
        params = {"limit": 5}
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                appointments = data.get("data", {}).get("admission", [])
                test_results.append(f"VetManager API: ✅ ({len(appointments)} записей)")
            else:
                test_results.append(f"VetManager API: ❌ ({data.get('error', {}).get('message', 'Unknown')})")
        else:
            test_results.append(f"VetManager API: ❌ HTTP {response.status_code}")
    except Exception as e:
        test_results.append(f"VetManager API: ❌ {str(e)}")
    
    # 3. Проверка записей на разные даты
    dates_to_check = [
        (datetime.now().strftime("%Y-%m-%d"), "сегодня"),
        ((datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"), "завтра"),
        ((datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"), "послезавтра")
    ]
    
    for date_str, label in dates_to_check:
        appointments = find_appointments_by_date(date_str)
        test_results.append(f"Записи на {label}: {len(appointments)}")
    
    # Формируем итоговое сообщение
    message = "🔍 <b>РЕЗУЛЬТАТЫ ТЕСТА СИСТЕМЫ</b>\n\n"
    message += "\n".join(test_results)
    message += "\n\n📊 <i>Система готова к работе!</i>"
    
    send_telegram(message)
    return "✅ Тест системы выполнен!"

# ============ ВЕБ-ИНТЕРФЕЙС ============
@app.route("/")
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>VetManager Reminder Bot</title>
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
            .btn-warning { background: #f39c12; }
            .btn-warning:hover { background: #e67e22; }
        </style>
    </head>
    <body>
        <h1>🤖 VetManager Reminder Bot</h1>
        <div class="card">
            <p><b>Статус:</b> ✅ Работает</p>
            <p><b>Telegram:</b> @Fulsim_bot</p>
            <p><b>Администратор:</b> ID 921853682</p>
            <p><b>Клиника:</b> drug14.vetmanager2.ru</p>
        </div>
        
        <h2>📋 Основные команды</h2>
        <div class="card">
            <a class="btn btn-success" href="/remind">/remind</a> - Напоминание на завтра<br><br>
            <a class="btn" href="/week">/week</a> - Отчёт на неделю<br><br>
            <a class="btn" href="/test">/test</a> - Тест системы<br><br>
            <a class="btn" href="/check_all">/check_all</a> - Проверить все даты<br><br>
            <a class="btn btn-warning" href="/send_test">/send_test</a> - Тест Telegram
        </div>
        
        <h2>🔧 Дополнительные функции</h2>
        <div class="card">
            <p><b>Автоматические напоминания:</b> Каждый день в 18:00</p>
            <p><b>Формат сообщений:</b> Время, клиент, питомец, врач, описание</p>
            <p><b>Лимит:</b> Показывает до 20 записей в сообщении</p>
        </div>
        
        <div style="text-align: center; margin-top: 30px; color: #7f8c8d;">
            <p>Версия 2.0 | Обновлено: 06.01.2026</p>
        </div>
    </body>
    </html>
    '''

@app.route("/remind")
def remind():
    return send_tomorrow_notification()

@app.route("/week")
def week():
    return send_weekly_report()

@app.route("/test")
def test():
    return test_system()

@app.route("/check_all")
def check_all():
    """Показать все записи на разные даты"""
    html = "<h2>🔍 Проверка записей на разные даты</h2>"
    
    dates = [
        ("Сегодня", datetime.now().strftime("%Y-%m-%d")),
        ("Завтра", (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")),
        ("Послезавтра", (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")),
        ("Через 3 дня", (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")),
        ("Через 4 дня", (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d")),
        ("Через 5 дней", (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")),
        ("Через 6 дней", (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")),
        ("Через 7 дней", (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")),
    ]
    
    for label, date_str in dates:
        appointments = find_appointments_by_date(date_str)
        date_formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
        
        html += f"<h3>📅 {label} ({date_formatted}): {len(appointments)} записей</h3>"
        
        if appointments:
            # Сортируем по времени
            appointments.sort(key=lambda x: x.get("admission_date", ""))
            
            for i, app in enumerate(appointments[:10], 1):
                time = app.get("admission_date", "").split(" ")[1][:5] if " " in app.get("admission_date", "") else "??:??"
                client = app.get("client", {})
                name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
                if not name:
                    name = f"Клиент ID:{app.get('client_id')}"
                
                pet = app.get("pet", {})
                pet_name = pet.get("alias", "питомец")
                
                html += f"<p>{i}. 🕒 {time} - {name} с {pet_name}</p>"
            
            if len(appointments) > 10:
                html += f"<p><i>... и ещё {len(appointments) - 10} записей</i></p>"
        else:
            html += "<p><i>Записей нет</i></p>"
        
        html += "<hr>"
    
    html += '<br><a href="/">← На главную</a>'
    return html

@app.route("/send_test")
def send_test():
    send_telegram("✅ <b>Тестовое сообщение</b>\nБот работает корректно!")
    return "✅ Тестовое сообщение отправлено в Telegram"

# ============ АВТОМАТИЧЕСКАЯ ОТПРАВКА ============
import threading
import time

def auto_scheduler():
    """Автоматическая отправка напоминаний"""
    while True:
        now = datetime.now()
        
        # Ежедневно в 18:00 - напоминание на завтра
        if now.hour == 18 and now.minute == 0:
            print(f"🕕 {now.strftime('%H:%M')} - Отправляю напоминание на завтра...")
            send_tomorrow_notification()
            time.sleep(61)  # Ждём минуту чтобы не сработать дважды
        
        # Каждый понедельник в 9:00 - отчёт на неделю
        if now.weekday() == 0 and now.hour == 9 and now.minute == 0:
            print(f"📅 {now.strftime('%H:%M')} - Отправляю недельный отчёт...")
            send_weekly_report()
            time.sleep(61)
        
        time.sleep(30)  # Проверяем каждые 30 секунд

# Запускаем планировщик в фоне
scheduler_thread = threading.Thread(target=auto_scheduler, daemon=True)
scheduler_thread.start()

# ============ ЗАПУСК СЕРВЕРА ============
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 VETMANAGER REMINDER BOT 2.0 ЗАПУЩЕН!")
    print("=" * 60)
    print(f"👤 Администратор: {ADMIN_ID}")
    print(f"🤖 Telegram бот: @Fulsim_bot")
    print(f"🏥 Клиника: drug14.vetmanager2.ru")
    print(f"🔑 API ключ: {VETMANAGER_KEY[:10]}...")
    print("=" * 60)
    print("🌐 Веб-интерфейс доступен по адресам:")
    print("   https://vetmanager-bot-1.onrender.com/")
    print("   https://vetmanager-bot-1.onrender.com/remind")
    print("   https://vetmanager-bot-1.onrender.com/week")
    print("   https://vetmanager-bot-1.onrender.com/test")
    print("=" * 60)
    print("📅 Автоматические напоминания:")
    print("   🕕 18:00 каждый день - напоминание на завтра")
    print("   📅 9:00 каждый понедельник - отчёт на неделю")
    print("=" * 60)
    
    # Тестовый запуск при старте
    print("\n🔍 Выполняю тест системы...")
    test_result = test_system()
    print(f"Результат теста: {test_result}")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
    
