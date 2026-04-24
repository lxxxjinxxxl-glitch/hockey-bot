import requests
from fastapi import FastAPI, Request

from database import engine
from models import Base, Training

from sqlalchemy.orm import sessionmaker

# создаём БД
Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

app = FastAPI()

TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"
API_URL = "https://platform-api.max.ru/messages"

# FSM состояния
user_states = {}

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


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", data)

    if data.get("update_type") != "message_created":
        return {"ok": True}

    msg = data["message"]
    text = msg["body"].get("text", "")
    user_id = msg["sender"]["user_id"]

    print("TEXT:", text)

    # старт
    if text == "/start":
        send_message(user_id, "Привет! Я бот для записи на хоккей 🏒\n\n/add — создать тренировку\n/list — список тренировок")
        return {"ok": True}

    # список тренировок
    if text == "/list":
        trainings = db.query(Training).all()

        if not trainings:
            send_message(user_id, "Нет тренировок")
            return {"ok": True}

        result = ""
        for t in trainings:
            result += f"{t.id}. {t.datetime} | {t.place}\n"

        send_message(user_id, result)
        return {"ok": True}

    # старт создания
    if text == "/add":
        user_states[user_id] = {"step": 1}
        send_message(user_id, "Введи день недели и дату (пример: Пятница 24.04.2026):")
        return {"ok": True}

    # FSM
    if user_id in user_states:
        state = user_states[user_id]

        try:
            # 1 дата
            if state["step"] == 1:
                state["date"] = text
                state["step"] = 2
                send_message(user_id, "Введи время льда (пример 20:45-21:45):")
                return {"ok": True}

            # 2 время
            elif state["step"] == 2:
                state["time"] = text
                state["step"] = 3

                send_message(
                    user_id,
                    "Выбери место:\n"
                    "1. Олимпийский\n"
                    "2. Айсберг\n"
                    "3. Десант\n"
                    "4. Свой вариант"
                )
                return {"ok": True}

            # 3 место
            elif state["step"] == 3:
                if text in PLACES:
                    state["place"] = PLACES[text]
                    state["step"] = 4

                    send_message(
                        user_id,
                        "Выбери направления (через запятую):\n"
                        "1. Клюшка\n"
                        "2. Катание\n"
                        "3. Бросок\n"
                        "4. ОФП"
                    )
                    return {"ok": True}

                elif text == "4":
                    state["step"] = "custom_place"
                    send_message(user_id, "Напиши своё место:")
                    return {"ok": True}

            elif state["step"] == "custom_place":
                state["place"] = text
                state["step"] = 4

                send_message(
                    user_id,
                    "Выбери направления (через запятую):\n"
                    "1. Клюшка\n"
                    "2. Катание\n"
                    "3. Бросок\n"
                    "4. ОФП"
                )
                return {"ok": True}

            # 4 направления
            elif state["step"] == 4:
                selected = text.split(",")

                directions = []
                for i in selected:
                    i = i.strip()
                    if i in DIRECTIONS:
                        directions.append(DIRECTIONS[i])

                state["direction"] = "\n- " + "\n- ".join(directions)

                state["step"] = 5
                send_message(user_id, "Введи тренеров:")
                return {"ok": True}

            # 5 тренеры
            elif state["step"] == 5:
                state["coaches"] = text
                state["step"] = 6
                send_message(user_id, "Макс участников:")
                return {"ok": True}

            # 6 макс
            elif state["step"] == 6:
                state["max_slots"] = int(text)
                state["step"] = 7
                send_message(user_id, "Цена:")
                return {"ok": True}

            # 7 цена
            elif state["step"] == 7:
                state["price"] = text
                state["step"] = 8
                send_message(user_id, "Доп. информация (например возраст):")
                return {"ok": True}

            # 8 финал
            elif state["step"] == 8:
                state["extra"] = text

                training = Training(
                    datetime=state["date"],
                    place=state["place"],
                    direction=state["direction"],
                    coaches=state["coaches"],
                    max_slots=state["max_slots"],
                    price=state["price"]
                )

                db.add(training)
                db.commit()

                message = (
                    "Внимание ❗️\n"
                    f"▶️{state['date']}\n"
                    f"▶️Место проведения : {state['place']}\n"
                    f"▶️Лед: {state['time']}\n"
                    f"▶️Направленность:{state['direction']}\n"
                    f"▶️Тренер:\n-{state['coaches']}\n"
                    f"▶️Стоимость: {state['price']}р\n\n"
                    f"{state['max_slots']} человек!\n"
                    f"{state['extra']}"
                )

                send_message(user_id, message)

                del user_states[user_id]
                return {"ok": True}

        except Exception as e:
            print("ERROR:", e)
            send_message(user_id, "Ошибка ❌")
            del user_states[user_id]
            return {"ok": True}

    return {"ok": True}