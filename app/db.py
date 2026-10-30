import os
import psycopg

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://market:market@localhost:5432/market"
)


def get_conn():
    return psycopg.connect(DATABASE_URL)
