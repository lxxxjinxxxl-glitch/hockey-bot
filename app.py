from fastapi import FastAPI, Request
import requests

from database import Base, engine
from config import BOT_TOKEN

app = FastAPI()

# создаём таблицы (пока просто база)
Base.metadata.create_all(bind=engine)

# 🔹 отправка сообщения в MAX
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

# 🔹 проверка что сервер жив
@app.get("/")
def root():
    return {"status": "ok"}

# 🔹 основной webhook
"/webhook"
async def webhook(request: Request):
    data = await request.json()
    print("INCOMING:", data)

    # ✅ 1. запуск бота (самое важное для MAX)
    if data.get("update_type") == "bot_started":
        chat_id = data.get("chat_id")
        send_message(chat_id, "Бот запущен 🚀")
        return {"ok": True}

    # ✅ 2. сообщение пользователя
    if data.get("update_type") == "message_created":
        message = data.get("message", {})
        chat_id = message.get("chat_id")
        text = message.get("text", "")

        # защита от пустых сообщений
        if not text:
            return {"ok": True}

        # команды
        if text == "/start":
            send_message(chat_id, "Бот работает 🚀")

        elif text == "/help":
            send_message(chat_id, "Доступные команды:\n/start\n/help")

        # любое другое сообщение
        else:
            send_message(chat_id, f"Ты написал: {text}")

    return {"ok": True}