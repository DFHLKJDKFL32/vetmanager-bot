from flask import Flask
import requests
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# ============ ТВОИ КЛЮЧИ ============
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

def check_tomorrow_appointments():
    """Получить записи НА ЗАВТРА (работающий вариант)"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Вариант 1: Используем фильтр через параметр filter
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    # Правильный фильтр по дате
    filter_json = f'[{{"property":"admission_date","value":"{tomorrow}","operator":">="}}]'
    
    params = {
        "limit": 20,
        "filter": filter_json,
        "sort": '[{"property":"admission_date","direction":"ASC"}]'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        
        if data.get("success"):
            appointments = data.get("data", {}).get("admission", [])
            
            # Фильтруем только завтрашние на всякий случай
            tomorrow_appointments = []
            for app in appointments:
                admission_date = app.get("admission_date", "")
                if admission_date.startswith(tomorrow):
                    tomorrow_appointments.append(app)
            
            return tomorrow_appointments
        
    except Exception as e:
        print(f"❌ Ошибка API: {e}")
    
    return []

def check_and_send():
    """Основная функция проверки"""
    appointments = check_tomorrow_appointments()
    
    if not appointments:
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        send_telegram(f"📭 На {tomorrow} нет записей")
        return "📭 Нет записей на завтра"
    
    message = f"📅 <b>Найдено {len(appointments)} записей на завтра:</b>\n\n"
    
    for i, app in enumerate(appointments[:15], 1):  # первые 15
        # Время из admission_date
        admission_date = app.get("admission_date", "")
        time_part = admission_date.split(" ")[1] if " " in admission_date else "??:??"
        
        # Клиент
        client_data = app.get("client", {})
        client_name = f"{client_data.get('first_name', '')} {client_data.get('last_name', '')}".strip()
        if not client_name:
            client_name = f"Клиент ID:{app.get('client_id')}"
        
        # Питомец
        pet_data = app.get("pet", {})
        pet_name = pet_data.get("alias", "питомец")
        
        message += f"{i}. 🕒 {time_part} - {client_name} с {pet_name}\n"
        
        # Описание если есть
        description = app.get("description", "")
        if description:
            message += f"   📝 {description[:40]}...\n"
    
    if len(appointments) > 15:
        message += f"\n... и ещё {len(appointments) - 15} записей"
    
    send_telegram(message)
    return f"✅ Отправлено! Найдено записей: {len(appointments)}"

# ============ АЛЬТЕРНАТИВНЫЙ ВАРИАНТ ============
def check_recent_appointments():
    """Проверить записи на ближайшие 7 дней"""
    today = datetime.now().strftime("%Y-%m-%d")
    next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    # Ищем записи на ближайшую неделю
    filter_json = f'[{{"property":"admission_date","value":"{today}","operator":">="}},{{"property":"admission_date","value":"{next_week}","operator":"<="}}]'
    
    params = {
        "limit": 30,
        "filter": filter_json,
        "sort": '[{"property":"admission_date","direction":"ASC"}]'
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        
        if data.get("success"):
            all_appointments = data.get("data", {}).get("admission", [])
            
            # Группируем по дням
            appointments_by_day = {}
            for app in all_appointments:
                date_str = app.get("admission_date", "").split(" ")[0]
                if date_str:
                    if date_str not in appointments_by_day:
                        appointments_by_day[date_str] = []
                    appointments_by_day[date_str].append(app)
            
            return appointments_by_day
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    return {}

def send_weekly_report():
    """Отправить отчёт на неделю"""
    appointments_by_day = check_recent_appointments()
    
    if not appointments_by_day:
        send_telegram("📭 Нет записей на ближайшую неделю")
        return "📭 Нет записей"
    
    message = "📅 <b>Записи на ближайшую неделю:</b>\n\n"
    
    for date_str in sorted(appointments_by_day.keys()):
        appointments = appointments_by_day[date_str]
        message += f"<b>{date_str}:</b> {len(appointments)} записей\n"
        
        for app in appointments[:3]:  # первые 3 каждого дня
            time_part = app.get("admission_date", "").split(" ")[1] if " " in app.get("admission_date", "") else "??:??"
            client_data = app.get("client", {})
            client_name = f"{client_data.get('first_name', '')} {client_data.get('last_name', '')}".strip()
            if not client_name:
                client_name = f"Клиент ID:{app.get('client_id')}"
            
            message += f"  🕒 {time_part} - {client_name}\n"
        
        if len(appointments) > 3:
            message += f"  ... и ещё {len(appointments) - 3}\n"
        message += "\n"
    
    send_telegram(message)
    return f"✅ Отчёт отправлен! Всего дней: {len(appointments_by_day)}"

# ============ ВЕБ-ИНТЕРФЕЙС ============
@app.route("/")
def home():
    return '''
    <h1>🤖 VetManager Reminder Bot</h1>
    <p><b>Статус:</b> ✅ Работает</p>
    <p><b>Telegram:</b> @Fulsim_bot</p>
    
    <h3>Команды:</h3>
    <ul>
        <li><a href="/check">/check</a> - Проверить завтрашние записи</li>
        <li><a href="/week">/week</a> - Отчёт на неделю</li>
        <li><a href="/test">/test</a> - Тест Telegram</li>
    </ul>
    '''

@app.route("/check")
def check():
    return check_and_send()

@app.route("/week")
def week():
    return send_weekly_report()

@app.route("/test")
def test():
    send_telegram(f"🤖 Тест от бота! Время: {datetime.now().strftime('%H:%M:%S')}")
    return "✅ Тестовое сообщение отправлено!"

# ============ ЗАПУСК ============
if __name__ == "__main__":
    print("🚀 Бот запущен!")
    print("👉 Открой: https://vetmanager-bot-1.onrender.com/")
    print("👉 Для проверки: https://vetmanager-bot-1.onrender.com/check")
    print("👉 Отчёт на неделю: https://vetmanager-bot-1.onrender.com/week")
    app.run(host="0.0.0.0", port=5000)
