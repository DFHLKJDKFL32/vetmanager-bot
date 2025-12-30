import os
import requests
from datetime import datetime

print("VET MANAGER BOT - SIMPLE VERSION")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8516044859:AAFaJg3HeNMHhw-xV4Nm2goMbLmiFnmJDKI")
ADMIN_ID = int(os.getenv("ADMIN_ID", 921853682))

def send_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json().get("ok", False)
    except:
        return False

if __name__ == "__main__":
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    message = f"✅ Bot started\nTime: {datetime.now().strftime('%H:%M:%S')}"
    
    if send_telegram(ADMIN_ID, message):
        print("SUCCESS: Message sent!")
    else:
        print("ERROR: Can't send message")
    
    # Keep running
    import time
    while True:
        time.sleep(60)
        print("Still alive...")
