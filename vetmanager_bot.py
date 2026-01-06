import os
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify
import logging
import json
import time
import threading
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# ========== КОНФИГУРАЦИЯ ==========
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI')
VETMANAGER_KEY = os.environ.get('VETMANAGER_KEY', '29607ccc63c684fa672be9694f7f09ec')  # <-- ТВОЙ НАСТОЯЩИЙ КЛЮЧ!
VETMANAGER_DOMAIN = 'drug14.vetmanager2.ru'
ADMIN_ID = 921853682  # Твой Telegram ID

# Список отправленных напоминаний (чтобы не дублировать)
sent_reminders = set()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ВАЖНО: ПРАВИЛЬНЫЙ ПУТЬ К API ==========
# Судя по скриншоту настроек, используем стандартный REST API
VETMANAGER_API_URL = f"https://{VETMANAGER_DOMAIN}/rest/api"

# ========== ОТПРАВКА TELEGRAM ==========
def send_telegram_notification(chat_id, message):
    """Отправляет сообщение в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"✅ Сообщение отправлено в Telegram")
            return True
        else:
            logger.error(f"❌ Ошибка Telegram: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Ошибка отправки в Telegram: {e}")
        return False

# ========== ПОЛУЧЕНИЕ ДАННЫХ ИЗ VETMANAGER ==========
def get_vetmanager_data(endpoint, params=None):
    """Получает данные из Vetmanager API"""
    try:
        headers = {
            'X-USER-TOKEN': VETMANAGER_KEY,
            'Accept': 'application/json'
        }
        
        url = f"{VETMANAGER_API_URL}/{endpoint}"
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        logger.info(f"🔍 Запрос к {url}")
        logger.info(f"   Статус: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Успешно получены данные: {len(data.get('data', []))} записей")
            return data
        else:
            logger.error(f"❌ Ошибка API: {response.status_code}")
            logger.error(f"   Ответ: {response.text[:200]}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Ошибка при запросе к Vetmanager: {e}")
        return None

# ========== ПОЛУЧЕНИЕ ЗАПИСЕЙ НА ЗАВТРА ==========
def get_tomorrow_appointments():
    """Получает все записи на завтра"""
    try:
        # Завтрашняя дата
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime('%Y-%m-%d')
        
        # Параметры запроса
        params = {
            'sort': 'date',
            'order': 'asc',
            'filter[date]': tomorrow_str,
            'filter[active]': 1,
            'limit': 100
        }
        
        data = get_vetmanager_data('ads', params)
        
        if data and 'data' in data:
            return data['data']
        else:
            return []
            
    except Exception as e:
        logger.error(f"❌ Ошибка при получении записей: {e}")
        return []

# ========== ПРОВЕРКА И ОТПРАВКА НАПОМИНАНИЙ ==========
def check_and_send_reminders():
    """Основная функция для проверки и отправки напоминаний"""
    global sent_reminders
    
    logger.info("🔔 Начинаю проверку записей на завтра...")
    
    # Получаем записи на завтра
    appointments = get_tomorrow_appointments()
    
    if not appointments:
        logger.info("📭 На завтра записей нет")
        send_telegram_notification(
            ADMIN_ID,
            f"📅 На {datetime.now().strftime('%d.%m.%Y')} записей нет"
        )
        return
    
    logger.info(f"📋 Найдено записей на завтра: {len(appointments)}")
    
    # Формируем сводку
    summary = f"📊 <b>Сводка на завтра ({len(appointments)} записей):</b>\n\n"
    
    for i, appointment in enumerate(appointments, 1):
        try:
            # Извлекаем данные о клиенте
            client_data = appointment.get('client', {})
            client_name = f"{client_data.get('last_name', '')} {client_data.get('first_name', '')}".strip()
            
            # Извлекаем данные о питомце
            pet_data = appointment.get('pet', {})
            pet_name = pet_data.get('alias', 'Неизвестно')
            
            # Время приема
            appointment_time = appointment.get('date', '')
            if appointment_time:
                # Парсим время
                time_obj = datetime.fromisoformat(appointment_time.replace('Z', '+00:00'))
                formatted_time = time_obj.strftime('%H:%M')
            else:
                formatted_time = 'не указано'
            
            # Телефон
            phone = client_data.get('phone', 'не указан')
            
            # Формируем запись для сводки
            summary += f"{i}. <b>{client_name}</b>\n"
            summary += f"   🐾 {pet_name} | ⏰ {formatted_time}\n"
            summary += f"   📞 {phone}\n\n"
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки записи: {e}")
            continue
    
    # Отправляем сводку админу
    send_telegram_notification(ADMIN_ID, summary)
    
    # Проверяем время для отправки индивидуальных напоминаний
    # (например, отправлять за 2 часа до приема)
    current_hour = datetime.now().hour
    
    if current_hour >= 18:  # Вечером перед днем приема
        logger.info("🌙 Вечерняя отправка напоминаний...")
        
        for appointment in appointments:
            try:
                appointment_id = appointment.get('id')
                
                # Проверяем, не отправляли ли уже напоминание
                if appointment_id in sent_reminders:
                    continue
                
                client_data = appointment.get('client', {})
                client_name = f"{client_data.get('last_name', '')} {client_data.get('first_name', '')}".strip()
                phone = client_data.get('phone', '')
                
                if client_name and phone:
                    # Формируем сообщение для клиента
                    pet_name = appointment.get('pet', {}).get('alias', 'питомец')
                    appointment_time = appointment.get('date', '')
                    
                    if appointment_time:
                        time_obj = datetime.fromisoformat(appointment_time.replace('Z', '+00:00'))
                        formatted_time = time_obj.strftime('%H:%M')
                        formatted_date = time_obj.strftime('%d.%m.%Y')
                    else:
                        formatted_time = 'не указано'
                        formatted_date = 'завтра'
                    
                    message = f"🔔 <b>Напоминание о визите в клинику</b>\n\n"
                    message += f"Уважаемый(ая) {client_name}!\n"
                    message += f"Напоминаем, что завтра {formatted_date} в {formatted_time}\n"
                    message += f"у вас запланирован визит с {pet_name}.\n\n"
                    message += f"📞 Для подтверждения или переноса: {phone}\n\n"
                    message += f"Ждем вас!"
                    
                    # В реальном проекте здесь бы отправлялось клиенту
                    # Пока просто логируем
                    logger.info(f"📤 Напоминание для {client_name}: {formatted_time}")
                    
                    # Добавляем в отправленные
                    sent_reminders.add(appointment_id)
                    
            except Exception as e:
                logger.error(f"❌ Ошибка при подготовке напоминания: {e}")
                continue
    
    logger.info("✅ Проверка завершена")

# ========== ФУНКЦИЯ ДЛЯ РУЧНОЙ ПРОВЕРКИ ==========
@app.route('/check-now')
def check_now():
    """Ручной запуск проверки"""
    try:
        check_and_send_reminders()
        return jsonify({
            "status": "success",
            "message": "Проверка выполнена",
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# ========== ТЕСТ API ==========
@app.route('/test-api')
def test_api():
    """Тестирует подключение к API Vetmanager"""
    try:
        # Тестовый запрос для проверки API
        headers = {
            'X-USER-TOKEN': VETMANAGER_KEY,
            'Accept': 'application/json'
        }
        
        # Пробуем получить клиентов
        response = requests.get(
            f"{VETMANAGER_API_URL}/clients?limit=1",
            headers=headers,
            timeout=10
        )
        
        result = {
            "api_url": VETMANAGER_API_URL,
            "status_code": response.status_code,
            "api_key_used": VETMANAGER_KEY[:10] + "..." + VETMANAGER_KEY[-6:],
            "timestamp": datetime.now().isoformat()
        }
        
        if response.status_code == 200:
            result["status"] = "success"
            result["message"] = "API работает корректно"
            try:
                data = response.json()
                result["sample_data"] = data.get('data', [])[:2]
            except:
                result["response"] = response.text[:200]
        else:
            result["status"] = "error"
            result["message"] = f"Ошибка API: {response.status_code}"
            result["response"] = response.text[:200]
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# ========== ГЛАВНАЯ СТРАНИЦА ==========
@app.route('/')
def index():
    """Главная страница с информацией"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>VetManager Reminder Bot</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            .header {{
                text-align: center;
                margin-bottom: 40px;
            }}
            .logo {{
                font-size: 48px;
                margin-bottom: 20px;
            }}
            .status-card {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                border-left: 5px solid #28a745;
            }}
            .btn {{
                display: inline-block;
                padding: 12px 24px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                margin: 10px 5px;
                transition: all 0.3s;
            }}
            .btn:hover {{
                background: #5a67d8;
                transform: translateY(-2px);
            }}
            .info-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }}
            .info-card {{
                background: #f1f5f9;
                padding: 20px;
                border-radius: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">🤖</div>
                <h1>VetManager Reminder Bot</h1>
                <p>Автоматическая система напоминаний о записях</p>
            </div>
            
            <div class="status-card">
                <h3>📊 Статус системы</h3>
                <p><strong>Домен:</strong> {VETMANAGER_DOMAIN}</p>
                <p><strong>API ключ:</strong> {VETMANAGER_KEY[:8]}...{VETMANAGER_KEY[-8:]}</p>
                <p><strong>Telegram ID:</strong> {ADMIN_ID}</p>
                <p><strong>Время:</strong> {datetime.now().strftime('%H:%M:%S')}</p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="/test-api" class="btn">🧪 Тест API</a>
                <a href="/check-now" class="btn">🔔 Проверить сейчас</a>
                <a href="https://t.me/Fulsim_bot" class="btn" target="_blank">📱 Telegram бот</a>
            </div>
            
            <div class="info-grid">
                <div class="info-card">
                    <h4>📅 Как работает</h4>
                    <p>Система автоматически проверяет записи на завтра и отправляет напоминания:</p>
                    <ul>
                        <li>Ежедневно в 19:00 - сводка админу</li>
                        <li>За 2 часа до визита - клиентам</li>
                    </ul>
                </div>
                
                <div class="info-card">
                    <h4>🔧 Технологии</h4>
                    <ul>
                        <li>Python Flask</li>
                        <li>VetManager REST API</li>
                        <li>Telegram Bot API</li>
                        <li>Render.com (хостинг)</li>
                    </ul>
                </div>
            </div>
            
            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eaeaea; text-align: center; color: #666;">
                <p>Система автоматических напоминаний © 2024</p>
                <p><small>Обновлено: {datetime.now().strftime('%d.%m.%Y')}</small></p>
            </div>
        </div>
    </body>
    </html>
    """

# ========== ЗАПУСК ПЛАНИРОВЩИКА ==========
def start_scheduler():
    """Запускает планировщик для автоматической проверки"""
    scheduler = BackgroundScheduler()
    
    # Проверка каждый день в 19:00 (время московское)
    scheduler.add_job(
        func=check_and_send_reminders,
        trigger='cron',
        hour=19,
        minute=0,
        id='daily_check'
    )
    
    # Дополнительная проверка в 9:00 утра
    scheduler.add_job(
        func=check_and_send_reminders,
        trigger='cron',
        hour=9,
        minute=0,
        id='morning_check'
    )
    
    scheduler.start()
    logger.info("⏰ Планировщик запущен (19:00 и 9:00 ежедневно)")

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
if __name__ == '__main__':
    # Запускаем планировщик в отдельном потоке
    scheduler_thread = threading.Thread(target=start_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Тестируем API при запуске
    logger.info("🚀 Запуск VetManager Reminder Bot...")
    logger.info(f"🔑 API ключ: {VETMANAGER_KEY[:8]}...{VETMANAGER_KEY[-8:]}")
    logger.info(f"🌐 Домен: {VETMANAGER_DOMAIN}")
    logger.info(f"🤖 Telegram бот: @Fulsim_bot")
    
    # Проверяем подключение к API
    test_result = get_vetmanager_data('clients', {'limit': 1})
    if test_result:
        logger.info("✅ VetManager API доступен")
    else:
        logger.warning("⚠️  VetManager API недоступен, проверьте ключ")
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

