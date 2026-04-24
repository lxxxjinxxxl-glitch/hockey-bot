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

    requests.post(url, headers=headers, json={
        "chat_id": chat_id,
        "text": text
    })

@app.get("/")
def root():
    return {"status": "ok"}

"/webhook"
async def webhook(request: Request):
    data = await request.json()
    print("INCOMING:", data)

    if data.get("update_type") == "bot_started":
        chat_id = data.get("chat_id")
        send_message(chat_id, "Бот запущен 🚀")
        return {"ok": True}

    if data.get("update_type") == "message_created":
        message = data.get("message", {})
        chat_id = message.get("chat_id")
        text = message.get("text", "")

        if text:
            send_message(chat_id, f"Ты написал: {text}")

    return {"ok": True}