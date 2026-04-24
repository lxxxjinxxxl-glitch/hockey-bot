from fastapi import FastAPI, Request
import requests

from database import Base, engine
from config import BOT_TOKEN

app = FastAPI()

Base.metadata.create_all(bind=engine)

def send_message(chat_id, text):
    url = "https://platform-api.max.ru/messages"

    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "chat_id": chat_id,
        "text": text
    }

    requests.post(url, headers=headers, json=data)

@app.get("/")
def root():
    return {"status": "ok"}

# ✅ ВОТ ЭТО ГЛАВНОЕ
@app.post ("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print("UPDATE:", data)

    if data.get("update_type") == "bot_started":
        chat_id = data.get("chat_id")
        send_message(chat_id, "Бот запущен 🚀")

    if data.get("update_type") == "message_created":
        message = data.get("message", {})
        chat_id = message.get("chat_id")
        text = message.get("text", "")

        if text == "/start":
            send_message(chat_id, "Бот работает 🚀")
        elif text:
            send_message(chat_id, f"Ты написал: {text}")

    return {"ok": True}