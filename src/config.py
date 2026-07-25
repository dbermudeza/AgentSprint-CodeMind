import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    """Configuración centralizada del proyecto, cargada desde variables de entorno."""

    openai_api_key: str


settings = Settings(openai_api_key=os.getenv("OPENAI_API_KEY"))
