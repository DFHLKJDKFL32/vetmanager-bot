import os
import requests
from datetime import datetime
from flask import Flask, jsonify
import logging
import json

app = Flask(__name__)

# ========== КОНФИГУРАЦИЯ ==========
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI')
VETMANAGER_KEY = os.environ.get('VETMANAGER_KEY', '487bc6-4a39ee-be14b6-1ef17a-be257f')
VETMANAGER_DOMAIN = 'drug14.vetmanager2.ru'
ADMIN_ID = 921853682

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ПОИСК ПРАВИЛЬНОГО API ПУТИ ==========
def test_api_path(path_name, url, headers):
    """Тестирует конкретный путь API"""
    try:
        logger.info(f"🔍 Тестирую {path_name}: {url}")
        response = requests.get(url, headers=headers, params={"limit": 1}, timeout=10)
        
        logger.info(f"   Статус: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                logger.info(f"   ✅ УСПЕХ! Ответ JSON: {data.keys()}")
                return True, path_name, url, data
            except json.JSONDecodeError:
                logger.info(f"   Ответ не JSON: {response.text[:100]}")
                return False, path_name, url, response.text[:200]
        else:
            logger.info(f"   Ответ: {response.text[:200]}")
            return False, path_name, url, f"Status {response.status_code}: {response.text[:200]}"
            
    except Exception as e:
        logger.error(f"   ❌ Ошибка: {e}")
        return False, path_name, url, str(e)

def find_api_path():
    """Находит рабочий путь к API Vetmanager"""
    headers = {"X-User-Token": VETMANAGER_KEY}
    
    # ВСЕ ВОЗМОЖНЫЕ ПУТИ ДЛЯ VETMANAGER
    api_tests = [
        # Основные пути через index.php (самые вероятные)
        ("index.php?module=ApiRest", f"https://{VETMANAGER_DOMAIN}/index.php?module=ApiRest"),
        ("api.php", f"https://{VETMANAGER_DOMAIN}/api.php"),
        
        # Разные варианты с параметрами
        ("api/rest", f"https://{VETMANAGER_DOMAIN}/api/rest"),
        ("rest/api", f"https://{VETMANAGER_DOMAIN}/rest/api"),
        
        # Стандартные пути
        ("/api", f"https://{VETMANAGER_DOMAIN}/api"),
        ("/api/v2", f"https://{VETMANAGER_DOMAIN}/api/v2"),
        ("/api/v1", f"https://{VETMANAGER_DOMAIN}/api/v1"),
    ]
    
    # Тестируем клиентов для каждого пути
    working_paths = []
    
    for path_name, base_url in api_tests:
        # Формируем URL для получения клиентов
        if "?" in base_url:
            url = f"{base_url}&object=Client&action=get&limit=1"
        else:
            url = f"{base_url}/clients?limit=1"
        
        success, path_name, url, result = test_api_path(path_name, url, headers)
        
        if success:
            working_paths.append({
                "name": path_name,
                "url": url,
                "result": result
            })
    
    return working_paths

# ========== ТЕСТИРОВАНИЕ ПРИ ЗАПУСКЕ ==========
logger.info("=" * 60)
logger.info("🚀 ПОИСК РАБОЧЕГО API ПУТИ VETMANAGER")
logger.info("=" * 60)

working_paths = find_api_path()

if working_paths:
    logger.info(f"✅ Найдено рабочих путей: {len(working_paths)}")
    for path in working_paths:
        logger.info(f"📡 Путь: {path['name']}")
        logger.info(f"   URL: {path['url']}")
else:
    logger.error("❌ Не найдено рабочих API путей!")

# ========== ВЕБ-ИНТЕРФЕЙС ==========
@app.route('/')
def index():
    """Главная страница диагностики"""
    
    # Формируем HTML с результатами тестирования
    results_html = ""
    
    if working_paths:
        for path in working_paths:
            results_html += f"""
            <div style="background: #d4edda; padding: 15px; margin: 10px 0; border-radius: 8px;">
                <h3>✅ {path['name']}</h3>
                <p><strong>URL:</strong> {path['url']}</p>
                <p><strong>Ответ:</strong> {json.dumps(path.get('result', {}), ensure_ascii=False)[:200]}...</p>
            </div>
            """
    else:
        results_html = """
        <div style="background: #f8d7da; padding: 20px; border-radius: 8px;">
            <h3>❌ Не найдено рабочих API путей!</h3>
            <p>Возможные причины:</p>
            <ol>
                <li>Неверный API ключ</li>
                <li>API отключен в настройках Vetmanager</li>
                <li>Нужны другие параметры запроса</li>
                <li>Требуется другая авторизация</li>
            </ol>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Vetmanager API Диагностика</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f5f5f5;
            }}
            .container {{
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                padding-bottom: 20px;
                border-bottom: 2px solid #eee;
                margin-bottom: 30px;
            }}
            .api-test {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                margin: 15px 0;
                font-family: monospace;
                overflow-x: auto;
            }}
            .test-buttons {{
                display: flex;
                gap: 10px;
                margin: 20px 0;
                flex-wrap: wrap;
            }}
            .btn {{
                display: inline-block;
                padding: 10px 20px;
                background: #007bff;
                color: white;
                text-decoration: none;
                border-radius: 5px;
            }}
            .btn:hover {{
                background: #0056b3;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔍 Vetmanager API Диагностика</h1>
                <p><strong>Домен:</strong> {VETMANAGER_DOMAIN}</p>
                <p><strong>API ключ:</strong> {VETMANAGER_KEY[:10]}...{VETMANAGER_KEY[-6:]}</p>
                <p><strong>Время проверки:</strong> {datetime.now().strftime('%H:%M:%S')}</p>
            </div>
            
            <h2>📊 Результаты тестирования API путей</h2>
            {results_html}
            
            <div class="api-test">
                <h3>🧪 Ручной тест API:</h3>
                <p>Попробуйте выполнить в терминале:</p>
                <pre>
curl -H "X-User-Token: {VETMANAGER_KEY}" \\
     "https://{VETMANAGER_DOMAIN}/index.php?module=ApiRest&object=Client&action=get&limit=1"
                </pre>
                
                <p>Или эту команду:</p>
                <pre>
curl -H "X-User-Token: {VETMANAGER_KEY}" \\
     "https://{VETMANAGER_DOMAIN}/api.php?object=Client&action=get&limit=1"
                </pre>
            </div>
            
            <div style="margin-top: 30px;">
                <h3>🔗 Полезные ссылки для тестирования:</h3>
                <div class="test-buttons">
                    <a href="/test-all" class="btn">Тест всех путей</a>
                    <a href="/check" class="btn">Проверить API</a>
                    <a href="/test-manual" class="btn">Ручной тест</a>
                    <a href="https://t.me/Fulsim_bot" class="btn" target="_blank">Telegram бот</a>
                </div>
            </div>
            
            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666;">
                <h4>📋 Инструкция для разработчиков Vetmanager:</h4>
                <p>Чтобы включить API в Vetmanager:</p>
                <ol>
                    <li>Зайдите в админ-панель Vetmanager</li>
                    <li>Найдите настройки API/REST</li>
                    <li>Включите API доступ</li>
                    <li>Создайте API ключ с правами на чтение клиентов</li>
                    <li>Укажите правильный URL для API запросов</li>
                </ol>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/test-all')
def test_all():
    """Тестирует все возможные пути"""
    return """
    <html>
    <head>
        <title>Тест всех API путей</title>
        <script>
        async function testPath(path, url) {
            const resultDiv = document.getElementById(`result-${path}`);
            resultDiv.innerHTML = '🔄 Тестирую...';
            
            try {
                const response = await fetch(url, {
                    method: 'GET',
                    headers: {
                        'X-User-Token': '487bc6-4a39ee-be14b6-1ef17a-be257f'
                    }
                });
                
                if (response.ok) {
                    const data = await response.text();
                    resultDiv.innerHTML = `<span style="color: green;">✅ 200 OK</span><br><small>${data.substring(0, 100)}...</small>`;
                } else {
                    resultDiv.innerHTML = `<span style="color: red;">❌ ${response.status} ${response.statusText}</span>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<span style="color: red;">❌ Ошибка: ${error.message}</span>`;
            }
        }
        
        // Автоматически тестируем все пути при загрузке
        window.onload = function() {
            const paths = [
                {name: 'index.php?module=ApiRest', url: 'https://drug14.vetmanager2.ru/index.php?module=ApiRest&object=Client&action=get&limit=1'},
                {name: 'api.php', url: 'https://drug14.vetmanager2.ru/api.php?object=Client&action=get&limit=1'},
                {name: '/api/clients', url: 'https://drug14.vetmanager2.ru/api/clients?limit=1'},
                {name: '/rest/api/clients', url: 'https://drug14.vetmanager2.ru/rest/api/clients?limit=1'},
                {name: '/api/v2/clients', url: 'https://drug14.vetmanager2.ru/api/v2/clients?limit=1'}
            ];
            
            paths.forEach(path => {
                testPath(path.name.replace(/[^a-zA-Z0-9]/g, '-'), path.url);
            });
        }
        </script>
    </head>
    <body style="font-family: Arial; padding: 20px;">
        <h1>🧪 Тест всех путей API</h1>
        
        <div id="test-index-php" style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 5px;">
            <h3>index.php?module=ApiRest</h3>
            <div id="result-index-php-module-ApiRest">Ожидание...</div>
        </div>
        
        <div id="test-api-php" style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 5px;">
            <h3>api.php</h3>
            <div id="result-api-php">Ожидание...</div>
        </div>
        
        <div id="test-api-clients" style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 5px;">
            <h3>/api/clients</h3>
            <div id="result-api-clients">Ожидание...</div>
        </div>
        
        <div id="test-rest-api-clients" style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 5px;">
            <h3>/rest/api/clients</h3>
            <div id="result-rest-api-clients">Ожидание...</div>
        </div>
        
        <div id="test-api-v2-clients" style="margin: 15px 0; padding: 15px; background: #f8f9fa; border-radius: 5px;">
            <h3>/api/v2/clients</h3>
            <div id="result-api-v2-clients">Ожидание...</div>
        </div>
        
        <div style="margin-top: 30px;">
            <a href="/">Назад к диагностике</a>
        </div>
    </body>
    </html>
    """

@app.route('/check')
def check():
    """API endpoint для проверки"""
    return jsonify({
        "status": "testing",
        "working_paths": len(working_paths),
        "domain": VETMANAGER_DOMAIN,
        "api_key_set": bool(VETMANAGER_KEY),
        "timestamp": datetime.now().isoformat(),
        "details": working_paths if working_paths else "No working paths found"
    })

@app.route('/test-manual')
def test_manual():
    """Ручной тест"""
    return """
    <html>
    <body style="font-family: Arial; padding: 20px;">
        <h1>🔧 Ручной тест API Vetmanager</h1>
        
        <h3>1. Тест через index.php (самый вероятный):</h3>
        <pre>
https://drug14.vetmanager2.ru/index.php
?module=ApiRest
&object=Client
&action=get
&limit=1
&key=487bc6-4a39ee-be14b6-1ef17a-be257f
        </pre>
        
        <h3>2. Тест через api.php:</h3>
        <pre>
https://drug14.vetmanager2.ru/api.php
?object=Client
&action=get
&limit=1
&key=487bc6-4a39ee-be14b6-1ef17a-be257f
        </pre>
        
        <h3>3. Что делать если не работает:</h3>
        <ol>
            <li>Зайдите в админку Vetmanager: https://drug14.vetmanager2.ru</li>
            <li>Найдите раздел "API" или "REST API"</li>
            <li>Включите API доступ</li>
            <li>Посмотрите примеры API запросов</li>
            <li>Скопируйте правильный URL</li>
        </ol>
        
        <div style="margin-top: 30px;">
            <a href="/">Назад</a>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
