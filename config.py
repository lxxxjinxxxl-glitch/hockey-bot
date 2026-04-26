# config.py
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://platform-api.max.ru/messages"
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
TRAINER_IDS = [125743856]
BOT_USER_ID = 623400516852
BOT_LINK = "https://max.ru/id623400516852_bot"