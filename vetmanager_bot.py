import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify
import logging
import re

app = Flask(__name__)

# ========== КОНФИГУРАЦИЯ ==========
# Получаем переменные из Render Environment Variables
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI')
VETMANAGER_KEY = os.environ.get('VETMANAGER_KEY', '487bc6-4a39ee-be14b6-1ef17a-be257f')

# ФИКСИРУЕМ ПРОБЛЕМУ: если есть VETMANAGER_URL, извлекаем из него домен
VETMANAGER_URL = os.environ.get('VETMANAGER_URL', '')
if VETMANAGER_URL:
    # Извлекаем домен из URL: https://drug14.vetmanager2.ru → drug14.vetmanager2.ru
    if '://' in VETMANAGER_URL:
        domain = VETMANAGER_URL.split('://')[1]
    else:
        domain = VETMANAGER_URL
    VETMANAGER_DOMAIN = domain
else:
    # Если VETMANAGER_URL нет, используем стандартный
    VETMANAGER_DOMAIN = 'drug14.vetmanager2.ru'

# Формируем полный URL
VETMANAGER_API_URL = f'https://{VETMANAGER_DOMAIN}/api'
ADMIN_ID = 921853682

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Логируем настройки при запуске
logger.info("=" * 60)
logger.info("🚀 ЗАПУСК VETMANAGER BOT")
logger.info("=" * 60)
logger.info(f"TELEGRAM_TOKEN: {TELEGRAM_TOKEN[:10]}...")
logger.info(f"VETMANAGER_KEY: {VETMANAGER_KEY[:10]}...{VETMANAGER_KEY[-6:]}")
logger.info(f"VETMANAGER_DOMAIN: {VETMANAGER_DOMAIN}")
logger.info(f"VETMANAGER_API_URL: {VETMANAGER_API_URL}")
logger.info("=" * 60)

# ========== ПРОВЕРКА API ==========
def check_api():
    """Проверяет подключение к Vetmanager API"""
    logger.info("🔌 Проверяю API подключение...")
    
    if not VETMANAGER_KEY:
        return False, "❌ API ключ не установлен", 0
    
    url = f"{VETMANAGER_API_URL}/clients"
    headers = {"X-User-Token": VETMANAGER_KEY}
    
    try:
        response = requests.get(url, headers=headers, params={"limit": 1}, timeout=10)
        logger.info(f"📊 Статус ответа: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                client_count = len(data['data'])
                logger.info(f"✅ API работает! Клиентов: {client_count}")
                return True, "✅ API подключен успешно", client_count
            else:
                return False, "❌ Некорректный формат ответа", 0
        elif response.status_code == 401:
            return False, "❌ Ошибка 401: Неверный API ключ", 0
        elif response.status_code == 403:
            return False, "❌ Ошибка 403: Доступ запрещен", 0
        else:
            return False, f"❌ Ошибка {response.status_code}", 0
            
    except Exception as e:
        logger.error(f"❌ Ошибка подключения: {e}")
        return False, f"❌ Ошибка: {str(e)}", 0

# ========== ВЕБ-ИНТЕРФЕЙС ==========
@app.route('/')
def index():
    """Главная страница"""
    api_working, message, client_count = check_api()
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Vetmanager Bot Status</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f8f9fa;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                padding: 30px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                padding-bottom: 20px;
                border-bottom: 2px solid #eee;
                margin-bottom: 30px;
            }}
            .status {{
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                font-size: 1.2em;
            }}
            .success {{
                background: #d4edda;
                color: #155724;
                border: 2px solid #c3e6cb;
            }}
            .error {{
                background: #f8d7da;
                color: #721c24;
                border: 2px solid #f5c6cb;
            }}
            .config {{
                background: #e8f4fd;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                font-family: monospace;
            }}
            .btn {{
                display: inline-block;
                padding: 10px 20px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 5px;
            }}
            .btn:hover {{
                background: #0056b3;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏥 Vetmanager Telegram Bot</h1>
                <p>Ветеринарная Клиника Друг, Невинномысск</p>
            </div>
            
            <div class="status {'success' if api_working else 'error'}">
                <h2>{'✅ API РАБОТАЕТ' if api_working else '❌ API НЕДОСТУПЕН'}</h2>
                <p><strong>Статус:</strong> {message}</p>
                {'<p><strong>Клиентов в базе:</strong> ' + str(client_count) + '</p>' if client_count > 0 else ''}
                <p><strong>Время проверки:</strong> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            </div>
            
            <div class="config">
                <h3>🔧 Конфигурация системы</h3>
                <p><strong>TELEGRAM_TOKEN:</strong> {TELEGRAM_TOKEN[:10]}...{TELEGRAM_TOKEN[-6:] if len(TELEGRAM_TOKEN) > 6 else ''}</p>
                <p><strong>VETMANAGER_KEY:</strong> {VETMANAGER_KEY[:10]}...{VETMANAGER_KEY[-6:]}</p>
                <p><strong>VETMANAGER_DOMAIN:</strong> {VETMANAGER_DOMAIN}</p>
                <p><strong>VETMANAGER_API_URL:</strong> {VETMANAGER_API_URL}</p>
                <p><strong>ADMIN_ID:</strong> {ADMIN_ID}</p>
            </div>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="/test" class="btn">🧪 Тест API</a>
                <a href="/check" class="btn">🔄 Проверить</a>
                <a href="https://t.me/Fulsim_bot" class="btn" target="_blank">🤖 Telegram бот</a>
            </div>
            
            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666;">
                <p>Если API не работает, проверьте:</p>
                <ol>
                    <li>Правильность API ключа в Vetmanager</li>
                    <li>Доступ к домену {VETMANAGER_DOMAIN}</li>
                    <li>Права доступа API ключа</li>
                    <li>Логи в панели Render</li>
                </ol>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/check')
def check():
    """API для проверки подключения"""
    api_working, message, client_count = check_api()
    return jsonify({
        "status": "success" if api_working else "error",
        "message": message,
        "client_count": client_count,
        "domain": VETMANAGER_DOMAIN,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/test')
def test():
    """Страница тестирования"""
    return """
    <html>
    <body style="font-family: Arial; padding: 20px;">
        <h1>🧪 Тест Vetmanager API</h1>
        
        <h3>1. Проверка подключения:</h3>
        <div id="test-result">Проверяю...</div>
        
        <h3>2. Тест вручную через cURL:</h3>
        <pre id="curl-command"></pre>
        
        <h3>3. Что делать если не работает:</h3>
        <ol>
            <li>Проверьте API ключ в Vetmanager</li>
            <li>Убедитесь, что сайт доступен: <a href="https://drug14.vetmanager2.ru" target="_blank">drug14.vetmanager2.ru</a></li>
            <li>Проверьте логи в Render</li>
            <li>Свяжитесь с поддержкой Vetmanager</li>
        </ol>
        
        <script>
            // Показываем curl команду
            document.getElementById('curl-command').textContent = 
                'curl -H "X-User-Token: YOUR_API_KEY" \\\\\n' +
                '     "https://drug14.vetmanager2.ru/api/clients?limit=1"';
            
            // Выполняем тест
            fetch('/check')
                .then(r => r.json())
                .then(data => {
                    const div = document.getElementById('test-result');
                    if (data.status === 'success') {
                        div.innerHTML = `<div style="background: #d4edda; padding: 15px; border-radius: 8px;">
                            <h4>✅ API работает!</h4>
                            <p>Сообщение: ${data.message}</p>
                            <p>Клиентов: ${data.client_count}</p>
                            <p>Домен: ${data.domain}</p>
                        </div>`;
                    } else {
                        div.innerHTML = `<div style="background: #f8d7da; padding: 15px; border-radius: 8px;">
                            <h4>❌ API не работает</h4>
                            <p>Ошибка: ${data.message}</p>
                            <p>Проверьте настройки подключения</p>
                        </div>`;
                    }
                });
        </script>
    </body>
    </html>
    """

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    # Проверяем подключение при запуске
    api_working, message, client_count = check_api()
    logger.info(f"Результат проверки: {message}")
    
    # Запускаем сервер
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
