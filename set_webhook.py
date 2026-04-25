import requests
from config import BOT_TOKEN

# 👇 Публичный URL вашего сервера на Railway
RAILWAY_URL = "https://твой-сервер.railway.app/webhook"

url = f"https://platform-api.max.ru/bot/{BOT_TOKEN}/set_webhook"
resp = requests.post(url, json={"url": RAILWAY_URL})
print("Webhook set:", resp.status_code, resp.text)