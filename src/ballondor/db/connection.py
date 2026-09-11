"""Database helpers for Ballon d'Or Index."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]


def load_env() -> None:
    load_dotenv(ROOT / ".env")


def database_url() -> str:
    load_env()
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env")
    return url


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url())
