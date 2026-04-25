import requests

TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"
API_URL = "https://platform-api.max.ru/messages"
USER_ID = 125743856  # ваш ID

headers = {
    "Authorization": TOKEN,
    "Content-Type": "application/json"
}

# Вариант 1: keyboard внутри reply_markup
payload1 = {
    "text": "Тест 1",
    "reply_markup": {
        "keyboard": [
            [{"text": "Кнопка 1"}]
        ]
    }
}

# Вариант 2: keyboard на верхнем уровне
payload2 = {
    "text": "Тест 2",
    "keyboard": {
        "keyboard": [
            [{"text": "Кнопка 2"}]
        ]
    }
}

# Вариант 3: keyboard как строка JSON
import json
payload3 = {
    "text": "Тест 3",
    "keyboard": json.dumps({
        "keyboard": [
            [{"text": "Кнопка 3"}]
        ]
    })
}

for name, payload in [("reply_markup", payload1), ("keyboard-obj", payload2), ("keyboard-str", payload3)]:
    url = f"{API_URL}?user_id={USER_ID}"
    r = requests.post(url, headers=headers, json=payload)
    print(f"{name}: {r.status_code} | {r.text[:200]}")