import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()

TOKEN = os.getenv("BOT_TOKEN")

API_URL = "https://platform-api.max.ru/messages"


# 🔥 ПРАВИЛЬНАЯ отправка по документации MAX
def send_message(chat_id: int, text: str):
    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "recipient": {
            "chat_id": chat_id
        },
        "body": {
            "text": text
        }
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    print("SEND:", response.status_code, response.text)


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", data)

    # 🔹 бот запущен
    if data.get("update_type") == "bot_started":
        chat_id = data.get("chat_id")

        print("BOT_STARTED:", chat_id)
        send_message(chat_id, "Бот запущен 🚀")

    # 🔹 сообщение
    if data.get("update_type") == "message_created":
        msg = data["message"]

        text = msg["body"].get("text", "")
        chat_id = msg["recipient"]["chat_id"]

        print("TEXT:", text)
        print("CHAT_ID:", chat_id)

        if text == "/start":
            send_message(chat_id, "Привет! Я работаю ✅")

        elif text == "/add":
            send_message(chat_id, "Создаем тренировку 🏒\nНапиши дату:")

        else:
            send_message(chat_id, f"Ты написал: {text}")

    return {"ok": True}