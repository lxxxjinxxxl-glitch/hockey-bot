def training_inline_buttons(training_id: int):
    """Inline-кнопки для поста в чате (тип message)"""
    return {
        "attachments": [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [
                            {
                                "type": "message",
                                "text": "✅ Записаться",
                                "payload": f"/join_{training_id}"
                            },
                            {
                                "type": "message",
                                "text": "👥 Кто идёт?",
                                "payload": f"/list_{training_id}"
                            }
                        ],
                        [
                            {
                                "type": "message",
                                "text": "❌ Отказаться",
                                "payload": f"/leave_{training_id}"
                            }
                        ]
                    ]
                }
            }
        ]
    }