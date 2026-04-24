from fastapi import FastAPI, Request
import requests
from config import BOT_TOKEN

app = FastAPI()


@app.get("/")
def root():
    return {"status": "ok"}


def send_message(chat_id, text):
    """Отправляет сообщение пользователю через API MAX"""
    url = f"https://max.ru/api/bots/{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    try:
        response = requests.post(url, json=payload)
        print(f"Отправка сообщения: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    print(f"Получены данные: {data}")

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text == "/start":
            send_message(chat_id, "Бот работает 👍")

    return {"ok": True}