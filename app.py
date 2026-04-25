import requests
import json
from fastapi import FastAPI, Request

from database import init_db, SessionLocal, Training, Registration
from keyboards import main_menu, training_inline_buttons
from config import BOT_TOKEN, API_URL, GROUP_CHAT_ID, TRAINER_IDS

init_db()
db = SessionLocal()

app = FastAPI()

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


def send_message(user_id: int, text: str, keyboard=None):
    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }
    url = f"{API_URL}?user_id={user_id}"
    payload = {"text": text}
    if keyboard:
        payload["keyboard"] = json.dumps(keyboard)

    r = requests.post(url, headers=headers, json=payload)
    print("SEND:", r.status_code, r.text)
    return r.json()


def is_trainer(user_id: int) -> bool:
    return user_id in TRAINER_IDS


def get_main_list(training_id: int):
    return db.query(Registration).filter_by(
        training_id=training_id, status="main"
    ).order_by(Registration.position).all()


def get_queue_list(training_id: int):
    return db.query(Registration).filter_by(
        training_id=training_id, status="queue"
    ).order_by(Registration.position).all()


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", data)

    # --- CALLBACK от Inline-кнопок ---
    if data.get("callback_query"):
        cb = data["callback_query"]
        user_id = cb["from"]["user_id"]
        cb_data = cb["data"]

        if cb_data.startswith("join_"):
            training_id = int(cb_data.split("_")[1])
            training = db.query(Training).get(training_id)
            if not training or not training.is_active:
                send_message(user_id, "Тренировка недоступна")
                return {"ok": True}

            exist = db.query(Registration).filter_by(
                training_id=training_id, user_id=user_id
            ).first()
            if exist:
                send_message(user_id, "Вы уже записаны / в очереди")
                return {"ok": True}

            main_count = len(get_main_list(training_id))
            queue_count = len(get_queue_list(training_id))

            if main_count < training.max_slots:
                pos = main_count + 1
                reg = Registration(
                    training_id=training_id,
                    user_id=user_id,
                    status="main",
                    position=pos
                )
                db.add(reg)
                db.commit()
                send_message(user_id, f"✅ Вы записаны в основной состав! ({pos}/{training.max_slots})")
            else:
                pos = queue_count + 1
                reg = Registration(
                    training_id=training_id,
                    user_id=user_id,
                    status="queue",
                    position=pos
                )
                db.add(reg)
                db.commit()
                send_message(user_id, f"⏳ Мест нет. Вы {pos}-й в очереди.")

        elif cb_data.startswith("list_"):
            training_id = int(cb_data.split("_")[1])
            main = get_main_list(training_id)
            queue = get_queue_list(training_id)

            text = "👥 **Состав:**\n"
            if main:
                for i, r in enumerate(main, 1):
                    text += f"{i}. ID:{r.user_id}\n"
            else:
                text += "Пока никого\n"
            text += "\n⏳ **Очередь:**\n"
            if queue:
                for i, r in enumerate(queue, 1):
                    text += f"{i}. ID:{r.user_id}\n"
            else:
                text += "Пусто"

            send_message(user_id, text)

        elif cb_data.startswith("leave_"):
            training_id = int(cb_data.split("_")[1])
            reg = db.query(Registration).filter_by(
                training_id=training_id, user_id=user_id
            ).first()
            if not reg:
                send_message(user_id, "Вы не записаны")
                return {"ok": True}

            was_main = (reg.status == "main")
            db.delete(reg)
            db.commit()

            if was_main:
                first_queue = db.query(Registration).filter_by(
                    training_id=training_id, status="queue"
                ).order_by(Registration.position).first()
                if first_queue:
                    first_queue.status = "main"
                    main_count = len(get_main_list(training_id))
                    first_queue.position = main_count + 1
                    db.commit()
                    send_message(
                        first_queue.user_id,
                        "🎉 Место освободилось! Вы переведены в основной состав!"
                    )

            send_message(user_id, "❌ Вы отписаны")

        return {"ok": True}

    # --- ОБЫЧНОЕ СООБЩЕНИЕ ---
    if data.get("update_type") != "message_created":
        return {"ok": True}

    msg = data["message"]
    text = msg["body"].get("text", "")
    user_id = msg["sender"]["user_id"]

    print("TEXT:", text)

    if text == "/start":
        trainer = is_trainer(user_id)
        kb = main_menu(trainer)
        send_message(user_id, "Привет! Я бот для записи на тренировки 🏒", kb)
        return {"ok": True}

    if text == "/list":
        trainings = db.query(Training).filter_by(is_active=True).all()
        if not trainings:
            send_message(user_id, "Нет активных тренировок")
            return {"ok": True}
        result = "📋 Активные тренировки:\n"
        for t in trainings:
            main_count = len(get_main_list(t.id))
            result += f"\n{t.id}. {t.date} | {t.place} | {main_count}/{t.max_slots}"
        send_message(user_id, result)
        return {"ok": True}

    if text == "➕ Создать тренировку":
        if not is_trainer(user_id):
            send_message(user_id, "Только для тренеров")
            return {"ok": True}
        user_states[user_id] = {"step": 1}
        send_message(user_id, "Введи день и дату (пример: Пятница 24.04.2026):")
        return {"ok": True}

    if user_id in user_states:
        state = user_states[user_id]
        try:
            if state["step"] == 1:
                state["date"] = text
                state["step"] = 2
                send_message(user_id, "Время (20:45-21:45):")
            elif state["step"] == 2:
                state["time"] = text
                state["step"] = 3
                send_message(user_id, "Место (1-Олимпийский, 2-Айсберг, 3-Десант, 4-своё):")
            elif state["step"] == 3:
                places = {"1": "ЛДС Олимпийский", "2": "ЛДС Айсберг", "3": "ЛДС Десант"}
                if text in places:
                    state["place"] = places[text]
                    state["step"] = 4
                    send_message(user_id, "Направления (через запятую):\n1-Клюшка, 2-Катание, 3-Бросок, 4-ОФП")
                elif text == "4":
                    state["step"] = "custom_place"
                    send_message(user_id, "Своё место:")
                else:
                    state["place"] = text
                    state["step"] = 4
                    send_message(user_id, "Направления (через запятую):\n1-Клюшка, 2-Катание, 3-Бросок, 4-ОФП")
            elif state["step"] == "custom_place":
                state["place"] = text
                state["step"] = 4
                send_message(user_id, "Направления (через запятую):\n1-Клюшка, 2-Катание, 3-Бросок, 4-ОФП")
            elif state["step"] == 4:
                dirs = {"1": "Техника клюшки", "2": "Техника катания", "3": "Техника броска", "4": "ОФП"}
                selected = [dirs.get(x.strip(), x.strip()) for x in text.split(",")]
                state["direction"] = ", ".join(selected)
                state["step"] = 5
                send_message(user_id, "Тренеры:")
            elif state["step"] == 5:
                state["coaches"] = text
                state["step"] = 6
                send_message(user_id, "Макс. участников:")
            elif state["step"] == 6:
                state["max_slots"] = int(text)
                state["step"] = 7
                send_message(user_id, "Цена (руб):")
            elif state["step"] == 7:
                state["price"] = text
                state["step"] = 8
                send_message(user_id, "Доп. информация (возраст и т.д.):")
            elif state["step"] == 8:
                state["extra"] = text

                training = Training(
                    date=state["date"],
                    time=state["time"],
                    place=state["place"],
                    direction=state["direction"],
                    coaches=state["coaches"],
                    max_slots=state["max_slots"],
                    price=state["price"],
                    extra=state["extra"],
                    is_active=True
                )
                db.add(training)
                db.commit()

                post = (
                    "🏒 **НОВАЯ ТРЕНИРОВКА**\n"
                    f"📅 {state['date']}\n"
                    f"🕐 {state['time']}\n"
                    f"📍 {state['place']}\n"
                    f"🎯 {state['direction']}\n"
                    f"👤 Тренер: {state['coaches']}\n"
                    f"👥 Мест: {state['max_slots']}\n"
                    f"💰 {state['price']} руб.\n"
                    f"ℹ️ {state['extra']}"
                )

                kb = training_inline_buttons(training.id)
                resp = send_message(GROUP_CHAT_ID, post, kb)

                msg_id = resp.get("message", {}).get("message_id")
                if msg_id:
                    training.group_msg_id = str(msg_id)
                    db.commit()

                send_message(user_id, "✅ Тренировка создана и опубликована в чате!")
                del user_states[user_id]
        except Exception as e:
            print("FSM ERROR:", e)
            send_message(user_id, "Ошибка при создании ❌")
            del user_states[user_id]

        return {"ok": True}

    return {"ok": True}