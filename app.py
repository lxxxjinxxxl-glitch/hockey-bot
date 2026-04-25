import requests
import json
from fastapi import FastAPI, Request

from database import init_db, SessionLocal, Training, Registration
from keyboards import training_inline_buttons
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


def send_message(user_id: int, text: str, inline_keyboard=None):
    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }
    url = f"{API_URL}?user_id={user_id}"
    payload = {"text": text}
    if inline_keyboard:
        payload["attachments"] = inline_keyboard["attachments"]

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
    print("UPDATE:", json.dumps(data, ensure_ascii=False, indent=2)[:500])

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
                db.add(Registration(
                    training_id=training_id, user_id=user_id,
                    status="main", position=pos
                ))
                db.commit()
                send_message(user_id, f"✅ Вы в основном составе! ({pos}/{training.max_slots})")
            else:
                pos = queue_count + 1
                db.add(Registration(
                    training_id=training_id, user_id=user_id,
                    status="queue", position=pos
                ))
                db.commit()
                send_message(user_id, f"⏳ Мест нет. Вы {pos}-й в очереди.")
            return {"ok": True}

        elif cb_data.startswith("list_"):
            training_id = int(cb_data.split("_")[1])
            main = get_main_list(training_id)
            queue = get_queue_list(training_id)

            text = "👥 Состав:\n"
            if main:
                for i, r in enumerate(main, 1):
                    text += f"{i}. ID:{r.user_id}\n"
            else:
                text += "Пока никого\n"
            text += "\n⏳ Очередь:\n"
            text += "\n".join(f"{i}. ID:{r.user_id}" for i, r in enumerate(queue, 1)) or "Пусто"
            send_message(user_id, text)
            return {"ok": True}

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
                    first_queue.position = len(get_main_list(training_id)) + 1
                    db.commit()
                    send_message(first_queue.user_id, "🎉 Место освободилось! Вы в основном составе!")

            send_message(user_id, "❌ Вы отписаны")
            return {"ok": True}

    # --- ОБЫЧНОЕ СООБЩЕНИЕ ---
    if data.get("update_type") != "message_created":
        return {"ok": True}

    msg = data["message"]
    text = msg["body"].get("text", "").strip()
    user_id = msg["sender"]["user_id"]

    print(f"TEXT: '{text}' | from: {user_id}")

    # /start
    if text == "/start":
        if is_trainer(user_id):
            send_message(user_id, "Привет, тренер! 🏒\n/add — создать тренировку\n/list — список")
        else:
            send_message(user_id, "Привет! 🏒\n/list — список тренировок")
        return {"ok": True}

    # /list
    if text == "/list":
        trainings = db.query(Training).filter_by(is_active=True).all()
        if not trainings:
            send_message(user_id, "Нет активных тренировок")
            return {"ok": True}
        result = "📋 Тренировки:\n"
        for t in trainings:
            main_count = len(get_main_list(t.id))
            result += f"\n{t.id}. {t.date} | {t.place} | {main_count}/{t.max_slots}"
        send_message(user_id, result)
        return {"ok": True}

    # /add — старт FSM
    if text == "/add":
        if not is_trainer(user_id):
            send_message(user_id, "Только для тренеров")
            return {"ok": True}
        user_states[user_id] = {"step": "date"}
        send_message(user_id, "📅 Введи дату (Пример: Пятница 24.04.2026):")
        return {"ok": True}

    # FSM
    if user_id in user_states:
        state = user_states[user_id]
        step = state["step"]
        print(f"FSM step={step}, text='{text}'")

        try:
            # Шаг: дата
            if step == "date":
                state["date"] = text
                state["step"] = "time_start"
                send_message(user_id, "🕐 Введи время НАЧАЛА (Пример: 20:45):")

            # Шаг: время начала
            elif step == "time_start":
                if ":" not in text:
                    send_message(user_id, "❌ Неверный формат. Введи время как 20:45:")
                    return {"ok": True}
                state["time_start"] = text
                state["step"] = "time_end"
                send_message(user_id, "🕐 Введи время КОНЦА (Пример: 21:45):")

            # Шаг: время конца
            elif step == "time_end":
                if ":" not in text:
                    send_message(user_id, "❌ Неверный формат. Введи время как 21:45:")
                    return {"ok": True}
                state["time_end"] = text
                state["step"] = "place"
                send_message(user_id, "📍 Место:\n1 — Олимпийский\n2 — Айсберг\n3 — Десант\n4 — Свой вариант")

            # Шаг: место
            elif step == "place":
                if text in PLACES:
                    state["place"] = PLACES[text]
                    state["step"] = "direction"
                    send_message(user_id, "🎯 Направления (через запятую):\n1-Клюшка, 2-Катание, 3-Бросок, 4-ОФП")
                elif text == "4":
                    state["step"] = "place_custom"
                    send_message(user_id, "📍 Напиши своё место:")
                else:
                    send_message(user_id, "❌ Выбери 1, 2, 3 или 4:")
                return {"ok": True}

            elif step == "place_custom":
                state["place"] = text
                state["step"] = "direction"
                send_message(user_id, "🎯 Направления (через запятую):\n1-Клюшка, 2-Катание, 3-Бросок, 4-ОФП")

            # Шаг: направления
            elif step == "direction":
                dirs = {"1": "Техника клюшки", "2": "Техника катания", "3": "Техника броска", "4": "ОФП"}
                selected = [dirs.get(x.strip(), x.strip()) for x in text.split(",") if x.strip()]
                if not selected:
                    send_message(user_id, "❌ Выбери хотя бы одно направление (1,2,3,4 через запятую):")
                    return {"ok": True}
                state["direction"] = ", ".join(selected)
                state["step"] = "coaches"
                send_message(user_id, "👤 Тренер(ы):")

            # Шаг: тренеры
            elif step == "coaches":
                state["coaches"] = text
                state["step"] = "max_slots"
                send_message(user_id, "👥 Макс. количество участников:")

            # Шаг: максимум участников
            elif step == "max_slots":
                if not text.isdigit() or int(text) < 1:
                    send_message(user_id, "❌ Введи число (например: 25):")
                    return {"ok": True}
                state["max_slots"] = int(text)
                state["step"] = "price"
                send_message(user_id, "💰 Цена (руб):")

            # Шаг: цена
            elif step == "price":
                state["price"] = text
                state["step"] = "extra"
                send_message(user_id, "ℹ️ Доп. информация (возраст и т.д.) или напиши «—» если нет:")

            # Шаг: доп.информация (НЕОБЯЗАТЕЛЬНО)
            elif step == "extra":
                state["extra"] = "" if text in ("-", "—", "нет", "пропустить") else text

                # Сохраняем в БД
                training = Training(
                    date=state["date"],
                    time=f"{state['time_start']}-{state['time_end']}",
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

                # Текст поста
                post = (
                    f"🏒 **НОВАЯ ТРЕНИРОВКА**\n"
                    f"📅 {state['date']}\n"
                    f"🕐 {state['time_start']} — {state['time_end']}\n"
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
            print(f"FSM ERROR: {type(e).__name__}: {e}")
            send_message(user_id, f"❌ Ошибка: {e}")
            if user_id in user_states:
                del user_states[user_id]

        return {"ok": True}

    return {"ok": True}