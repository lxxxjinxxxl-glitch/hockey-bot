import requests
from fastapi import FastAPI, Request

from database import SessionLocal, engine, Base
from models import Training, Booking

app = FastAPI()

# создаем таблицы
Base.metadata.create_all(bind=engine)

# ❗ ТВОЙ ТОКЕН
TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"

API_URL = "https://platform-api.max.ru/messages"

# состояния пользователей (FSM)
user_states = {}

# админы (тренеры)
ADMINS = [125743856]  # ← твой user_id

# варианты
PLACES = {
    "1": "ЛДС Олимпийский",
    "2": "ЛДС Айсберг",
    "3": "ЛДС Десант"
}

DIRECTIONS = {
    "1": "Техника владения клюшкой",
    "2": "Техника катания",
    "3": "Техника броска",
    "4": "ОФП"
}


# =========================
# ОТПРАВКА СООБЩЕНИЯ
# =========================
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

    print("TEXT:", text)

    db = SessionLocal()

    # =========================
    # /start
    # =========================
    if text.lower() == "/start":
        send_message(user_id, "Бот для записи на хоккей 🏒")

        if user_id in ADMINS:
            send_message(user_id, "Ты тренер.\nКоманда: /add")

        return {"ok": True}

    # =========================
    # СОЗДАНИЕ ТРЕНИРОВКИ
    # =========================
    if text == "/add" and user_id in ADMINS:
        user_states[user_id] = {"step": 1}
        send_message(user_id, "Введи дату и время:")
        return {"ok": True}

    # =========================
    # FSM (ШАГИ)
    # =========================
    if user_id in user_states:
        state = user_states[user_id]

        try:
            # ШАГ 1 — дата
            if state["step"] == 1:
                state["datetime"] = text
                state["step"] = 2

                send_message(
                    user_id,
                    "Выбери место:\n"
                    "1. Олимпийский\n"
                    "2. Айсберг\n"
                    "3. Десант\n"
                    "4. Свой вариант"
                )
                return {"ok": True}

            # ШАГ 2 — место
            elif state["step"] == 2:
                if text in PLACES:
                    state["place"] = PLACES[text]
                    state["step"] = 3

                    send_message(
                        user_id,
                        "Выбери направление:\n"
                        "1. Клюшка\n"
                        "2. Катание\n"
                        "3. Бросок\n"
                        "4. ОФП\n"
                        "5. Свой вариант"
                    )
                    return {"ok": True}

                elif text == "4":
                    state["step"] = "custom_place"
                    send_message(user_id, "Напиши свое место:")
                    return {"ok": True}

                else:
                    send_message(user_id, "Выбери цифру 1-4")
                    return {"ok": True}

            # свое место
            elif state["step"] == "custom_place":
                state["place"] = text
                state["step"] = 3

                send_message(
                    user_id,
                    "Выбери направление:\n"
                    "1. Клюшка\n"
                    "2. Катание\n"
                    "3. Бросок\n"
                    "4. ОФП\n"
                    "5. Свой вариант"
                )
                return {"ok": True}

            # направление
            elif state["step"] == 3:
                if text in DIRECTIONS:
                    state["direction"] = DIRECTIONS[text]
                    state["step"] = 4
                    send_message(user_id, "Тренеры (через запятую):")
                    return {"ok": True}

                elif text == "5":
                    state["step"] = "custom_direction"
                    send_message(user_id, "Напиши направление:")
                    return {"ok": True}

                else:
                    send_message(user_id, "Выбери цифру 1-5")
                    return {"ok": True}

            # свое направление
            elif state["step"] == "custom_direction":
                state["direction"] = text
                state["step"] = 4
                send_message(user_id, "Тренеры:")
                return {"ok": True}

            # тренеры
            elif state["step"] == 4:
                state["coaches"] = text
                state["step"] = 5
                send_message(user_id, "Макс участников:")
                return {"ok": True}

            # макс слоты
            elif state["step"] == 5:
                state["max_slots"] = int(text)
                state["step"] = 6
                send_message(user_id, "Цена:")
                return {"ok": True}

            # финал
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

                send_message(
                    user_id,
                    f"Тренировка создана ✅\n\n"
                    f"{state['datetime']}\n"
                    f"{state['place']}\n"
                    f"{state['direction']}\n"
                    f"{state['coaches']}\n"
                    f"{state['price']} руб"
                )

                del user_states[user_id]
                return {"ok": True}

        except Exception as e:
            print("ERROR:", e)
            send_message(user_id, "Ошибка при создании ❌")
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

        waiting = db.query(Booking).filter_by(
            training_id=training.id,
            status="waiting"
        ).first()

        if waiting:
            waiting.status = "active"
            db.commit()

            send_message(waiting.user_id, "Ты попал в состав ✅")

        return {"ok": True}

    return {"ok": True}