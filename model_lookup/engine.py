# db/engine.py

import os
import urllib.parse
from sqlalchemy import create_engine
from dotenv import load_dotenv
from pathlib import Path

# -------------------------
# Environment loading
# -------------------------


def load_env():
    """
    Load environment variables from .env file.
    Must be called explicitly by the application.
    """
    base_dir = Path.cwd()
    env_path = base_dir.parent / "model_lookup" / "creds" / ".env"

    load_dotenv(dotenv_path=env_path)

    required_vars = [
        "pb_aristor_server",
        "DB_VehConfig",
        "USER_NAME",
        "PASSWORD",
        "ODBC_DRIVER",
    ]

    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        raise RuntimeError(f"Missing environment variables: {missing}")


# -------------------------
# Engine factory
# -------------------------


def create_engine_from_env():
    """
    Create and return a SQLAlchemy Engine using environment variables.
    """
    odbc_str = (
        f"DRIVER={{{os.getenv('ODBC_DRIVER')}}};"
        f"SERVER={os.getenv('pb_aristor_server')};"
        f"DATABASE={os.getenv('DB_VehConfig')};"
        f"UID={os.getenv('USER_NAME')};"
        f"PWD={os.getenv('PASSWORD')};"
        "TrustServerCertificate=yes;"
    )

    odbc_params = urllib.parse.quote_plus(odbc_str)

    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={odbc_params}",
        pool_pre_ping=True,
        fast_executemany=True,
    )
