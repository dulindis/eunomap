from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    RESET_DB = os.getenv("RESET_DB")
    DATABASE_URL = os.getenv("DATABASE_URL")
    GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    PASSWORD_SALT = os.getenv("PASSWORD_SALT")
    
    # Tag Mode Configuration
    TAG_MODE = os.getenv("TAG_MODE", "path").lower()  # "path" or "flat"
    TAG_DISAMBIGUATION_ENABLED = os.getenv("TAG_DISAMBIGUATION_ENABLED", "true").lower() == "true"
    TAG_AUTO_CREATE = os.getenv("TAG_AUTO_CREATE", "true").lower() == "true"
    TAG_DEFAULT_PARENT = os.getenv("TAG_DEFAULT_PARENT", None)
