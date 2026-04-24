from fastapi import FastAPI, Request
import requests

from database import Base, engine
from config import BOT_TOKEN

app = FastAPI()

Base.metadata.create_all(bind=engine)


def send_message(user_id, text):
    url = "https://platform-api.max.ru/messages"

    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "recipient": {
            "user_id": user_id
        },
        "text": text
    }

    r = requests.post(url, headers=headers, json=data)
    print("SEND:", r.status_code, r.text)


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print("UPDATE:", data)

    # 🚀 запуск бота
    if data.get("update_type") == "bot_started":
        user_id = data.get("user", {}).get("user_id")

        print("BOT_STARTED user_id:", user_id)

        if user_id:
            send_message(user_id, "Бот запущен 🚀")

    # 💬 сообщение
    if data.get("update_type") == "message_created":
        message = data.get("message", {})

        user_id = message.get("sender", {}).get("user_id")
        text = message.get("body", {}).get("text", "")

        print("USER_ID:", user_id)
        print("TEXT:", text)

        if user_id and text == "/start":
            send_message(user_id, "Бот работает 🚀")

        elif user_id and text:
            send_message(user_id, f"Ты написал: {text}")

    return {"ok": True}