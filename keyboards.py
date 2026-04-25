def main_menu(is_trainer: bool):
    if is_trainer:
        return {
            "keyboard": [
                [{"text": "➕ Создать тренировку"}],
                [{"text": "📋 Мои тренировки"}],
            ],
            "resize_keyboard": True
        }
    else:
        return {
            "keyboard": [
                [{"text": "📝 Мои записи"}],
            ],
            "resize_keyboard": True
        }


def training_inline_buttons(training_id: int):
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Записаться", "callback_data": f"join_{training_id}"},
                {"text": "👥 Кто идёт?", "callback_data": f"list_{training_id}"},
            ],
            [
                {"text": "❌ Отказаться", "callback_data": f"leave_{training_id}"},
            ]
        ]
    }