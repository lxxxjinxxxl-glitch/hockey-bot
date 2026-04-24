import os
from dotenv import load_dotenv
from pathlib import Path

# 👉 жёстко указываем путь к .env
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

BOT_TOKEN = os.getenv("BOT_TOKEN")

print("CONFIG TOKEN:", BOT_TOKEN)  # 👈 проверка

ADMINS = [623400516852]