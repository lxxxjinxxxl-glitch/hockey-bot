# app.py
import requests
import json
import re
import time
import threading
from fastapi import FastAPI, Request

from database import init_db, SessionLocal, Training, Registration
from keyboards import training_inline_buttons, trainer_training_buttons
from config import BOT_TOKEN, API_URL, GROUP_CHAT_ID, TRAINER_IDS

init_db()
db = SessionLocal()

app = FastAPI()

user_states = {}
edit_states = {}
edit_time_start = {}

# Автозапись
AUTO_JOIN_USER_ID = 125743856
AUTO_JOIN_LAST_NAME = "Щекетов"
AUTO_JOIN_DISPLAY = "Jin"

PLACES = {
    "1": "ЛДС Олимпийский",
    "2": "ЛДС Айсберг",
    "3": "ЛДС Десант"
}

DIRECTIONS = {
    "1": "Техника владения клюшкой",
    "2": "Техника катания",
    "3": "Техника броска",
    "4": "ОФП",
    "5": "Скоростно-силовая подготовка"
}


def send_message(target_id: int, text: str, inline_keyboard=None, reply_keyboard=None):
    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }
    if target_id < 0:
        url = f"{API_URL}?chat_id={target_id}"
    else:
        url = f"{API_URL}?user_id={target_id}"

    payload = {"text": text}
    if inline_keyboard:
        payload["attachments"] = inline_keyboard["attachments"]
    if reply_keyboard:
        payload["keyboard"] = reply_keyboard

    r = requests.post(url, headers=headers, json=payload)
    print(f"SEND to {target_id}: {r.status_code}")
    try:
        return r.json()
    except:
        print("SEND RAW:", r.text[:300])
        return {"ok": False}


def edit_message(message_id: str, text: str, inline_keyboard=None):
    headers = {
        "Authorization": BOT_TOKEN,
        "Content-Type": "application/json"
    }
    url = f"https://platform-api.max.ru/messages?message_id={message_id}"
    payload = {"text": text}
    if inline_keyboard:
        payload["attachments"] = inline_keyboard["attachments"]

    r = requests.put(url, headers=headers, json=payload)
    print(f"EDIT {message_id}: {r.status_code}")
    try:
        return r.json()
    except:
        return {"ok": False}


def delete_message(message_id: str):
    headers = {"Authorization": BOT_TOKEN}
    url = f"https://platform-api.max.ru/messages?message_id={message_id}"
    r = requests.delete(url, headers=headers)
    print(f"DELETE {message_id}: {r.status_code}")
    return r.status_code


def try_send_to_user(user_id: int, text: str) -> bool:
    resp = send_message(user_id, text)
    if isinstance(resp, dict) and resp.get("message"):
        return True
    return False


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


def reg_display(r) -> str:
    if r.last_name:
        return f"{r.last_name} (ID:{r.user_id})"
    return f"ID:{r.user_id}"


def build_training_post(training) -> str:
    main = get_main_list(training.id)
    queue = get_queue_list(training.id)

    post = (
        f"🏒 НОВАЯ ТРЕНИРОВКА\n"
        f"📅 {training.date}\n"
        f"🕐 {training.time}\n"
        f"📍 {training.place}\n"
        f"🎯 {training.direction}\n"
        f"👥 Тренерский состав: {training.coaches}\n"
        f"👥 Мест: {training.max_slots}\n"
        f"💰 {training.price} руб."
    )
    if training.extra and training.extra.lower() not in ("нет", "-", "—", "пропустить"):
        post += f"\nℹ️ {training.extra}"

    post += f"\n\n👥 Состав ({len(main)}/{training.max_slots}):"
    if main:
        for i, r in enumerate(main, 1):
            post += f"\n{i}. {reg_display(r)}"
    else:
        post += "\nПока никого"

    if queue:
        post += "\n\n⏳ Очередь:"
        for i, r in enumerate(queue, 1):
            post += f"\n{i}. {reg_display(r)}"

    return post


def update_training_post(training):
    if training.group_msg_id:
        post = build_training_post(training)
        kb = training_inline_buttons(training.id)
        edit_message(training.group_msg_id, post, kb)


def move_queue_to_main(training_id: int, slots: int):
    moved = 0
    for _ in range(slots):
        first_queue = db.query(Registration).filter_by(
            training_id=training_id, status="queue"
        ).order_by(Registration.position).first()
        if first_queue:
            first_queue.status = "main"
            first_queue.position = len(get_main_list(training_id)) + 1
            db.commit()
            try_send_to_user(first_queue.user_id, "🎉 Место освободилось! Вы в основном составе!")
            moved += 1
        else:
            break
    return moved


def get_trainer_keyboard():
    return json.dumps({
        "keyboard": [
            [{"text": "➕ Создать тренировку"}],
            [{"text": "📋 Список тренировок"}]
        ],
        "resize_keyboard": True
    })


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", json.dumps(data, ensure_ascii=False, indent=2)[:500])

    # --- MESSAGE_CALLBACK ---
    if data.get("update_type") == "message_callback" or data.get("callback"):
        cb = data.get("callback") or data
        user_id = cb.get("user", {}).get("user_id") or cb.get("from", {}).get("user_id") or ""
        user_first = cb.get("user", {}).get("first_name", "")
        user_display_name = user_first or f"ID:{user_id}"
        cb_data = cb.get("payload") or cb.get("data") or ""

        print(f"CALLBACK: user={user_id} ({user_display_name}), payload={cb_data}")

        if not user_id:
            return {"ok": True}

        # ----- ЗАПИСАТЬСЯ -----
        if cb_data.startswith("join_"):
            training_id = int(cb_data.split("_")[1])
            training = db.query(Training).get(training_id)

            if not training or not training.is_active:
                return {"ok": True}

            exist = db.query(Registration).filter_by(
                training_id=training_id, user_id=user_id
            ).first()
            if exist:
                try_send_to_user(user_id, "Вы уже записаны / в очереди")
                return {"ok": True}

            resp = send_message(GROUP_CHAT_ID, f"@{user_display_name}, введите вашу ФАМИЛИЮ для записи:")
            ask_msg_id = None
            if isinstance(resp, dict) and resp.get("message"):
                ask_msg_id = resp["message"]["body"]["mid"]

            user_states[user_id] = {
                "step": "ask_lastname_in_chat",
                "training_id": training_id,
                "display_name": user_display_name,
                "ask_msg_id": ask_msg_id
            }
            return {"ok": True}

        # ----- ОТКАЗАТЬСЯ -----
        elif cb_data.startswith("leave_"):
            training_id = int(cb_data.split("_")[1])
            training = db.query(Training).get(training_id)
            reg = db.query(Registration).filter_by(
                training_id=training_id, user_id=user_id
            ).first()

            if not reg:
                try_send_to_user(user_id, "Вы не записаны")
                return {"ok": True}

            was_main = (reg.status == "main")
            disp = reg_display(reg)
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
                    try_send_to_user(first_queue.user_id, "🎉 Место освободилось! Вы в основном составе!")
                    send_message(GROUP_CHAT_ID,
                        f"❌ {disp} отказался от участия.\n"
                        f"🎉 {reg_display(first_queue)} переведён из очереди в основной состав!"
                    )
                else:
                    send_message(GROUP_CHAT_ID, f"❌ {disp} отказался от участия.")
            else:
                send_message(GROUP_CHAT_ID, f"❌ {disp} покинул очередь.")

            try_send_to_user(user_id, "❌ Вы отписаны")
            if training:
                update_training_post(training)
            return {"ok": True}

        # ----- УДАЛИТЬ -----
        elif cb_data.startswith("delete_"):
            training_id = int(cb_data.split("_")[1])
            if not is_trainer(user_id):
                return {"ok": True}
            training = db.query(Training).get(training_id)
            if training:
                training.is_active = False
                db.commit()
                for r in db.query(Registration).filter_by(training_id=training_id).all():
                    try_send_to_user(r.user_id, f"❌ Тренировка {training.date} отменена")
                try_send_to_user(user_id, "✅ Тренировка удалена")
                send_message(GROUP_CHAT_ID, f"❌ Тренировка #{training_id} отменена")
            return {"ok": True}

        # ----- ИЗМЕНИТЬ -----
        elif cb_data.startswith("edit_"):
            training_id = int(cb_data.split("_")[1])
            if not is_trainer(user_id):
                return {"ok": True}
            edit_states[user_id] = {"training_id": training_id, "step": "choose_field"}
            try_send_to_user(user_id,
                "Что меняем?\n"
                "1 — Дата\n"
                "2 — Время\n"
                "3 — Место\n"
                "4 — Направления\n"
                "5 — Тренеры\n"
                "6 — Места\n"
                "7 — Цена\n"
                "8 — Доп.инфо"
            )
            return {"ok": True}

        # ----- СОСТАВ -----
        elif cb_data.startswith("list_"):
            training_id = int(cb_data.split("_")[1])
            training = db.query(Training).get(training_id)
            if training:
                post = build_training_post(training)
                try_send_to_user(user_id, post)
            return {"ok": True}

        return {"ok": True}

    # --- ОБЫЧНОЕ СООБЩЕНИЕ ---
    if data.get("update_type") != "message_created":
        return {"ok": True}

    msg = data["message"]
    text = msg["body"].get("text", "").strip()
    user_id = msg["sender"]["user_id"]
    msg_id = msg["body"].get("mid", "")

    print(f"TEXT: '{text}' | from: {user_id}")

    if text.startswith("/"):
        user_states.pop(user_id, None)
        edit_states.pop(user_id, None)
        edit_time_start.pop(user_id, None)

    # ----- FSM: фамилия в чате -----
    if user_id in user_states and user_states[user_id].get("step") == "ask_lastname_in_chat":
        state = user_states[user_id]
        last_name = text.strip()
        training_id = state["training_id"]
        training = db.query(Training).get(training_id)
        display_name = state.get("display_name", f"ID:{user_id}")

        if msg_id:
            delete_message(msg_id)
        ask_msg_id = state.get("ask_msg_id")
        if ask_msg_id:
            delete_message(ask_msg_id)

        if not training or not training.is_active:
            try_send_to_user(user_id, "Тренировка недоступна")
            del user_states[user_id]
            return {"ok": True}

        main_count = len(get_main_list(training_id))
        queue_count = len(get_queue_list(training_id))

        if main_count < training.max_slots:
            pos = main_count + 1
            db.add(Registration(
                training_id=training_id, user_id=user_id,
                last_name=last_name, status="main", position=pos
            ))
            db.commit()
            msg_text = f"✅ {last_name}, вы в основном составе! (#{pos}/{training.max_slots})"
            chat_msg = f"✅ {display_name} ({last_name}) записан в основной состав (#{pos}/{training.max_slots})"
        else:
            pos = queue_count + 1
            db.add(Registration(
                training_id=training_id, user_id=user_id,
                last_name=last_name, status="queue", position=pos
            ))
            db.commit()
            msg_text = f"⏳ {last_name}, мест нет. Вы {pos}-й в очереди."
            chat_msg = f"⏳ {display_name} ({last_name}) добавлен в очередь (#{pos})"

        try_send_to_user(user_id, msg_text)
        send_message(GROUP_CHAT_ID, chat_msg)
        if training:
            update_training_post(training)
        del user_states[user_id]
        return {"ok": True}

    # ----- /start -----
    if text == "/start":
        if is_trainer(user_id):
            send_message(user_id,
                "Привет, тренер! 🏒\n"
                "/list — список\n/edit <ID> — изменить\n/delete <ID> — удалить",
                reply_keyboard=get_trainer_keyboard()
            )
        else:
            send_message(user_id, "Привет! 🏒\n/list — список тренировок")
        return {"ok": True}

    # ----- Кнопка «Создать тренировку» -----
    if text == "➕ Создать тренировку":
        if not is_trainer(user_id):
            send_message(user_id, "Только для тренеров")
            return {"ok": True}
        user_states[user_id] = {"step": "date"}
        send_message(user_id, "📅 Введи дату (24.04.2026):")
        return {"ok": True}

    # ----- Кнопка «Список тренировок» -----
    if text == "📋 Список тренировок":
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

    # ----- /list -----
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

    # ----- /add -----
    if text == "/add":
        if not is_trainer(user_id):
            send_message(user_id, "Только для тренеров")
            return {"ok": True}
        user_states[user_id] = {"step": "date"}
        send_message(user_id, "📅 Введи дату (24.04.2026):")
        return {"ok": True}

    # ----- /edit -----
    if text.startswith("/edit "):
        if not is_trainer(user_id):
            send_message(user_id, "Только для тренеров")
            return {"ok": True}
        try:
            training_id = int(text.split()[1])
        except:
            send_message(user_id, "Формат: /edit <ID>")
            return {"ok": True}
        training = db.query(Training).get(training_id)
        if not training:
            send_message(user_id, "Тренировка не найдена")
            return {"ok": True}
        edit_states[user_id] = {"training_id": training_id, "step": "choose_field"}
        send_message(user_id,
            "Что меняем?\n"
            "1 — Дата\n"
            "2 — Время\n"
            "3 — Место\n"
            "4 — Направления\n"
            "5 — Тренеры\n"
            "6 — Места\n"
            "7 — Цена\n"
            "8 — Доп.инфо"
        )
        return {"ok": True}

    # ----- /delete -----
    if text.startswith("/delete "):
        if not is_trainer(user_id):
            send_message(user_id, "Только для тренеров")
            return {"ok": True}
        try:
            training_id = int(text.split()[1])
        except:
            send_message(user_id, "Формат: /delete <ID>")
            return {"ok": True}
        training = db.query(Training).get(training_id)
        if training:
            training.is_active = False
            db.commit()
            for r in db.query(Registration).filter_by(training_id=training_id).all():
                try_send_to_user(r.user_id, f"❌ Тренировка {training.date} отменена")
            send_message(user_id, "✅ Тренировка удалена")
            send_message(GROUP_CHAT_ID, f"❌ Тренировка #{training_id} отменена")
        else:
            send_message(user_id, "Не найдена")
        return {"ok": True}

    # ----- FSM: редактирование -----
    if user_id in edit_states:
        state = edit_states[user_id]
        step = state["step"]
        training = db.query(Training).get(state["training_id"])

        if step == "choose_field":
            field_map = {"1": "date", "2": "time", "3": "place", "4": "direction",
                         "5": "coaches", "6": "max_slots", "7": "price", "8": "extra"}
            if text in field_map:
                state["field"] = field_map[text]
                if text == "2":
                    state["step"] = "edit_time_start"
                    send_message(user_id, "🕐 Новое время НАЧАЛА (20:45):")
                else:
                    prompts = {
                        "date": "📅 Новая дата:",
                        "place": "📍 Новое место:\n1 — Олимпийский\n2 — Айсберг\n3 — Десант\n4 — Своё",
                        "direction": "🎯 Новые направления (через запятую):\n"
                                     "1 — Клюшка\n2 — Катание\n3 — Бросок\n4 — ОФП\n5 — Скор-силовая\nИли свой текст",
                        "coaches": "👤 Новые тренеры:",
                        "max_slots": "👥 Новое макс. количество:",
                        "price": "💰 Новая цена:",
                        "extra": "ℹ️ Новая доп.информация:"
                    }
                    state["step"] = "edit_value"
                    send_message(user_id, prompts[state["field"]])
            else:
                send_message(user_id, "Выбери 1-8")
            return {"ok": True}

        elif step == "edit_time_start":
            if ":" not in text:
                send_message(user_id, "❌ Формат: 20:45")
                return {"ok": True}
            edit_time_start[user_id] = text
            state["step"] = "edit_time_end"
            send_message(user_id, "🕐 Новое время КОНЦА (21:45):")
            return {"ok": True}

        elif step == "edit_time_end":
            if ":" not in text:
                send_message(user_id, "❌ Формат: 21:45")
                return {"ok": True}
            start = edit_time_start.pop(user_id, "")
            training.time = f"{start}-{text}"
            db.commit()
            update_training_post(training)
            send_message(user_id, f"✅ Время обновлено: {training.time}")
            del edit_states[user_id]
            return {"ok": True}

        elif step == "edit_value":
            field = state["field"]
            if field == "place":
                places = {"1": "ЛДС Олимпийский", "2": "ЛДС Айсберг", "3": "ЛДС Десант"}
                training.place = places.get(text, text)
            elif field == "direction":
                parts = [x.strip() for x in text.split(",") if x.strip()]
                training.direction = ", ".join([DIRECTIONS.get(p, p) for p in parts])
            elif field == "max_slots":
                if not text.isdigit() or int(text) < 1:
                    send_message(user_id, "❌ Введи число > 0")
                    return {"ok": True}
                old_slots = training.max_slots
                training.max_slots = int(text)
                if training.max_slots > old_slots:
                    moved = move_queue_to_main(training.id, training.max_slots - old_slots)
                    if moved:
                        send_message(user_id, f"🎉 {moved} чел. переведены из очереди в состав!")
            else:
                setattr(training, field, text)
            db.commit()
            update_training_post(training)
            send_message(user_id, f"✅ Поле '{field}' обновлено!")
            del edit_states[user_id]
            return {"ok": True}

    # ----- FSM: создание тренировки -----
    if user_id in user_states:
        state = user_states[user_id]
        step = state.get("step", "")
        if step in ("ask_lastname_in_chat",):
            return {"ok": True}

        if not is_trainer(user_id):
            del user_states[user_id]
            send_message(user_id, "Только для тренеров")
            return {"ok": True}

        print(f"FSM step={step}, text='{text}'")

        try:
            if step == "date":
                if not re.search(r'\d{2}\.\d{2}\.\d{4}', text) and not re.search(r'\d{2}\.\d{2}', text):
                    send_message(user_id, "❌ Неверный формат. Пример: 24.04.2026")
                    return {"ok": True}
                state["date"] = text
                state["step"] = "time_start"
                send_message(user_id, "🕐 Введи время НАЧАЛА (20:45):")

            elif step == "time_start":
                if ":" not in text:
                    send_message(user_id, "❌ Формат: 20:45")
                    return {"ok": True}
                state["time_start"] = text
                state["step"] = "time_end"
                send_message(user_id, "🕐 Введи время КОНЦА (21:45):")

            elif step == "time_end":
                if ":" not in text:
                    send_message(user_id, "❌ Формат: 21:45")
                    return {"ok": True}
                state["time_end"] = text
                state["step"] = "place"
                send_message(user_id,
                    "📍 Место:\n"
                    "1 — Олимпийский\n"
                    "2 — Айсберг\n"
                    "3 — Десант\n"
                    "4 — Свой вариант"
                )

            elif step == "place":
                if text in PLACES:
                    state["place"] = PLACES[text]
                    state["step"] = "direction"
                    send_message(user_id,
                        "🎯 Направления (через запятую):\n"
                        "1 — Клюшка\n"
                        "2 — Катание\n"
                        "3 — Бросок\n"
                        "4 — ОФП\n"
                        "5 — Скор-силовая\n"
                        "Или свой текст"
                    )
                elif text == "4":
                    state["step"] = "place_custom"
                    send_message(user_id, "📍 Своё место:")
                else:
                    send_message(user_id, "❌ Выбери 1-4")
                return {"ok": True}

            elif step == "place_custom":
                state["place"] = text
                state["step"] = "direction"
                send_message(user_id,
                    "🎯 Направления (через запятую):\n"
                    "1 — Клюшка\n"
                    "2 — Катание\n"
                    "3 — Бросок\n"
                    "4 — ОФП\n"
                    "5 — Скор-силовая\n"
                    "Или свой текст"
                )

            elif step == "direction":
                parts = [x.strip() for x in text.split(",") if x.strip()]
                selected = [DIRECTIONS.get(p, p) for p in parts]
                if not selected:
                    send_message(user_id, "❌ Выбери хотя бы одно")
                    return {"ok": True}
                state["direction"] = ", ".join(selected)
                state["step"] = "coaches"
                send_message(user_id, "👤 Тренер(ы):")

            elif step == "coaches":
                state["coaches"] = text
                state["step"] = "max_slots"
                send_message(user_id, "👥 Макс. участников:")

            elif step == "max_slots":
                if not text.isdigit() or int(text) < 1:
                    send_message(user_id, "❌ Число > 0")
                    return {"ok": True}
                state["max_slots"] = int(text)
                state["step"] = "price"
                send_message(user_id, "💰 Цена (руб):")

            elif step == "price":
                state["price"] = text
                state["step"] = "extra"
                send_message(user_id, "ℹ️ Доп. информация (или «нет»):")

            elif step == "extra":
                state["extra"] = "" if text.lower() in ("нет", "-", "—", "пропустить") else text

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

                post = build_training_post(training)
                kb = training_inline_buttons(training.id)
                resp = send_message(GROUP_CHAT_ID, post, kb)

                if isinstance(resp, dict) and resp.get("message"):
                    training.group_msg_id = resp["message"]["body"]["mid"]
                    db.commit()

                trainer_kb = trainer_training_buttons(training.id)
                send_message(user_id, f"✅ Тренировка #{training.id} создана!", trainer_kb)
                del user_states[user_id]

                # Автозапись Щекетова через 5 секунд
                def auto_join():
                    time.sleep(5)
                    tr = db.query(Training).get(training.id)
                    if not tr or not tr.is_active:
                        return
                    main_count = len(get_main_list(tr.id))
                    queue_count = len(get_queue_list(tr.id))
                    if main_count < tr.max_slots:
                        pos = main_count + 1
                        db.add(Registration(
                            training_id=tr.id,
                            user_id=AUTO_JOIN_USER_ID,
                            last_name=AUTO_JOIN_LAST_NAME,
                            status="main",
                            position=pos
                        ))
                        db.commit()
                        try_send_to_user(AUTO_JOIN_USER_ID,
                            f"✅ {AUTO_JOIN_LAST_NAME}, вы в основном составе! (#{pos}/{tr.max_slots})"
                        )
                        send_message(GROUP_CHAT_ID,
                            f"✅ {AUTO_JOIN_DISPLAY} ({AUTO_JOIN_LAST_NAME}) записан в основной состав (#{pos}/{tr.max_slots})"
                        )
                    else:
                        pos = queue_count + 1
                        db.add(Registration(
                            training_id=tr.id,
                            user_id=AUTO_JOIN_USER_ID,
                            last_name=AUTO_JOIN_LAST_NAME,
                            status="queue",
                            position=pos
                        ))
                        db.commit()
                        try_send_to_user(AUTO_JOIN_USER_ID,
                            f"⏳ {AUTO_JOIN_LAST_NAME}, мест нет. Вы {pos}-й в очереди."
                        )
                        send_message(GROUP_CHAT_ID,
                            f"⏳ {AUTO_JOIN_DISPLAY} ({AUTO_JOIN_LAST_NAME}) добавлен в очередь (#{pos})"
                        )
                    update_training_post(tr)

                threading.Thread(target=auto_join).start()

        except Exception as e:
            print(f"FSM ERROR: {e}")
            send_message(user_id, f"❌ Ошибка: {e}")
            user_states.pop(user_id, None)
            edit_states.pop(user_id, None)
            edit_time_start.pop(user_id, None)

        return {"ok": True}

    return {"ok": True}