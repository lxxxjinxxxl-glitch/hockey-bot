import requests
from config import BOT_TOKEN

url = "https://platform-api.max.ru/subscriptions"

headers = {
    "Authorization": BOT_TOKEN,
    "Content-Type": "application/json"
}

data = {
    "url": "https://hockey-bot-production.up.railway.app/webhook"
}

response = requests.post(url, headers=headers, json=data)

print(response.status_code)
print(response.text)