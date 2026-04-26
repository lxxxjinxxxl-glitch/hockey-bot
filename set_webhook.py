import requests

BOT_TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"
WEBHOOK_URL = "https://hockey-bot-production.up.railway.app/webhook"

# Сначала удаляем старую подписку
requests.delete(
    f"https://platform-api.max.ru/subscriptions?url={WEBHOOK_URL}",
    headers={"Authorization": BOT_TOKEN}
)

# Пробуем разные названия callback-события
types_to_try = [
    "message_callback",
    "inline_keyboard_callback",
    "button_callback",
    "callback_query",
]

for t in types_to_try:
    resp = requests.post(
        "https://platform-api.max.ru/subscriptions",
        headers={"Authorization": BOT_TOKEN, "Content-Type": "application/json"},
        json={
            "url": WEBHOOK_URL,
            "update_types": ["message_created", t]
        }
    )
    print(f"{t}: {resp.status_code} | {resp.text[:200]}")
    if resp.status_code == 200:
        print(f"✅ Найдено: {t}")
        break