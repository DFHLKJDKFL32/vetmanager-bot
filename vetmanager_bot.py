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

# ============ 2. ПОЛУЧИТЬ ЗАПИСИ НА ЗАВТРА ============
def get_tomorrow_appointments():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    params = {"date_from": tomorrow, "date_to": tomorrow, "limit": 50}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                appointments = data.get("data", {}).get("admission", [])
                return appointments
    except:
        pass
    return []

# ============ 3. ПОЛУЧИТЬ КЛИЕНТА ПО ID ============
def get_client(client_id):
    url = f"https://drug14.vetmanager2.ru/rest/api/client/{client_id}"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return data.get("data", {})
    except:
        pass
    return {}

# ============ 4. ОСНОВНАЯ ФУНКЦИЯ ============
def check_and_send():
    """Проверить записи и отправить уведомление"""
    appointments = get_tomorrow_appointments()
    
    if not appointments:
        send_telegram(f"📭 На завтра нет записей")
        return "📭 Нет записей на завтра"
    
    # Отправляем тебе сообщение
    message = f"📅 <b>Завтра {len(appointments)} записей:</b>\n\n"
    
    for i, app in enumerate(appointments[:10], 1):  # первые 10
        client_id = app.get("client_id")
        time = app.get("time", "??:??")
        
        # Получаем имя клиента
        client = get_client(client_id)
        client_name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
        if not client_name:
            client_name = f"Клиент ID:{client_id}"
        
        message += f"{i}. 🕒 {time} - {client_name}\n"
    
    send_telegram(message)
    return f"✅ Отправлено! Записей: {len(appointments)}"

# ============ 5. ВЕБ-СТРАНИЦА ============
@app.route("/")
def home():
    return '''
    <h1>🤖 VetManager Reminder Bot</h1>
    <p><b>Статус:</b> ✅ Всё работает</p>
    <p><b>Админ ID:</b> 921853682</p>
    <p><b>Telegram бот:</b> @Fulsim_bot</p>
    
    <h3>Команды:</h3>
    <ul>
        <li><a href="/check">/check</a> - Проверить завтрашние записи</li>
        <li><a href="/test">/test</a> - Тест Telegram</li>
    </ul>
    '''

@app.route("/check")
def check():
    result = check_and_send()
    return result

@app.route("/test")
def test():
    send_telegram(f"🤖 Тест от бота! Время: {datetime.now().strftime('%H:%M:%S')}")
    return "✅ Тестовое сообщение отправлено!"

# ============ ЗАПУСК ============
if __name__ == "__main__":
    print("🚀 Бот запущен!")
    print("1. Открой: https://vetmanager-bot-1.onrender.com/")
    print("2. Нажми '/check' для проверки записей")
    app.run(host="0.0.0.0", port=5000)
