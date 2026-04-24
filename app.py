import requests
from fastapi import FastAPI, Request

from database import SessionLocal, engine, Base
from models import Training, Booking

app = FastAPI()

# создаем таблицы
Base.metadata.create_all(bind=engine)

TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"
API_URL = "https://platform-api.max.ru/messages"

# 👇 состояние пользователей (FSM)
user_states = {}

# 👇 список админов (тренеров)
ADMINS = [125743856]  # ← вставь свой user_id


# =========================
# ОТПРАВКА СООБЩЕНИЯ (НЕ ТРОГАЕМ!)
# =========================
def send_message(user_id: int, text: str):
    headers = {
        "Authorization": TOKEN,
        "Content-Type": "application/json"
    }

    url = f"{API_URL}?user_id={user_id}"

    payload = {"text": text}

    r = requests.post(url, headers=headers, json=payload)
    print("SEND:", r.status_code, r.text)


# =========================
# WEBHOOK
# =========================
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", data)

    if data.get("update_type") != "message_created":
        return {"ok": True}

    msg = data["message"]
    user_id = msg["sender"]["user_id"]
    text = msg["body"].get("text", "")

    db = SessionLocal()

    # =========================
    # СТАРТ
    # =========================
    if text == "/start":
        send_message(user_id, "Бот для записи на хоккей 🏒")

        if user_id in ADMINS:
            send_message(user_id, "Ты тренер. Команда: /add")

        return {"ok": True}

    # =========================
    # СОЗДАНИЕ ТРЕНИРОВКИ (ШАГ 1)
    # =========================
    if text == "/add" and user_id in ADMINS:
        user_states[user_id] = {"step": 1}
        send_message(user_id, "Введи дату и время:")
        return {"ok": True}

    # =========================
    # FSM (ПОШАГОВО)
    # =========================
    if user_id in user_states:
        state = user_states[user_id]

        try:
            if state["step"] == 1:
                state["datetime"] = text
                state["step"] = 2
                send_message(user_id, "Место:")
                return {"ok": True}

            elif state["step"] == 2:
                state["place"] = text
                state["step"] = 3
                send_message(user_id, "Направление:")
                return {"ok": True}

            elif state["step"] == 3:
                state["direction"] = text
                state["step"] = 4
                send_message(user_id, "Тренеры:")
                return {"ok": True}

            elif state["step"] == 4:
                state["coaches"] = text
                state["step"] = 5
                send_message(user_id, "Макс участников:")
                return {"ok": True}

            elif state["step"] == 5:
                state["max_slots"] = int(text)
                state["step"] = 6
                send_message(user_id, "Цена:")
                return {"ok": True}

            elif state["step"] == 6:
                state["price"] = int(text)

                training = Training(
                    datetime=state["datetime"],
                    place=state["place"],
                    direction=state["direction"],
                    coaches=state["coaches"],
                    max_slots=state["max_slots"],
                    price=state["price"]
                )

                db.add(training)
                db.commit()

                send_message(user_id, "Тренировка создана ✅")

                del user_states[user_id]
                return {"ok": True}

        except Exception as e:
            print("ERROR:", e)
            send_message(user_id, "Ошибка ❌")
            del user_states[user_id]
            return {"ok": True}

    # =========================
    # ЗАПИСЬ
    # =========================
    if text.startswith("/join"):
        parts = text.split()

        if len(parts) < 2:
            send_message(user_id, "Формат: /join Иванов")
            return {"ok": True}

        name = parts[1]

        training = db.query(Training).order_by(Training.id.desc()).first()

        if not training:
            send_message(user_id, "Нет тренировок")
            return {"ok": True}

        active = db.query(Booking).filter_by(
            training_id=training.id,
            status="active"
        ).count()

        if active < training.max_slots:
            status = "active"
            send_message(user_id, "Ты записан ✅")
        else:
            status = "waiting"
            queue_pos = db.query(Booking).filter_by(
                training_id=training.id,
                status="waiting"
            ).count() + 1

            send_message(user_id, f"Ты в очереди №{queue_pos}")

        booking = Booking(
            training_id=training.id,
            user_id=user_id,
            name=name,
            status=status
        )

        db.add(booking)
        db.commit()

        return {"ok": True}

    # =========================
    # ОТКАЗ
    # =========================
    if text == "/leave":
        training = db.query(Training).order_by(Training.id.desc()).first()

        booking = db.query(Booking).filter_by(
            training_id=training.id,
            user_id=user_id
        ).first()

        if not booking:
            send_message(user_id, "Ты не записан")
            return {"ok": True}

        db.delete(booking)
        db.commit()

        send_message(user_id, "Ты отказался ❌")

        # берем первого из очереди
        waiting = db.query(Booking).filter_by(
            training_id=training.id,
            status="waiting"
        ).first()

        if waiting:
            waiting.status = "active"
            db.commit()

            send_message(waiting.user_id, "Ты попал в основной состав ✅")

        return {"ok": True}

    return {"ok": True}