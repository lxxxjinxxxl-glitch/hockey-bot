import requests
from fastapi import FastAPI, Request

# БАЗА
from database import SessionLocal, engine, Base
import models

# создаем таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI()

TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"
API_URL = "https://platform-api.max.ru/messages"


# ✅ РАБОЧАЯ ОТПРАВКА (НЕ ТРОГАТЬ)
def send_message(user_id: int, text: str):
    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json"
    }

    url = f"{API_URL}?user_id={user_id}"

    payload = {
        "text": text
    }

    response = requests.post(url, headers=headers, json=payload)
    print("SEND:", response.status_code, response.text)


# ==============================
# 🔥 ОСНОВНОЙ ВЕБХУК
# ==============================
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", data)

    db = SessionLocal()

    # =========================
    # 🚀 СТАРТ
    # =========================
    if data.get("update_type") == "bot_started":
        user_id = data["user"]["user_id"]

        send_message(user_id, "Бот запущен 🚀")

    # =========================
    # 💬 СООБЩЕНИЯ
    # =========================
    if data.get("update_type") == "message_created":
        msg = data["message"]

        text = msg["body"].get("text", "")
        user_id = msg["sender"]["user_id"]

        print("TEXT:", text)

        # =====================
        # /start
        # =====================
        if text == "/start":
            send_message(user_id, "Привет! Я бот для записи на хоккей 🏒")

        # =====================
        # /add — создать тренировку
        # =====================
        elif text.startswith("/add"):
            try:
                # формат:
                # /add Дата|Место|Направление|Тренеры|Макс|Цена

                parts = text.replace("/add ", "").split("|")

                training = models.Training(
                    datetime=parts[0],
                    place=parts[1],
                    direction=parts[2],
                    coaches=parts[3],
                    max_slots=int(parts[4]),
                    price=int(parts[5])
                )

                db.add(training)
                db.commit()

                send_message(user_id, "Тренировка создана ✅")

            except Exception as e:
                print("ERROR:", e)
                send_message(user_id, "Ошибка при создании тренировки ❌")

        # =====================
        # /list — список
        # =====================
        elif text == "/list":
            trainings = db.query(models.Training).all()

            if not trainings:
                send_message(user_id, "Тренировок нет")
            else:
                result = ""

                for t in trainings:
                    result += (
                        f"\nID: {t.id}\n"
                        f"{t.datetime}\n"
                        f"{t.place}\n"
                        f"{t.direction}\n"
                        f"Тренеры: {t.coaches}\n"
                        f"Мест: {t.max_slots}\n"
                        f"Цена: {t.price}₽\n"
                        f"------\n"
                    )

                send_message(user_id, result)

        # =====================
        # /join
        # =====================
        elif text.startswith("/join"):
            try:
                parts = text.split(" ")

                training_id = int(parts[1])
                name = parts[2]

                bookings = db.query(models.Booking).filter(
                    models.Booking.training_id == training_id
                ).all()

                training = db.query(models.Training).filter(
                    models.Training.id == training_id
                ).first()

                if len(bookings) < training.max_slots:
                    booking = models.Booking(
                        training_id=training_id,
                        user_id=user_id,
                        name=name
                    )

                    db.add(booking)
                    db.commit()

                    send_message(user_id, "Ты записан ✅")
                else:
                    position = len(bookings) - training.max_slots + 1
                    send_message(user_id, f"Ты в очереди. Место: {position}")

            except Exception as e:
                print("ERROR:", e)
                send_message(user_id, "Ошибка записи ❌")

        # =====================
        # любое сообщение
        # =====================
        else:
            send_message(user_id, f"Ты написал: {text}")

    db.close()
    return {"ok": True}