import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()

TOKEN = os.getenv("BOT_TOKEN")  # обязательно через env!

API_URL = "https://platform-api.max.ru/messages"


def send_message(user_id: int, text: str):
    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "user_id": user_id,   # ВАЖНО: не chat_id!
        "text": text
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    print("SEND:", response.status_code, response.text)


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", data)

    # старт бота
    if data.get("update_type") == "bot_started":
        user_id = data["user"]["user_id"]

        print("BOT_STARTED:", user_id)
        send_message(user_id, "Бот запущен 🚀")

    # сообщение
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