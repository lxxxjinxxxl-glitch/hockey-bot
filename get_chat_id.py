import requests

TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"

headers = {
    "Authorization": TOKEN,
    "Content-Type": "application/json"
}

# Попытка 1: список чатов
url = "https://platform-api.max.ru/chats"
resp = requests.get(url, headers=headers)
print("СТАТУС:", resp.status_code)
print("ОТВЕТ:", resp.text[:2000])  # первые 2000 символов