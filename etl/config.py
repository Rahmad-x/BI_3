from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

load_dotenv()

def create_connection(prefix):
    host = os.getenv(f"{prefix}_HOST")
    port = os.getenv(f"{prefix}_PORT", "3306")
    user = os.getenv(f"{prefix}_USER")
    password = os.getenv(f"{prefix}_PASSWORD")
    database = os.getenv(f"{prefix}_DATABASE")

    connection_url = (
        f"mysql+pymysql://{user}:{password}"
        f"@{host}:{port}/{database}"
    )

    return create_engine(
        connection_url,
        pool_pre_ping=True
    )