from flask import Flask
import requests
from datetime import datetime, timedelta

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
        requests.post(url, json=data, timeout=5)
        return True
    except:
        return False

# ============ 2. ПОЛУЧИТЬ ЗАПИСИ ИЗ VETMANAGER ============
def get_appointments():
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    params = {"limit": 50}  # Берем 50 последних записей
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        
        if data.get("success"):
            return data.get("data", {}).get("admission", [])
    except:
        pass
    return []

# ============ 3. НАЙТИ ЗАПИСИ НА ЗАВТРА ============
def find_tomorrow_appointments():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    all_appointments = get_appointments()
    
    tomorrow_apps = []
    for app in all_appointments:
        date_str = app.get("admission_date", "")
        if date_str.startswith(tomorrow):
            tomorrow_apps.append(app)
    
    return tomorrow_apps

# ============ 4. ОТПРАВИТЬ УВЕДОМЛЕНИЕ ============
def send_notification():
    appointments = find_tomorrow_appointments()
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    if not appointments:
        send_telegram(f"📭 На завтра ({tomorrow}) нет записей")
        return "📭 Нет записей"
    
    # Формируем сообщение
    message = f"📅 <b>На завтра ({tomorrow}): {len(appointments)} записей</b>\n\n"
    
    for i, app in enumerate(appointments[:10], 1):
        # Время
        date_str = app.get("admission_date", "")
        time = date_str.split(" ")[1][:5] if " " in date_str else "??:??"
        
        # Клиент
        client = app.get("client", {})
        client_name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
        if not client_name:
            client_name = f"Клиент ID:{app.get('client_id')}"
        
        # Питомец
        pet = app.get("pet", {})
        pet_name = pet.get("alias", "питомец")
        
        message += f"{i}. 🕒 {time} - {client_name} с {pet_name}\n"
    
    if len(appointments) > 10:
        message += f"\n... и ещё {len(appointments) - 10} записей"
    
    send_telegram(message)
    return f"✅ Отправлено! Записей: {len(appointments)}"

# ============ 5. ВЕБ-СТРАНИЦА ============
@app.route("/")
def home():
    return '''
    <h1>🤖 VetManager Reminder Bot</h1>
    <p><b>Статус:</b> ✅ Работает</p>
    <p><b>Telegram:</b> @Fulsim_bot</p>
    
    <h3>Команды:</h3>
    <ul>
        <li><a href="/check">/check</a> - Проверить завтрашние записи</li>
        <li><a href="/send">/send</a> - Тест Telegram</li>
        <li><a href="/status">/status</a> - Статус системы</li>
    </ul>
    '''

@app.route("/check")
def check():
    return send_notification()

@app.route("/send")
def send():
    send_telegram(f"🤖 Тест! Бот работает. Время: {datetime.now().strftime('%H:%M:%S')}")
    return "✅ Тестовое сообщение отправлено!"

@app.route("/status")
def status():
    appointments = get_appointments()
    total = len(appointments)
    
    # Последняя запись
    last_app = appointments[0] if appointments else {}
    last_date = last_app.get("admission_date", "нет")
    
    return f'''
    <h2>📊 Статус системы</h2>
    <p><b>Всего записей в базе:</b> {total}</p>
    <p><b>Последняя запись:</b> {last_date}</p>
    <p><b>Telegram бот:</b> @Fulsim_bot</p>
    <p><b>Владелец:</b> ID {ADMIN_ID}</p>
    <p><a href="/">На главную</a></p>
    '''

# ============ ЗАПУСК ============
if __name__ == "__main__":
    print("🚀 Бот запущен!")
    print("👉 Открой: https://vetmanager-bot-1.onrender.com/")
    print("👉 Для проверки: https://vetmanager-bot-1.onrender.com/check")
    app.run(host="0.0.0.0", port=5000)
