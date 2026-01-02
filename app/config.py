import os

import dotenv

dotenv.load_dotenv()


class Settings:
    OPENROUTER_APIKEY: str = os.getenv("OPENROUTER_APIKEY")
    MODEL_NAME: str = os.getenv("MODEL_NAME")
    OPENWEATHERMAP_APIKEY: str = os.getenv("OPENWEATHERMAP_APIKEY")
    SERPAPI_APIKEY: str = os.getenv("SERPAPI_APIKEY")
    DATABASE_URL: str = os.getenv("DATABASE_URL")
