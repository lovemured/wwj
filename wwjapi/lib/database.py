"""Shared MySQL connection helpers for local CRM scripts."""
from contextlib import contextmanager

import pymysql

from lib.config import load_config


def connect_database(env=None, profile=None):
    """Open a MySQL connection using the selected local config file."""
    database = load_config(env, profile).get("database", {})
    required = ("host", "name", "user", "password")
    missing = [key for key in required if not database.get(key)]
    if missing:
        raise ValueError(f"数据库配置缺少字段: {', '.join(missing)}")

    return pymysql.connect(
        host=database["host"],
        port=int(database.get("port", 3306)),
        user=database["user"],
        password=database["password"],
        database=database["name"],
        charset=database.get("charset", "utf8mb4"),
    )


@contextmanager
def database_connection(env=None, profile=None):
    """Yield a configured MySQL connection and always close it afterwards."""
    connection = connect_database(env, profile)
    try:
        yield connection
    finally:
        connection.close()
