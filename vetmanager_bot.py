from flask import Flask
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

TELEGRAM_TOKEN = "8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI"
VETMANAGER_KEY = "29607ccc63c684fa672be9694f7f09ec"
ADMIN_ID = "921853682"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": ADMIN_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=data, timeout=5)
        return True
    except:
        return False

def get_appointments(days=1):
    """Получить записи на N дней вперёд"""
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    params = {"limit": 200}  # Больше записей
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        data = response.json()
        
        if data.get("success"):
            all_apps = data.get("data", {}).get("admission", [])
            
            # Фильтруем по дате
            target_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            filtered_apps = []
            
            for app in all_apps:
                date_str = app.get("admission_date", "")
                if date_str.startswith(target_date):
                    filtered_apps.append(app)
            
            return filtered_apps
    except Exception as e:
        print(f"Ошибка: {e}")
    
    return []

def format_appointment(app, index):
    """Отформатировать одну запись"""
    # Время
    date_str = app.get("admission_date", "")
    time = date_str.split(" ")[1][:5] if " " in date_str else "??:??"
    
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
        pet_type = pet.get("pet_type_data", {}).get("title", "питомец")
        pet_name = pet_type
    
    # Описание
    description = app.get("description", "").strip()
    
    # Формируем строку
    result = f"{index}. 🕒 {time} - {client_name} с {pet_name}"
    
    if description:
        # Сокращаем длинное описание
        if len(description) > 40:
            description = description[:40] + "..."
        result += f"\n   📝 {description}"
    
    return result

def send_daily_reminder():
    """Отправить напоминания на завтра"""
    appointments = get_appointments(days=1)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    if not appointments:
        send_telegram(f"📭 На завтра ({tomorrow}) нет записей")
        return f"📭 Нет записей на {tomorrow}"
    
    message = f"📅 <b>Напоминание! Завтра {tomorrow}:</b>\n"
    message += f"<i>Всего записей: {len(appointments)}</i>\n\n"
    
    for i, app in enumerate(appointments[:15], 1):
        message += format_appointment(app, i) + "\n"
    
    if len(appointments) > 15:
        message += f"\n... и ещё {len(appointments) - 15} записей"
    
    # Добавляем инструкцию для администратора
    message += "\n\n⚡ <i>Не забудьте позвонить клиентам для подтверждения!</i>"
    
    send_telegram(message)
    return f"✅ Напоминания отправлены! Записей: {len(appointments)}"

def send_weekly_report():
    """Отчёт на неделю"""
    appointments_by_day = {}
    
    # Собираем записи на 7 дней вперёд
    for days in range(1, 8):
        date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
        day_appointments = get_appointments(days)
        
        if day_appointments:
            appointments_by_day[date] = day_appointments
    
    if not appointments_by_day:
        send_telegram("📭 На ближайшую неделю нет записей")
        return "📭 Нет записей на неделю"
    
    message = "📅 <b>План на неделю:</b>\n\n"
    
    total_appointments = 0
    for date_str in sorted(appointments_by_day.keys()):
        apps = appointments_by_day[date_str]
        total_appointments += len(apps)
        
        # Форматируем дату
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d.%m.%Y (%a)")
        
        message += f"<b>{formatted_date}:</b> {len(apps)} записей\n"
    
    message += f"\n<b>Итого на неделю:</b> {total_appointments} записей"
    
    send_telegram(message)
    return f"✅ Отчёт отправлен! Всего записей: {total_appointments}"

# ============ ВЕБ-ИНТЕРФЕЙС ============
@app.route("/")
def home():
    return '''
    <h1>🤖 VetManager Reminder Bot</h1>
    <p><b>Статус:</b> ✅ Работает отлично!</p>
    <p><b>Админ:</b> ID 921853682</p>
    <p><b>Telegram:</b> @Fulsim_bot</p>
    
    <h3>Автоматические напоминания:</h3>
    <ul>
        <li><a href="/remind">/remind</a> - Напоминание на завтра</li>
        <li><a href="/week">/week</a> - Отчёт на неделю</li>
        <li><a href="/test">/test</a> - Тест бота</li>
    </ul>
    
    <h3>Для клиентов (в будущем):</h3>
    <p>Клиенты смогут писать боту /start и получать свои напоминания</p>
    '''

@app.route("/remind")
def remind():
    return send_daily_reminder()

@app.route("/week")
def week():
    return send_weekly_report()

@app.route("/test")
def test():
    send_telegram(f"✅ Бот работает! Время: {datetime.now().strftime('%H:%M')}")
    return "✅ Тест пройден!"

# ============ АВТОМАТИЗАЦИЯ ============
def auto_send_reminders():
    """Автоматическая отправка в 18:00 каждый день"""
    while True:
        now = datetime.now()
        
        # Если 18:00 - отправляем напоминания
        if now.hour == 18 and now.minute == 0:
            print(f"🕕 {now.strftime('%H:%M')} - Отправляю напоминания...")
            send_daily_reminder()
        
        # Ждём 60 секунд
        time.sleep(60)

# Запускаем автоматизацию в отдельном потоке
import threading
import time
scheduler = threading.Thread(target=auto_send_reminders, daemon=True)
scheduler.start()

# ============ ЗАПУСК ============
if __name__ == "__main__":
    print("=" * 50)
    print("🚀 VETMANAGER REMINDER BOT ЗАПУЩЕН!")
    print("=" * 50)
    print(f"👤 Админ: {ADMIN_ID}")
    print(f"🤖 Бот: @Fulsim_bot")
    print(f"🏥 Клиника: drug14.vetmanager2.ru")
    print(f"🌐 Веб-интерфейс: https://vetmanager-bot-1.onrender.com/")
    print("=" * 50)
    print("📋 Доступные команды:")
    print("  /remind - Напоминания на завтра")
    print("  /week   - Отчёт на неделю")
    print("  /test   - Тест бота")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=5000, debug=False)
