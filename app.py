from fastapi import FastAPI, Request
import requests
from config import BOT_TOKEN

app = FastAPI()

print("CONFIG TOKEN:", BOT_TOKEN)


# ✅ ПРАВИЛЬНАЯ ОТПРАВКА
def send_message(chat_id, text):
    url = "https://platform-api.max.ru/messages"

    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "recipient": {
            "chat_id": chat_id
        },
        "message": {
            "text": text
        }
    }

    response = requests.post(url, headers=headers, json=data)
    print("SEND:", response.status_code, response.text)


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print("UPDATE:", data)

    # 📌 бот старт
    if data.get("update_type") == "bot_started":
        chat_id = data.get("chat_id")
        print("BOT_STARTED:", chat_id)

        send_message(chat_id, "Бот запущен 🚀")

    # 📌 сообщение
    if data.get("update_type") == "message_created":
        message = data.get("message", {})

        chat_id = message.get("recipient", {}).get("chat_id")
        text = message.get("body", {}).get("text", "")

        print("CHAT_ID:", chat_id)
        print("TEXT:", text)

        if text == "/start":
            send_message(chat_id, "Бот работает 🚀")
        elif text:
            send_message(chat_id, f"Ты написал: {text}")

    return {"ok": True}