def training_inline_buttons(training_id: int):
    """Кнопки под постом в общем чате"""
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


def trainer_training_buttons(training_id: int):
    """Кнопки для тренера в личке после создания"""
    return {
        "attachments": [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": [
                        [
                            {
                                "type": "callback",
                                "text": "📝 Состав",
                                "payload": f"list_{training_id}"
                            },
                            {
                                "type": "callback",
                                "text": "✏️ Изменить",
                                "payload": f"edit_{training_id}"
                            }
                        ],
                        [
                            {
                                "type": "callback",
                                "text": "🗑 Удалить",
                                "payload": f"delete_{training_id}"
                            }
                        ]
                    ]
                }
            }
        ]
    }