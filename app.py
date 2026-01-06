from flask import Flask
import requests
import os
from datetime import datetime, timedada

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

# ============ 2. ПОЛУЧЕНИЕ ДАННЫХ ИЗ VETMANAGER ============
def get_vetmanager_data():
    url = "https://drug14.vetmanager2.ru/rest/api/user"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                user_count = data.get("data", {}).get("totalCount", 0)
                return f"✅ VetManager работает! Пользователей: {user_count}"
        return f"❌ Ошибка VetManager"
    except:
        return "❌ Нет подключения"

# ============ 3. ПРОВЕРКА ЗАВТРАШНИХ ЗАПИСЕЙ ============
def check_tomorrow():
    tomorrow = (datetime.now() + timedada(days=1)).strftime("%Y-%m-%d")
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    params = {"date_from": tomorrow, "date_to": tomorrow, "limit": 10}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                appointments = data.get("data", {}).get("admission", [])
                
                # ОТПРАВЛЯЕМ СООБЩЕНИЕ ТЕБЕ
                if appointments:
                    message = f"📅 <b>Завтра {tomorrow} записей:</b> {len(appointments)}\n\n"
                    for app in appointments[:3]:  # первые 3
                        message += f"🕒 {app.get('time', '')} - Клиент ID: {app.get('client_id', '')}\n"
                    send_telegram(message)
                    return f"✅ Отправлено! Записей: {len(appointments)}"
                else:
                    send_telegram(f"📭 На {tomorrow} нет записей")
                    return "📭 Нет записей"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"
    
    return "❌ Не удалось проверить"

# ============ 4. ВЕБ-СТРАНИЦА ============
@app.route("/")
def home():
    status = get_vetmanager_data()
    return f'''
    <h1>🤖 VetManager Reminder Bot</h1>
    <p><b>Статус:</b> {status}</p>
    <p><b>Админ:</b> {ADMIN_ID}</p>
    
    <h3>Команды:</h3>
    <ul>
        <li><a href="/test">/test</a> - Проверить VetManager</li>
        <li><a href="/check">/check</a> - Проверить завтрашние записи</li>
        <li><a href="/send">/send</a> - Тест Telegram</li>
    </ul>
    '''

@app.route("/test")
def test():
    return get_vetmanager_data()

@app.route("/check")
def check():
    result = check_tomorrow()
    return result

@app.route("/send")
def send():
    send_telegram(f"🤖 Тест от бота! Время: {datetime.now().strftime('%H:%M:%S')}")
    return "✅ Тестовое сообщение отправлено!"

# ============ ЗАПУСК ============
if __name__ == "__main__":
    print("🚀 Бот запущен!")
    print(f"🔑 API ключ: {VETMANAGER_KEY}")
    print(f"🤖 Telegram бот: @Fulsim_bot")
    print(f"👤 Твой ID: {ADMIN_ID}")
    print(f"🌐 Открой: http://localhost:5000")
    
    # Автоматически проверяем при запуске
    print(f"📡 Статус: {get_vetmanager_data()}")
    
    app.run(host="0.0.0.0", port=5000)
