import os
import requests
from fastapi import FastAPI, Request

from database import SessionLocal, engine, Base
from models import Training, Booking

# создаем таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI()

TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"

API_URL = "https://platform-api.max.ru/messages"


# =========================
# ОТПРАВКА СООБЩЕНИЯ
# =========================
def send_message(chat_id: int, text: str, buttons=None):
    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if buttons:
        payload["attachments"] = [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": buttons
                }
            }
        ]

    response = requests.post(API_URL, headers=headers, json=payload)
    print("SEND:", response.status_code, response.text)


# =========================
# СОЗДАНИЕ ТРЕНИРОВКИ
# =========================
def create_training():
    db = SessionLocal()

    training = Training(
        direction="Техника катания",
        coaches="Иванов И.И.",
        place="ЛДС Олимпийский",
        datetime="Суббота 25.04",
        max_slots=2,
        price=1000
    )

    db.add(training)
    db.commit()
    db.refresh(training)

    db.close()

    return training


# =========================
# ЗАПИСЬ НА ТРЕНИРОВКУ
# =========================
def join_training(training_id, user_id, name):
    db = SessionLocal()

    training = db.query(Training).filter(Training.id == training_id).first()

    active_count = db.query(Booking).filter(
        Booking.training_id == training_id,
        Booking.status == "active"
    ).count()

    if active_count < training.max_slots:
        status = "active"
        text = "✅ Ты записан на тренировку"
    else:
        status = "queue"
        queue_position = db.query(Booking).filter(
            Booking.training_id == training_id,
            Booking.status == "queue"
        ).count() + 1

        text = f"⏳ Ты в очереди. Номер: {queue_position}"

    booking = Booking(
        training_id=training_id,
        user_id=user_id,
        name=name,
        status=status
    )

    db.add(booking)
    db.commit()
    db.close()

    return text


# =========================
# WEBHOOK
# =========================
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", data)

    # =========================
    # СТАРТ БОТА
    # =========================
    if data.get("update_type") == "bot_started":
        chat_id = data["chat_id"]

        send_message(chat_id, "Бот запущен 🚀")

    # =========================
    # СООБЩЕНИЯ
    # =========================
    if data.get("update_type") == "message_created":
        msg = data["message"]
        text = msg["body"].get("text", "")
        chat_id = msg["recipient"]["chat_id"]
        user_id = msg["sender"]["user_id"]
        name = msg["sender"]["first_name"]

        print("TEXT:", text)

        # старт
        if text == "/start":
            send_message(chat_id, "Привет! Я бот записи на хоккей 🏒")

        # создать тренировку
        elif text == "/add":
            training = create_training()

            message_text = (
                f"🏒 Тренировка\n"
                f"📅 {training.datetime}\n"
                f"📍 {training.place}\n"
                f"👥 0/{training.max_slots}\n"
                f"💰 {training.price} руб"
            )

            buttons = [
                [
                    {
                        "type": "callback",
                        "text": "Записаться",
                        "payload": f"join_{training.id}"
                    }
                ]
            ]

            send_message(chat_id, message_text, buttons)

    # =========================
    # НАЖАТИЕ КНОПОК
    # =========================
    if data.get("update_type") == "message_callback":
        callback = data["callback"]
        payload = callback["payload"]
        chat_id = callback["message"]["recipient"]["chat_id"]
        user_id = callback["sender"]["user_id"]
        name = callback["sender"]["first_name"]

        print("CALLBACK:", payload)

        if payload.startswith("join_"):
            training_id = int(payload.split("_")[1])

            result_text = join_training(training_id, user_id, name)

            send_message(chat_id, result_text)

    return {"ok": True}