import requests
from fastapi import FastAPI, Request

app = FastAPI()

# ❗ ВСТАВЬ СЮДА СВОЙ ТОКЕН
TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"

API_URL = "https://platform-api.max.ru/messages"


def send_message(user_id: int, text: str):
    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json"
    }

    # user_id идет в URL
    url = f"{API_URL}?user_id={user_id}"

    payload = {
        "text": text
    }

    response = requests.post(url, headers=headers, json=payload)
    print("SEND:", response.status_code, response.text)


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", data)

    # запуск бота
    if data.get("update_type") == "bot_started":
        user_id = data["user"]["user_id"]

        print("BOT_STARTED:", user_id)
        send_message(user_id, "Бот запущен 🚀")

    # сообщения
    if data.get("update_type") == "message_created":
        msg = data["message"]

        text = msg["body"].get("text", "")
        user_id = msg["sender"]["user_id"]

        print("TEXT:", text)

        if text == "/start":
            send_message(user_id, "Привет! Я работаю ✅")
        else:
            send_message(user_id, f"Ты написал: {text}")

    return {"ok": True}