from flask import Flask, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

# ========== КОНФИГУРАЦИЯ ==========
TELEGRAM_TOKEN = '8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI'
VETMANAGER_KEY = '29607ccc63c684fa672be9694f7f09ec'  # ТВОЙ НОВЫЙ КЛЮЧ
ADMIN_ID = 921853682

# ========== ФУНКЦИИ ==========
def test_vetmanager():
    """Тест API VetManager"""
    try:
        headers = {'X-User-Token': VETMANAGER_KEY, 'Accept': 'application/json'}
        response = requests.get(
            'https://drug14.vetmanager2.ru/rest/api/client?limit=1',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'status': '✅ API работает',
                'clients_count': len(data.get('data', [])),
                'message': data.get('message', 'Успешно')
            }
        else:
            return {
                'success': False,
                'status': f'❌ Ошибка {response.status_code}',
                'error': response.text[:200]
            }
    except Exception as e:
        return {'success': False, 'status': '❌ Ошибка подключения', 'error': str(e)}

def send_telegram(text):
    """Отправка в Telegram"""
    try:
        response = requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            json={'chat_id': ADMIN_ID, 'text': text, 'parse_mode': 'HTML'}
        )
        return response.status_code == 200
    except:
        return False

# ========== ВЕБ-СТРАНИЦЫ ==========
@app.route('/')
def home():
    test_result = test_vetmanager()
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>VetManager Bot</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial; margin: 40px; background: #f0f2f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .status {{ padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .success {{ background: #d4edda; color: #155724; border-left: 5px solid #28a745; }}
            .error {{ background: #f8d7da; color: #721c24; border-left: 5px solid #dc3545; }}
            .btn {{ display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 5px; }}
            .btn:hover {{ background: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 VetManager Reminder Bot</h1>
            
            <div class="status {'success' if test_result['success'] else 'error'}">
                <h3>📊 Статус системы</h3>
                <p><strong>API VetManager:</strong> {test_result['status']}</p>
                <p><strong>Ключ:</strong> {VETMANAGER_KEY[:8]}...{VETMANAGER_KEY[-8:]}</p>
                <p><strong>Время:</strong> {datetime.now().strftime("%H:%M:%S")}</p>
                {'<p>✅ Клиентов в базе: ' + str(test_result['clients_count']) + '</p>' if test_result.get('clients_count') else ''}
                {'<p><small>Ошибка: ' + test_result.get('error', '') + '</small></p>' if not test_result['success'] else ''}
            </div>
            
            <div>
                <h3>⚡ Действия</h3>
                <a href="/test" class="btn">🧪 Тест API</a>
                <a href="/telegram" class="btn">📱 Тест Telegram</a>
                <a href="/check" class="btn">🔔 Проверить записи</a>
                <a href="/debug" class="btn">🔧 Диагностика</a>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/test')
def test():
    """Тест API"""
    result = test_vetmanager()
    return jsonify(result)

@app.route('/telegram')
def telegram_test():
    """Тест Telegram"""
    success = send_telegram(f"✅ Тест Telegram\nВремя: {datetime.now().strftime('%H:%M:%S')}\nКлюч: {VETMANAGER_KEY[:8]}...")
    return jsonify({'success': success, 'message': 'Сообщение отправлено' if success else 'Ошибка отправки'})

@app.route('/check')
def check():
    """Проверка записей на завтра"""
    result = test_vetmanager()
    
    if result['success']:
        message = f"📅 Проверка записей\n\n✅ API работает\nКлиентов: {result['clients_count']}\nВремя: {datetime.now().strftime('%H:%M:%S')}"
        send_telegram(message)
        return jsonify({'status': 'success', 'message': 'Проверка выполнена'})
    else:
        send_telegram(f"❌ Ошибка API\n{result.get('error', 'Неизвестная ошибка')}")
        return jsonify({'status': 'error', 'message': 'Ошибка API'})

@app.route('/debug')
def debug():
    """Полная диагностика"""
    vet_test = test_vetmanager()
    telegram_test = send_telegram(f"🔧 Диагностика системы\nВремя: {datetime.now().strftime('%H:%M:%S')}")
    
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'vetmanager': vet_test,
        'telegram': '✅ Работает' if telegram_test else '❌ Ошибка',
        'api_key': VETMANAGER_KEY[:10] + '...',
        'endpoints': {
            'home': '/',
            'test': '/test',
            'telegram': '/telegram',
            'check': '/check',
            'debug': '/debug'
        }
    })

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    
    # Приветственное сообщение
    print(f"🚀 Запуск VetManager Bot на порту {port}")
    print(f"🔑 API ключ: {VETMANAGER_KEY[:8]}...")
    
    # Тест при запуске
    test_result = test_vetmanager()
    if test_result['success']:
        print(f"✅ VetManager API доступен")
        send_telegram(f"🚀 VetManager Bot запущен!\n✅ API работает\nКлиентов: {test_result.get('clients_count', 0)}")
    else:
        print(f"❌ VetManager API недоступен: {test_result.get('error', '')}")
        send_telegram(f"🚀 VetManager Bot запущен\n⚠️ API ошибка: {test_result.get('error', '')[:100]}")
    
    app.run(host='0.0.0.0', port=port, debug=False)
