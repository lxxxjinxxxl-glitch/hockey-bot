import requests

TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"

url = "https://platform-api.max.ru/subscriptions"

headers = {
    "Authorization": TOKEN,
    "Content-Type": "application/json"
}

data = {
    "url": "https://hockey-bot-production.up.railway.app/webhook"
}

response = requests.post(url, headers=headers, json=data)

print(response.status_code)
print(response.text)