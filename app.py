import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()

TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"

API_URL = "https://platform-api.max.ru/messages"


# ✅ ИСПРАВЛЕНО: теперь chat_id
def send_message(chat_id: int, text: str):
    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    print("SEND:", response.status_code, response.text)


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", data)

    # ✅ bot_started
    if data.get("update_type") == "bot_started":
        chat_id = data["chat_id"]   # ← ВАЖНО

        print("BOT_STARTED:", chat_id)
        send_message(chat_id, "Бот запущен 🚀")

    # ✅ message_created
    if data.get("update_type") == "message_created":
        msg = data["message"]
        text = msg["body"].get("text", "")

        # ✅ ВАЖНО: берем chat_id, а не user_id
        chat_id = msg["recipient"]["chat_id"]

        print("CHAT_ID:", chat_id)
        print("TEXT:", text)

        if text == "/start":
            send_message(chat_id, "Привет! Я работаю ✅")
        else:
            send_message(chat_id, f"Ты написал: {text}")

    return {"ok": True}