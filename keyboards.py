def training_inline_buttons(training_id: int, is_admin: bool = False):
    buttons = [
        [
            {
                "type": "callback",
                "text": "✅ Записаться",
                "payload": f"join_{training_id}"
            },
            {
                "type": "callback",
                "text": "👥 Кто идёт?",
                "payload": f"list_{training_id}"
            }
        ],
        [
            {
                "type": "callback",
                "text": "❌ Отказаться",
                "payload": f"leave_{training_id}"
            }
        ]
    ]

    # Кнопка «Удалить» только для админов
    if is_admin:
        buttons.append([
            {
                "type": "callback",
                "text": "🗑 Удалить",
                "payload": f"delete_{training_id}"
            }
        ])

    return {
        "attachments": [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": buttons
                }
            }
        ]
    }