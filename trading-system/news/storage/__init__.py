# News Storage Module
# Contains storage backends for various databases

from .base_storage import BaseStorage
from .postgres_storage import PostgreSQLStorage
from .mysql_storage import MySQLStorage
from .sqlite_storage import SQLiteStorage

__all__ = [
    "BaseStorage",
    "PostgreSQLStorage",
    "MySQLStorage",
    "SQLiteStorage",
]
