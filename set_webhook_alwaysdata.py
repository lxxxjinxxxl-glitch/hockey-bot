import requests

BOT_TOKEN = "f9LHodD0cOK84NIrQMJHPRnik8266f6x7drNxJrLZ49v5-gGwdY9o0KJHBJNNudPUO-TyPkhZ5VkAO0Z9G9S"
ALWAYSDATA_URL = "https://jin.alwaysdata.net/webhook"

# Удалить старую подписку
requests.delete(
    f"https://platform-api.max.ru/subscriptions?url=https://hockey-bot-production.up.railway.app/webhook",
    headers={"Authorization": BOT_TOKEN}
)

# Новая на alwaysdata
resp = requests.post(
    "https://platform-api.max.ru/subscriptions",
    headers={"Authorization": BOT_TOKEN, "Content-Type": "application/json"},
    json={"url": ALWAYSDATA_URL, "update_types": ["message_created", "message_callback"]}
)
print(resp.status_code, resp.text)