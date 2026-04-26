def training_inline_buttons(training_id: int):
    """Inline-кнопки для поста в чате"""
    return {
        "attachments": [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
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
                }
            }
        ]
    }