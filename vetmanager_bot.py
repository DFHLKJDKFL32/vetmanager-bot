from flask import Flask, request
import requests
from datetime import datetime, timedelta
import json
import sqlite3
import threading
import time

app = Flask(__name__)

# ============ ТВОИ КЛЮЧИ ============
TELEGRAM_TOKEN = "8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI"
VETMANAGER_KEY = "29607ccc63c684fa672be9694f7f09ec"
ADMIN_ID = "921853682"

# ============ 1. ГЛУБОКИЙ ДЕБАГ VETMANAGER API ============
def debug_vetmanager_api():
    """Полная отладка API VetManager"""
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    debug_info = []
    
    try:
        # Пробуем разные параметры
        test_params = [
            {"limit": 100},
            {"limit": 100, "active": 1},
            {"limit": 100, "status": "active"},
            {"limit": 100, "admission_date_from": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")},
            {}  # Без параметров
        ]
        
        for i, params in enumerate(test_params):
            print(f"\n🔍 Тест #{i+1} с параметрами: {params}")
            
            try:
                response = requests.get(url, headers=headers, params=params, timeout=15)
                debug_info.append(f"\n📊 Тест #{i+1} (params: {params}):")
                debug_info.append(f"   Статус: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get("success"):
                        appointments = data.get("data", {}).get("admission", [])
                        debug_info.append(f"   Успешно! Записей: {len(appointments)}")
                        
                        # Показываем первые 3 записи
                        if appointments:
                            for j, app in enumerate(appointments[:3], 1):
                                date_str = app.get("admission_date", "Нет даты")
                                client = app.get("client", {})
                                name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
                                if not name:
                                    name = f"Клиент ID:{app.get('client_id')}"
                                
                                debug_info.append(f"   {j}. {date_str} - {name}")
                    else:
                        error = data.get('error', {}).get('message', 'Unknown')
                        debug_info.append(f"   Ошибка API: {error}")
                else:
                    debug_info.append(f"   HTTP ошибка: {response.status_code}")
                    
            except Exception as e:
                debug_info.append(f"   Исключение: {str(e)}")
        
        # Теперь получаем ВСЕ данные и смотрим их
        print(f"\n🔍 Получение ВСЕХ данных...")
        all_appointments = []
        
        for limit in [50, 100, 200, 500]:
            params = {"limit": limit}
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    appointments = data.get("data", {}).get("admission", [])
                    all_appointments.extend(appointments)
                    print(f"   Получено {len(appointments)} с limit={limit}")
                    
                    if len(appointments) < limit:
                        break
        
        debug_info.append(f"\n📈 ИТОГО получено записей: {len(all_appointments)}")
        
        if all_appointments:
            # Группируем по датам
            dates = {}
            for app in all_appointments:
                date_str = app.get("admission_date", "").split(" ")[0] if " " in app.get("admission_date", "") else "Без даты"
                if date_str not in dates:
                    dates[date_str] = 0
                dates[date_str] += 1
            
            debug_info.append("\n📅 Распределение по датам:")
            for date_str, count in sorted(dates.items(), reverse=True)[:10]:  # 10 последних дат
                debug_info.append(f"   {date_str}: {count} записей")
            
            # Ищем завтрашние записи
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            tomorrow_apps = []
            
            for app in all_appointments:
                date_str = app.get("admission_date", "").split(" ")[0] if " " in app.get("admission_date", "") else ""
                if date_str == tomorrow:
                    tomorrow_apps.append(app)
            
            debug_info.append(f"\n🎯 Записей на завтра ({tomorrow}): {len(tomorrow_apps)}")
            
            if tomorrow_apps:
                debug_info.append("\n📋 Записи на завтра:")
                for i, app in enumerate(tomorrow_apps[:10], 1):
                    time = app.get("admission_date", "").split(" ")[1][:5] if " " in app.get("admission_date", "") else "??:??"
                    client = app.get("client", {})
                    name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
                    if not name:
                        name = f"Клиент ID:{app.get('client_id')}"
                    
                    debug_info.append(f"   {i}. {time} - {name}")
        
        return "\n".join(debug_info)
        
    except Exception as e:
        return f"❌ Ошибка при отладке: {str(e)}"

def get_real_appointments_with_debug():
    """Получение реальных записей с подробным выводом"""
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"\n🎯 Ищем записи на завтра: {tomorrow}")
    
    try:
        # Сначала пробуем получить все записи
        all_appointments = []
        
        for limit in [100, 200, 500]:
            params = {"limit": limit}
            print(f"🔍 Запрос с limit={limit}...")
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("success"):
                    appointments = data.get("data", {}).get("admission", [])
                    print(f"✅ Получено {len(appointments)} записей")
                    all_appointments.extend(appointments)
                    
                    # Проверяем формат данных
                    if appointments:
                        print(f"\n📋 Пример первой записи:")
                        first_app = appointments[0]
                        print(f"   ID: {first_app.get('id')}")
                        print(f"   Дата: {first_app.get('admission_date')}")
                        print(f"   Клиент ID: {first_app.get('client_id')}")
                        print(f"   Данные клиента: {first_app.get('client')}")
                        print(f"   Статус: {first_app.get('status')}")
                        print(f"   Active: {first_app.get('active')}")
                    
                    if len(appointments) < limit:
                        print(f"   ⚠️ Получено меньше записей чем limit, вероятно это все записи")
                        break
                else:
                    error = data.get('error', {}).get('message', 'Unknown')
                    print(f"❌ API error: {error}")
            else:
                print(f"❌ HTTP error: {response.status_code}")
        
        # Теперь фильтруем записи на завтра
        tomorrow_appointments = []
        
        print(f"\n🔍 Фильтрация записей на завтра ({tomorrow})...")
        
        for app in all_appointments:
            admission_date = app.get("admission_date", "")
            
            # Проверяем разные форматы дат
            if admission_date:
                print(f"   Проверяем запись ID {app.get('id')}: {admission_date}")
                
                # Проверяем разные форматы
                if admission_date.startswith(tomorrow):
                    tomorrow_appointments.append(app)
                    print(f"     ✅ Найдена запись на завтра!")
                else:
                    # Пробуем парсить другие форматы
                    try:
                        # Убираем временную зону если есть
                        date_str = admission_date.split("+")[0].strip() if "+" in admission_date else admission_date
                        
                        # Пробуем разные форматы
                        formats = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"]
                        
                        for fmt in formats:
                            try:
                                dt = datetime.strptime(date_str, fmt)
                                if dt.strftime("%Y-%m-%d") == tomorrow:
                                    tomorrow_appointments.append(app)
                                    print(f"     ✅ Найдена (парсинг {fmt})!")
                                    break
                            except:
                                continue
                    except:
                        pass
        
        print(f"\n📊 Результат фильтрации:")
        print(f"   Всего записей получено: {len(all_appointments)}")
        print(f"   Найдено на завтра: {len(tomorrow_appointments)}")
        
        return tomorrow_appointments
        
    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return []

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
        print(f"❌ Telegram send error: {e}")
        return False

# ============ 3. ПОЛУЧЕНИЕ И ОТПРАВКА РЕАЛЬНЫХ ДАННЫХ ============
def find_and_send_real_appointments():
    """Найти и отправить реальные записи"""
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    print(f"\n" + "="*60)
    print(f"🔍 ПОИСК РЕАЛЬНЫХ ЗАПИСЕЙ НА ЗАВТРА ({tomorrow})")
    print("="*60)
    
    # Получаем записи с дебагом
    appointments = get_real_appointments_with_debug()
    
    if not appointments:
        message = f"📭 ВНИМАНИЕ! На завтра ({tomorrow}) не найдено записей в VetManager\n\n"
        message += f"<i>Возможные причины:</i>\n"
        message += f"1. Записи в другой временной зоне\n"
        message += f"2. Другая дата в системе VetManager\n"
        message += f"3. Проблема с фильтрацией\n\n"
        message += f"<b>Проверьте:</b> https://vetmanager-bot-1.onrender.com/debug"
        
        send_telegram(ADMIN_ID, message)
        return "⚠️ Записей не найдено (см. детали в дебаге)"
    
    # Формируем сообщение
    message = f"🎯 <b>РЕАЛЬНЫЕ ЗАПИСИ НА ЗАВТРА ({tomorrow})</b>\n\n"
    message += f"<i>Найдено записей: {len(appointments)}</i>\n\n"
    
    # Группируем по врачам
    doctors = {}
    for app in appointments:
        doctor_data = app.get("user", {})
        doctor_name = doctor_data.get("last_name", doctor_data.get("login", "Неизвестный врач"))
        
        if doctor_name not in doctors:
            doctors[doctor_name] = []
        doctors[doctor_name].append(app)
    
    for doctor, apps in doctors.items():
        message += f"👨‍⚕️ <b>{doctor}:</b> {len(apps)} записей\n"
        for app in apps:
            time = app.get("admission_date", "").split(" ")[1][:5] if " " in app.get("admission_date", "") else "??:??"
            client = app.get("client", {})
            name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
            if not name:
                name = f"Клиент ID:{app.get('client_id')}"
            
            message += f"   🕒 {time} - {name}\n"
        message += "\n"
    
    message += "📊 <b>Подробная информация по каждой записи:</b>"
    
    send_telegram(ADMIN_ID, message)
    
    # Отправляем детали по каждой записи
    for i, app in enumerate(appointments, 1):
        # ID записи
        appointment_id = app.get("id", "?")
        
        # Дата и время
        admission_date = app.get("admission_date", "")
        if " " in admission_date:
            time = admission_date.split(" ")[1][:5]
        else:
            time = "??:??"
        
        # Клиент
        client = app.get("client", {})
        client_id = app.get("client_id", "")
        first_name = client.get("first_name", "").strip()
        last_name = client.get("last_name", "").strip()
        
        if first_name or last_name:
            client_name = f"{first_name} {last_name}".strip()
        else:
            client_name = f"Клиент ID:{client_id}"
        
        # Телефон
        phone = client.get("cell_phone", client.get("phone", "Не указан")).strip()
        
        # Питомец
        pet = app.get("pet", {})
        pet_name = pet.get("alias", pet.get("pet_name", "питомец")).strip()
        
        # Врач
        doctor = app.get("user", {})
        doctor_name = doctor.get("last_name", doctor.get("login", "Врач")).strip()
        
        # Описание
        description = app.get("description", "").strip()
        
        # Формируем сообщение
        detail_msg = f"📋 <b>Запись #{i}</b> (ID: {appointment_id})\n"
        detail_msg += f"🕒 <b>Время:</b> {time}\n"
        detail_msg += f"👤 <b>Клиент:</b> {client_name}\n"
        detail_msg += f"📞 <b>Телефон:</b> {phone}\n"
        detail_msg += f"👨‍⚕️ <b>Врач:</b> {doctor_name}\n"
        detail_msg += f"🐾 <b>Питомец:</b> {pet_name}\n"
        
        if description:
            if len(description) > 50:
                description = description[:50] + "..."
            detail_msg += f"📝 <b>Комментарий:</b> {description}\n"
        
        detail_msg += f"\n<b>Статус:</b> ⏳ Ожидает подтверждения"
        
        # Кнопки
        buttons = {
            "inline_keyboard": [
                [
                    {"text": "📞 Позвонить", "callback_data": f"call_{appointment_id}"},
                    {"text": "✅ Подтвердить", "callback_data": f"confirm_{appointment_id}"}
                ],
                [
                    {"text": "❌ Отменить", "callback_data": f"cancel_{appointment_id}"},
                    {"text": "👤 Подробнее", "callback_data": f"info_{appointment_id}"}
                ]
            ]
        }
        
        send_telegram(ADMIN_ID, detail_msg, buttons)
        time.sleep(0.3)  # Небольшая пауза
    
    return f"✅ Найдено и отправлено {len(appointments)} реальных записей!"

# ============ 4. ВЕБ-ИНТЕРФЕЙС ============
@app.route("/")
def home():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>VetManager Debug System</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #2c3e50; }}
            .card {{ background: #f8f9fa; border-radius: 10px; padding: 20px; margin: 15px 0; border-left: 4px solid #3498db; }}
            .btn {{ display: inline-block; background: #3498db; color: white; padding: 12px 24px; 
                   text-decoration: none; border-radius: 5px; margin: 5px; font-weight: bold; }}
            .btn:hover {{ background: #2980b9; }}
            .btn-success {{ background: #27ae60; }}
            .btn-success:hover {{ background: #219653; }}
            .btn-warning {{ background: #f39c12; }}
            .btn-warning:hover {{ background: #e67e22; }}
            .btn-danger {{ background: #e74c3c; }}
            .btn-danger:hover {{ background: #c0392b; }}
            .debug-info {{ background: #2c3e50; color: white; padding: 15px; border-radius: 5px; font-family: monospace; }}
        </style>
    </head>
    <body>
        <h1>🐛 VetManager Debug System</h1>
        
        <div class="card">
            <h2>🔍 Отладка поиска записей</h2>
            <p><b>Дата завтра:</b> {tomorrow}</p>
            <p><b>Проблема:</b> Бот не находит записи, хотя они есть</p>
            <p><b>Цель:</b> Найти причину и исправить</p>
        </div>
        
        <div class="card">
            <h3>🎯 Основные тесты</h3>
            <a class="btn btn-success" href="/find_real">🔎 Найти реальные записи</a><br><br>
            <a class="btn btn-warning" href="/debug_api">🐛 Полная отладка API</a><br><br>
            <a class="btn btn-danger" href="/force_check">💥 Принудительная проверка</a><br><br>
            <a class="btn" href="/raw_data">📊 Сырые данные</a>
        </div>
        
        <div class="card">
            <h3>📝 Описание проблемы</h3>
            <p>1. В VetManager есть записи на завтра у врачей Базарнова и Олексина</p>
            <p>2. API возвращает данные, но фильтрация не работает</p>
            <p>3. Нужно понять формат дат в системе</p>
            <p>4. Исправить фильтрацию и найти реальные записи</p>
        </div>
    </body>
    </html>
    '''

@app.route("/find_real")
def find_real():
    return find_and_send_real_appointments()

@app.route("/debug_api")
def debug_api():
    result = debug_vetmanager_api()
    
    # Отправляем в Telegram
    chunks = [result[i:i+4000] for i in range(0, len(result), 4000)]
    for chunk in chunks:
        send_telegram(ADMIN_ID, f"<pre>{chunk}</pre>")
    
    return f'''
    <div style="font-family: Arial; padding: 20px;">
        <h2>🐛 Результаты отладки</h2>
        <pre style="background: #2c3e50; color: white; padding: 15px; border-radius: 5px; overflow: auto;">
{result}
        </pre>
        <p>Результаты также отправлены в Telegram</p>
        <a href="/" class="btn">← Назад</a>
    </div>
    '''

@app.route("/force_check")
def force_check():
    """Принудительная проверка всех дат"""
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    try:
        response = requests.get(url, headers=headers, params={"limit": 100}, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("success"):
                appointments = data.get("data", {}).get("admission", [])
                
                html = "<h2>💥 ПРИНУДИТЕЛЬНАЯ ПРОВЕРКА</h2>"
                html += f"<p><b>Всего записей получено:</b> {len(appointments)}</p>"
                
                if appointments:
                    html += "<h3>📅 Все записи (первые 20):</h3>"
                    
                    for i, app in enumerate(appointments[:20], 1):
                        date_str = app.get("admission_date", "Нет даты")
                        client = app.get("client", {})
                        name = f"{client.get('first_name', '')} {client.get('last_name', '')}".strip()
                        if not name:
                            name = f"Клиент ID:{app.get('client_id')}"
                        
                        html += f"<div style='border:1px solid #ddd; padding:10px; margin:5px;'>"
                        html += f"<b>#{i}:</b> {date_str}<br>"
                        html += f"<b>Клиент:</b> {name}<br>"
                        html += f"<b>ID записи:</b> {app.get('id')}<br>"
                        html += f"<b>Данные клиента:</b> {json.dumps(client, ensure_ascii=False)[:100]}..."
                        html += "</div>"
                
                return f'''
                <!DOCTYPE html>
                <html>
                <head><style>body {{ font-family: Arial; padding: 20px; }}</style></head>
                <body>{html}<br><a href="/" class="btn">← Назад</a></body>
                </html>
                '''
    
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

@app.route("/raw_data")
def raw_data():
    """Сырые данные из API"""
    url = "https://drug14.vetmanager2.ru/rest/api/admission"
    headers = {"X-REST-API-KEY": VETMANAGER_KEY}
    
    try:
        response = requests.get(url, headers=headers, params={"limit": 5}, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            html = "<h2>📊 Сырые данные API</h2>"
            html += f"<p><b>Статус:</b> {response.status_code}</p>"
            
            html += "<h3>Полный ответ:</h3>"
            html += f"<pre style='background: #f5f5f5; padding: 15px; border-radius: 5px; overflow: auto;'>"
            html += json.dumps(data, indent=2, ensure_ascii=False)
            html += "</pre>"
            
            return f'''
            <!DOCTYPE html>
            <html>
            <head><style>body {{ font-family: Arial; padding: 20px; }}</style></head>
            <body>{html}<br><a href="/" class="btn">← Назад</a></body>
            </html>
            '''
        else:
            return f"HTTP Error: {response.status_code}"
            
    except Exception as e:
        return f"Error: {str(e)}"

# ============ 5. WEBHOOK ДЛЯ КНОПОК ============
@app.route("/webhook", methods=["POST"])
def webhook():
    """Обработка кнопок"""
    try:
        data = request.json
        
        if "callback_query" in data:
            callback = data["callback_query"]
            chat_id = callback["from"]["id"]
            callback_data = callback["data"]
            
            print(f"📲 Callback: {callback_data}")
            
            # Простая обработка
            if callback_data.startswith("call_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"📞 Для звонка по записи #{appointment_id} проверьте детали в отчете")
                
            elif callback_data.startswith("confirm_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"✅ Запись #{appointment_id} подтверждена")
                
            elif callback_data.startswith("cancel_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"❌ Запись #{appointment_id} отменена")
                
            elif callback_data.startswith("info_"):
                appointment_id = callback_data.split("_")[1]
                send_telegram(chat_id, f"👤 Детали записи #{appointment_id} будут показаны")
            
            # Ответ на callback
            answer_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
            requests.post(answer_url, json={"callback_query_id": callback["id"]})
            
        return "OK"
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return "ERROR"

# ============ 6. ЗАПУСК ============
if __name__ == "__main__":
    print("=" * 70)
    print("🔍 VETMANAGER DEBUG SYSTEM ЗАПУЩЕН!")
    print("=" * 70)
    print("🎯 ЦЕЛЬ: Найти почему бот не видит записи на завтра")
    print(f"👤 Администратор: {ADMIN_ID}")
    print("🏥 API: drug14.vetmanager2.ru")
    print("=" * 70)
    print("🌐 Веб-интерфейс для отладки:")
    print("   https://vetmanager-bot-1.onrender.com/")
    print("   https://vetmanager-bot-1.onrender.com/find_real")
    print("   https://vetmanager-bot-1.onrender.com/debug_api")
    print("=" * 70)
    
    # Автоматический запуск отладки при старте
    print("\n🚀 Запускаю автоматическую отладку...")
    result = find_and_send_real_appointments()
    print(f"Результат: {result}")
    
    app.run(host="0.0.0.0", port=5000, debug=False)
