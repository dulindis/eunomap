from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    RESET_DB = os.getenv("RESET_DB") == "false"
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "your_client_id")
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
