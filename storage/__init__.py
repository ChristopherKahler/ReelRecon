"""
Storage module for ReelRecon Asset Management System.

Provides SQLite-based storage for assets and collections with full-text search.
"""

from .database import init_db, get_db_connection, DATABASE_PATH
from .models import Asset, Collection, AssetCollection

__all__ = [
    'init_db',
    'get_db_connection',
    'DATABASE_PATH',
    'Asset',
    'Collection',
    'AssetCollection'
]
