import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class LocalDatabaseService:
    """Local SQLite database service for user-specific data"""
    
    def __init__(self):
        self.config_manager = get_config_manager()
        
        # Get configuration values
        self.local_db_path = Path(self.config_manager.get_config("database.local_db_path", "data/local/local.db"))
        
        # Ensure directory exists
        self.local_db_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Local database service initialized with path: {self.local_db_path}")
    
    def initialize(self) -> bool:
        """Initialize the local database with required tables"""
        try:
            logger.info("Initializing local database...")
            
            # Ensure tables exist
            self.ensure_tables_exist()
            
            logger.info("Local database initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize local database: {e}")
            return False
    
    def ensure_tables_exist(self) -> bool:
        """Ensure required local database tables exist"""
        try:
            logger.info("Ensuring local database tables exist...")
            
            # Create user preferences table
            create_user_preferences_table = """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, preference_key)
                )
            """
            
            # Create user sessions table
            create_user_sessions_table = """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    expires_at DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create local cache table for remote data
            create_local_cache_table = """
                CREATE TABLE IF NOT EXISTS local_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT UNIQUE NOT NULL,
                    cache_data TEXT NOT NULL,
                    last_synced DATETIME DEFAULT CURRENT_TIMESTAMP,
                    expires_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create sync status table
            create_sync_status_table = """
                CREATE TABLE IF NOT EXISTS sync_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT UNIQUE NOT NULL,
                    last_sync_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    sync_status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Execute table creation queries
            self.execute_query(create_user_preferences_table)
            self.execute_query(create_user_sessions_table)
            self.execute_query(create_local_cache_table)
            self.execute_query(create_sync_status_table)
            
            logger.info("Local database tables ensured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure local tables exist: {e}")
            return False
    
    def execute_query(self, query: str, params: tuple = ()) -> Dict[str, Any]:
        """Execute a query on the local database"""
        try:
            conn = sqlite3.connect(str(self.local_db_path))
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            try:
                cursor.execute(query, params)
                
                # Determine if this is a SELECT query
                if query.strip().upper().startswith('SELECT'):
                    rows = cursor.fetchall()
                    data = [dict(row) for row in rows]
                    return {
                        "success": True,
                        "data": data,
                        "row_count": len(data)
                    }
                else:
                    # For INSERT, UPDATE, DELETE
                    conn.commit()
                    return {
                        "success": True,
                        "row_count": cursor.rowcount,
                        "lastrowid": cursor.lastrowid
                    }
                    
            finally:
                cursor.close()
                conn.close()
                
        except Exception as e:
            logger.error(f"Local database query failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": []
            }
    
    def get_user_preference(self, user_id: int, preference_key: str) -> Optional[str]:
        """Get a user preference value"""
        result = self.execute_query(
            "SELECT preference_value FROM user_preferences WHERE user_id = ? AND preference_key = ?",
            (user_id, preference_key)
        )
        
        if result["success"] and result["data"]:
            return result["data"][0]["preference_value"]
        return None
    
    def set_user_preference(self, user_id: int, preference_key: str, preference_value: str) -> bool:
        """Set a user preference value"""
        result = self.execute_query(
            """INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, preference_key, preference_value)
        )
        return result["success"]
    
    def get_user_preferences(self, user_id: int) -> Dict[str, str]:
        """Get all user preferences"""
        result = self.execute_query(
            "SELECT preference_key, preference_value FROM user_preferences WHERE user_id = ?",
            (user_id,)
        )
        
        if result["success"]:
            return {row["preference_key"]: row["preference_value"] for row in result["data"]}
        return {}
    
    def cache_data(self, cache_key: str, data: str, expires_at: Optional[str] = None) -> bool:
        """Cache data locally"""
        result = self.execute_query(
            """INSERT OR REPLACE INTO local_cache (cache_key, cache_data, expires_at, last_synced)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (cache_key, data, expires_at)
        )
        return result["success"]
    
    def get_cached_data(self, cache_key: str) -> Optional[str]:
        """Get cached data"""
        result = self.execute_query(
            "SELECT cache_data FROM local_cache WHERE cache_key = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)",
            (cache_key,)
        )
        
        if result["success"] and result["data"]:
            return result["data"][0]["cache_data"]
        return None
    
    def update_sync_status(self, table_name: str, status: str, error_message: str = None) -> bool:
        """Update sync status for a table"""
        result = self.execute_query(
            """INSERT OR REPLACE INTO sync_status (table_name, sync_status, error_message, last_sync_time, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (table_name, status, error_message)
        )
        return result["success"]
    
    def get_sync_status(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get sync status for a table"""
        result = self.execute_query(
            "SELECT * FROM sync_status WHERE table_name = ?",
            (table_name,)
        )
        
        if result["success"] and result["data"]:
            return result["data"][0]
        return None
    
    def get_all_sync_statuses(self) -> List[Dict[str, Any]]:
        """Get all sync statuses"""
        result = self.execute_query("SELECT * FROM sync_status ORDER BY table_name")
        
        if result["success"]:
            return result["data"]
        return []
    
    def clear_table_cache(self, table_name: str) -> bool:
        """Clear cache entries related to a specific table"""
        try:
            # Clear all query-based cache entries (since we can't easily match them to specific tables)
            result = self.execute_query(
                "DELETE FROM local_cache WHERE cache_key LIKE 'query_%'"
            )
            
            # Also clear remote table cache entries
            result2 = self.execute_query(
                "DELETE FROM local_cache WHERE cache_key = ?",
                (f"remote_{table_name}",)
            )
            
            logger.info(f"Cleared all query cache entries for table: {table_name}")
            return result["success"] and result2["success"]
            
        except Exception as e:
            logger.error(f"Failed to clear cache for table {table_name}: {e}")
            return False