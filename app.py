from fastapi import FastAPI, Request
import requests

from database import Base, engine
from config import BOT_TOKEN

app = FastAPI()

Base.metadata.create_all(bind=engine)

def send_message(chat_id, text):
    url = "https://api.max.ru/sendMessage"

    requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "token": BOT_TOKEN
    })

@app.get("/")
def root():
    return {"status": "ok"}

"/webhook"  # ← ВОТ ЭТО ВАЖНО
async def webhook(request: Request):
    data = await request.json()
    print(data)

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            send_message(chat_id, "Бот работает на сервере 🚀")

    return {"ok": True}