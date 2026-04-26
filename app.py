# app.py

import requests
import json
import re
from fastapi import FastAPI, Request

from database import init_db, SessionLocal, Training, Registration
from keyboards import training_inline_buttons
from config import BOT_TOKEN, API_URL, GROUP_CHAT_ID, TRAINER_IDS, BOT_USER_ID

init_db()
db = SessionLocal()

app = FastAPI()

# FSM для создания тренировки и для записи (фамилия)
user_states = {}
# FSM для редактирования тренировки
edit_states = {}

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


def send_message(target_id: int, text: str, inline_keyboard=None):
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

    r = requests.post(url, headers=headers, json=payload)
    print(f"SEND to {target_id}: {r.status_code}")
    try:
        return r.json()
    except:
        print("SEND RAW:", r.text[:300])
        return {"ok": False, "text": r.text}


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


def build_training_post(training) -> str:
    """Собирает текст поста для чата"""
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
    return post


@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    print("UPDATE:", json.dumps(data, ensure_ascii=False, indent=2)[:500])

    # --- MESSAGE_CALLBACK (кнопки) ---
    if data.get("update_type") == "message_callback" or data.get("callback"):
        cb = data.get("callback") or data
        user_id = cb.get("user", {}).get("user_id") or cb.get("from", {}).get("user_id") or ""
        user_first = cb.get("user", {}).get("first_name", "")
        user_last = cb.get("user", {}).get("last_name", "")
        user_display = f"{user_first} {user_last}".strip()
        cb_data = cb.get("payload") or cb.get("data") or ""

        print(f"CALLBACK: user={user_id} ({user_display}), payload={cb_data}")

        if not user_id:
            return {"ok": True}

        # Записаться — запрос фамилии
        if cb_data.startswith("join_"):
            training_id = int(cb_data.split("_")[1])
            training = db.query(Training).get(training_id)
            if not training or not training.is_active:
                send_message(GROUP_CHAT_ID, f"@{user_display}, тренировка недоступна")
                return {"ok": True}

            exist = db.query(Registration).filter_by(
                training_id=training_id, user_id=user_id
            ).first()
            if exist:
                send_message(GROUP_CHAT_ID, f"@{user_display}, вы уже записаны")
                return {"ok": True}

            # Сохраняем training_id и запускаем FSM для фамилии
            user_states[user_id] = {
                "step": "ask_lastname",
                "training_id": training_id,
                "first_name": user_first,
                "last_name": user_last
            }
            # Пытаемся в личку, иначе в чат
            if not try_send_to_user(user_id, "📝 Введите вашу ФАМИЛИЮ для записи:"):
                send_message(GROUP_CHAT_ID, f"@{user_display}, напишите фамилию в чат для записи")
            return {"ok": True}

        # Кто идёт
        elif cb_data.startswith("list_"):
            training_id = int(cb_data.split("_")[1])
            main = get_main_list(training_id)
            queue = get_queue_list(training_id)

            text = "👥 Состав:\n"
            if main:
                for i, r in enumerate(main, 1):
                    display = f"{r.first_name} {r.last_name}".strip()
                    text += f"{i}. {display} (ID:{r.user_id})\n"
            else:
                text += "Пока никого\n"
            text += "\n⏳ Очередь:\n"
            if queue:
                for i, r in enumerate(queue, 1):
                    display = f"{r.first_name} {r.last_name}".strip()
                    text += f"{i}. {display} (ID:{r.user_id})\n"
            else:
                text += "Пусто"

            if not try_send_to_user(user_id, text):
                send_message(GROUP_CHAT_ID, f"@{user_display}, не могу отправить в личку. Нажмите НАЧАТЬ в кнопке ниже")
            return {"ok": True}

        # Отказаться
        elif cb_data.startswith("leave_"):
            training_id = int(cb_data.split("_")[1])
            reg = db.query(Registration).filter_by(
                training_id=training_id, user_id=user_id
            ).first()
            if not reg:
                send_message(GROUP_CHAT_ID, f"@{user_display}, вы не записаны")
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
                    try_send_to_user(first_queue.user_id, "🎉 Место освободилось! Вы в основном составе!")

            send_message(GROUP_CHAT_ID, f"@{user_display}, вы отписаны")
            return {"ok": True}

        return {"ok": True}

    # --- ОБЫЧНОЕ СООБЩЕНИЕ ---
    if data.get("update_type") != "message_created":
        return {"ok": True}

    msg = data["message"]
    text = msg["body"].get("text", "").strip()
    user_id = msg["sender"]["user_id"]
    user_first = msg["sender"].get("first_name", "")

    print(f"TEXT: '{text}' | from: {user_id}")

    # ----- FSM: ответ на запрос фамилии -----
    if user_id in user_states and user_states[user_id].get("step") == "ask_lastname":
        state = user_states[user_id]
        state["last_name"] = text  # пользователь ввёл фамилию
        training_id = state["training_id"]
        training = db.query(Training).get(training_id)

        if not training or not training.is_active:
            send_message(user_id, "Тренировка недоступна")
            del user_states[user_id]
            return {"ok": True}

        main_count = len(get_main_list(training_id))
        queue_count = len(get_queue_list(training_id))

        if main_count < training.max_slots:
            pos = main_count + 1
            db.add(Registration(
                training_id=training_id, user_id=user_id,
                first_name=state.get("first_name", ""),
                last_name=text,
                status="main", position=pos
            ))
            db.commit()
            msg_text = f"✅ Вы в основном составе! ({pos}/{training.max_slots})"
        else:
            pos = queue_count + 1
            db.add(Registration(
                training_id=training_id, user_id=user_id,
                first_name=state.get("first_name", ""),
                last_name=text,
                status="queue", position=pos
            ))
            db.commit()
            msg_text = f"⏳ Мест нет. Вы {pos}-й в очереди."

        if not try_send_to_user(user_id, msg_text):
            send_message(GROUP_CHAT_ID, f"@{user_first} {text}, {msg_text}")

        del user_states[user_id]
        return {"ok": True}

    # /start
    if text == "/start":
        if is_trainer(user_id):
            send_message(user_id, "Привет, тренер! 🏒\n/add — создать\n/list — список\n/edit <ID> — изменить\n/delete <ID> — удалить")
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

    # /add
    if text == "/add":
        if not is_trainer(user_id):
            send_message(user_id, "Только для тренеров")
            return {"ok": True}
        user_states[user_id] = {"step": "date"}
        send_message(user_id, "📅 Введи дату (Пример: 24.04.2026):")
        return {"ok": True}

    # /edit <ID>
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
            "1 — Дата\n2 — Время\n3 — Место\n4 — Направления\n"
            "5 — Тренеры\n6 — Места\n7 — Цена\n8 — Доп.инфо"
        )
        return {"ok": True}

    # /delete <ID>
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
            for reg in db.query(Registration).filter_by(training_id=training_id).all():
                try_send_to_user(reg.user_id, f"❌ Тренировка {training.date} отменена")
            send_message(user_id, "✅ Тренировка удалена")
        else:
            send_message(user_id, "Не найдена")
        return {"ok": True}

    # ----- FSM: редактирование тренировки -----
    if user_id in edit_states:
        state = edit_states[user_id]
        step = state["step"]
        training = db.query(Training).get(state["training_id"])

        if step == "choose_field":
            field_map = {
                "1": "date", "2": "time", "3": "place",
                "4": "direction", "5": "coaches", "6": "max_slots",
                "7": "price", "8": "extra"
            }
            if text in field_map:
                state["field"] = field_map[text]
                prompts = {
                    "date": "📅 Новая дата:",
                    "time": "🕐 Новое время (20:45-21:45):",
                    "place": "📍 Новое место (или 1-Олимпийский, 2-Айсберг, 3-Десант, 4-своё):",
                    "direction": "🎯 Новые направления (1-5 или свой текст через запятую):",
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

        elif step == "edit_value":
            field = state["field"]
            if field == "place":
                places = {"1": "ЛДС Олимпийский", "2": "ЛДС Айсберг", "3": "ЛДС Десант"}
                if text in places:
                    training.place = places[text]
                else:
                    training.place = text
            elif field == "direction":
                dirs = {"1": "Техника клюшки", "2": "Техника катания", "3": "Техника броска", "4": "ОФП", "5": "Скоростно-силовая подготовка"}
                parts = [x.strip() for x in text.split(",") if x.strip()]
                selected = [dirs[p] if p in dirs else p for p in parts]
                training.direction = ", ".join(selected)
            elif field == "max_slots":
                if not text.isdigit() or int(text) < 1:
                    send_message(user_id, "❌ Введи число > 0")
                    return {"ok": True}
                training.max_slots = int(text)
            else:
                setattr(training, field, text)

            db.commit()
            # Обновить пост в чате
            if training.group_msg_id:
                # Пытаемся обновить через attachments (или пересоздать)
                post = build_training_post(training)
                kb = training_inline_buttons(training.id)
                # MAX не поддерживает edit message? Шлём новый пост
                send_message(GROUP_CHAT_ID, "🔄 Тренировка обновлена:\n" + post, kb)

            send_message(user_id, f"✅ Поле '{field}' обновлено!")
            del edit_states[user_id]
            return {"ok": True}

    # ----- FSM: создание тренировки -----
    if user_id in user_states:
        state = user_states[user_id]
        step = state["step"]
        if step in ("ask_lastname",):
            return {"ok": True}  # уже обработано выше
        print(f"FSM step={step}, text='{text}'")

        try:
            if step == "date":
                if not re.search(r'\d{2}\.\d{2}\.\d{4}', text) and not re.search(r'\d{2}\.\d{2}', text):
                    send_message(user_id, "❌ Неверный формат. Пример: 24.04.2026")
                    return {"ok": True}
                state["date"] = text
                state["step"] = "time_start"
                send_message(user_id, "🕐 Введи время НАЧАЛА (Пример: 20:45):")

            elif step == "time_start":
                if ":" not in text:
                    send_message(user_id, "❌ Неверный формат. Введи время как 20:45:")
                    return {"ok": True}
                state["time_start"] = text
                state["step"] = "time_end"
                send_message(user_id, "🕐 Введи время КОНЦА (Пример: 21:45):")

            elif step == "time_end":
                if ":" not in text:
                    send_message(user_id, "❌ Неверный формат. Введи время как 21:45:")
                    return {"ok": True}
                state["time_end"] = text
                state["step"] = "place"
                send_message(user_id, "📍 Место:\n1 — Олимпийский\n2 — Айсберг\n3 — Десант\n4 — Свой вариант")

            elif step == "place":
                if text in PLACES:
                    state["place"] = PLACES[text]
                    state["step"] = "direction"
                    send_message(user_id, "🎯 Направления (через запятую):\n1-Клюшка, 2-Катание, 3-Бросок, 4-ОФП, 5-Скор-силовая\nИли свой текст")
                elif text == "4":
                    state["step"] = "place_custom"
                    send_message(user_id, "📍 Напиши своё место:")
                else:
                    send_message(user_id, "❌ Выбери 1, 2, 3 или 4:")
                return {"ok": True}

            elif step == "place_custom":
                state["place"] = text
                state["step"] = "direction"
                send_message(user_id, "🎯 Направления (через запятую):\n1-Клюшка, 2-Катание, 3-Бросок, 4-ОФП, 5-Скор-силовая\nИли свой текст")

            elif step == "direction":
                parts = [x.strip() for x in text.split(",") if x.strip()]
                selected = [DIRECTIONS[p] if p in DIRECTIONS else p for p in parts]
                if not selected:
                    send_message(user_id, "❌ Выбери хотя бы одно направление")
                    return {"ok": True}
                state["direction"] = ", ".join(selected)
                state["step"] = "coaches"
                send_message(user_id, "👤 Тренер(ы):")

            elif step == "coaches":
                state["coaches"] = text
                state["step"] = "max_slots"
                send_message(user_id, "👥 Макс. количество участников:")

            elif step == "max_slots":
                if not text.isdigit() or int(text) < 1:
                    send_message(user_id, "❌ Введи число (например: 25):")
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

                if isinstance(resp, dict):
                    msg_id = resp.get("message", {}).get("message_id")
                    if msg_id:
                        training.group_msg_id = str(msg_id)
                        db.commit()

                send_message(user_id, f"✅ Тренировка #{training.id} создана и опубликована!")
                del user_states[user_id]

        except Exception as e:
            print(f"FSM ERROR: {type(e).__name__}: {e}")
            send_message(user_id, f"❌ Ошибка: {e}")
            if user_id in user_states:
                del user_states[user_id]
            if user_id in edit_states:
                del edit_states[user_id]

        return {"ok": True}

    return {"ok": True}