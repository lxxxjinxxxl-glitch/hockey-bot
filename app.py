from fastapi import FastAPI, Request
import requests
from config import BOT_TOKEN

app = FastAPI()

print("CONFIG TOKEN:", BOT_TOKEN)


# ✅ отправка сообщения (RAW API MAX)
def send_message(chat_id, text):
    url = "https://platform-api.max.ru/messages"

    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }

    data = {
        "recipient": {
            "chat_id": int(chat_id)
        },
        "message": {
            "text": text
        }
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        print("SEND:", response.status_code, response.text)
    except Exception as e:
        print("ERROR SEND:", e)


@app.get("/")
def root():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print("UPDATE:", data)

    # 🔹 пользователь открыл бота
    if data.get("update_type") == "bot_started":
        chat_id = data.get("chat_id")
        print("BOT_STARTED:", chat_id)

        send_message(chat_id, "Бот запущен 🚀")

    # 🔹 пользователь написал сообщение
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