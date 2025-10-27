import asyncio
import threading
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from src.services.local_database_service import LocalDatabaseService
from src.services.git_database_service import GitDatabaseService
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class HybridDatabaseService:
    """Hybrid database service managing both local and remote databases"""
    
    def __init__(self, local_db_service: LocalDatabaseService, remote_db_service: GitDatabaseService):
        self.local_db = local_db_service
        self.remote_db = remote_db_service
        
        # Configuration
        self.sync_interval = 300  # 5 minutes in seconds
        self.cache_expiry = 3600  # 1 hour in seconds
        
        # Sync control
        self.sync_thread = None
        self.sync_running = False
        self.last_sync_time = None
        
        logger.info("Hybrid database service initialized")
    
    def initialize(self) -> bool:
        """Initialize both local and remote databases"""
        try:
            logger.info("Initializing hybrid database service...")
            
            # Initialize local database
            if not self.local_db.initialize():
                logger.error("Failed to initialize local database")
                return False
            
            # Initialize remote database
            if not self.remote_db.initialize():
                logger.error("Failed to initialize remote database")
                return False
            
            # On startup: fetch remote and copy to local
            logger.info("Fetching remote database and copying to local...")
            self._copy_remote_to_local_on_startup()
            
            # Start periodic sync (local → remote)
            self.start_periodic_sync()
            
            logger.info("Hybrid database service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize hybrid database service: {e}")
            return False
    
    def start_periodic_sync(self):
        """Start the periodic synchronization thread"""
        if self.sync_thread is None or not self.sync_thread.is_alive():
            self.sync_running = True
            self.sync_thread = threading.Thread(target=self._sync_worker, daemon=True)
            self.sync_thread.start()
            logger.info("Periodic sync thread started")
    
    def stop_periodic_sync(self):
        """Stop the periodic synchronization thread"""
        self.sync_running = False
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=5)
        logger.info("Periodic sync thread stopped")
    
    def _copy_remote_to_local_on_startup(self):
        """Copy remote database to local on startup"""
        try:
            logger.info("Fetching latest changes from remote Git repository...")
            # Fetch from Git
            self.remote_db.git_storage.clone_or_fetch_repo()
            
            # Copy remote database file to local
            import shutil
            import sqlite3
            from pathlib import Path
            
            remote_db_path = Path(self.remote_db.git_storage.local_repo_path) / "database" / "sakura_db.db"
            local_db_path = self.local_db.local_db_path
            
            if remote_db_path.exists():
                if local_db_path.exists():
                    # Check database versions
                    local_version = 0
                    remote_version = 0
                    
                    try:
                        local_conn = sqlite3.connect(str(local_db_path))
                        local_cursor = local_conn.cursor()
                        local_cursor.execute("SELECT metadata_value FROM database_metadata WHERE metadata_key = 'version'")
                        result = local_cursor.fetchone()
                        if result:
                            local_version = int(result[0])
                        local_conn.close()
                    except Exception as e:
                        logger.warning(f"Could not get local version: {e}")
                    
                    try:
                        remote_conn = sqlite3.connect(str(remote_db_path))
                        remote_cursor = remote_conn.cursor()
                        remote_cursor.execute("SELECT metadata_value FROM database_metadata WHERE metadata_key = 'version'")
                        result = remote_cursor.fetchone()
                        if result:
                            remote_version = int(result[0])
                        remote_conn.close()
                    except Exception as e:
                        logger.warning(f"Could not get remote version: {e}")
                    
                    logger.info(f"Startup sync: Local version: {local_version}, Remote version: {remote_version}")
                    
                    # Check timestamps
                    remote_mtime = remote_db_path.stat().st_mtime
                    local_mtime = local_db_path.stat().st_mtime
                    
                    # Guard: If local has newer version (changes), sync local to remote
                    if local_version > remote_version:
                        logger.warning(f"Local has newer changes (v{local_version} > v{remote_version}). Syncing local to remote...")
                        self.sync_local_to_remote()
                        logger.info("Local database preserved, remote updated with local data")
                    # If local is older, copy from remote
                    elif local_version < remote_version:
                        logger.info(f"Remote has newer changes (v{remote_version} > v{local_version}), copying from remote...")
                        shutil.copy2(remote_db_path, local_db_path)
                        logger.info(f"✓ Copied remote database to: {local_db_path}")
                    # If versions are equal, check timestamps for conflicts
                    else:
                        time_diff = remote_mtime - local_mtime
                        
                        # If remote is significantly newer (> 1 second), there's a conflict
                        if time_diff > 1:
                            logger.warning(f"Startup version conflict (both v{local_version}): remote is {time_diff:.1f}s newer - fetching remote...")
                            shutil.copy2(remote_db_path, local_db_path)
                            logger.info(f"✓ Copied remote database to resolve conflict: {local_db_path}")
                        elif time_diff < -1:
                            logger.warning(f"Startup version conflict (both v{local_version}): local is {abs(time_diff):.1f}s newer - syncing local to remote...")
                            self.sync_local_to_remote()
                        else:
                            logger.info(f"Both databases at same version (v{local_version}) and similar timestamp - no sync needed")
                else:
                    logger.info("Local database doesn't exist, copying from remote...")
                    local_db_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(remote_db_path, local_db_path)
                    logger.info(f"✓ Copied remote database to: {local_db_path}")
            else:
                logger.warning("Remote database file not found, keeping local database")
                
        except Exception as e:
            logger.error(f"Failed to copy remote to local on startup: {e}")
    
    def _sync_worker(self):
        """Worker thread for periodic synchronization (remote → local for reads)"""
        while self.sync_running:
            try:
                logger.info("Starting periodic sync (remote → local)...")
                self.sync_remote_to_local()
                self.last_sync_time = datetime.now()
                logger.info(f"Periodic sync completed at {self.last_sync_time}")
                
                # Wait for next sync interval
                time.sleep(self.sync_interval)
                
            except Exception as e:
                logger.error(f"Error in periodic sync: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def sync_local_to_remote(self):
        """Synchronize local database to remote (periodic sync)"""
        try:
            logger.info("Syncing local database to remote...")
            
            # Copy local database file to remote location
            import shutil
            from pathlib import Path
            
            local_db_path = self.local_db.local_db_path
            remote_db_path = Path(self.remote_db.git_storage.local_repo_path) / "database" / "sakura_db.db"
            
            if local_db_path.exists():
                remote_db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(local_db_path, remote_db_path)
                logger.info(f"✓ Copied local database to remote: {remote_db_path}")
                
                # Commit to Git
                git_token = None
                try:
                    from flask import g
                    username = g.get('current_username')
                    if username:
                        git_token = self.remote_db.get_user_git_token(username)
                except:
                    pass
                
                commit_success = self.remote_db.commit_changes("Periodic sync: update from local database", git_token)
                if commit_success:
                    logger.info("✓ Changes committed to Git repository")
                else:
                    logger.warning("Failed to commit changes to Git")
            else:
                logger.warning("Local database file not found")
            
        except Exception as e:
            logger.error(f"Failed to sync local to remote: {e}")
    
    def sync_remote_to_local(self):
        """Synchronize remote database to local (periodic sync for reads)"""
        try:
            logger.info("Syncing remote database to local...")
            
            # Fetch latest from Git
            self.remote_db.git_storage.clone_or_fetch_repo()
            
            # Copy remote database file to local location
            import shutil
            import sqlite3
            from pathlib import Path
            
            remote_db_path = Path(self.remote_db.git_storage.local_repo_path) / "database" / "sakura_db.db"
            local_db_path = self.local_db.local_db_path
            
            if remote_db_path.exists():
                # Check database versions to determine if there are changes
                local_version = 0
                remote_version = 0
                
                try:
                    # Get local database version
                    local_conn = sqlite3.connect(str(local_db_path))
                    local_cursor = local_conn.cursor()
                    local_cursor.execute("SELECT metadata_value FROM database_metadata WHERE metadata_key = 'version'")
                    result = local_cursor.fetchone()
                    if result:
                        local_version = int(result[0])
                    local_conn.close()
                except Exception as e:
                    logger.warning(f"Could not get local database version: {e}")
                    local_version = 0
                
                try:
                    # Get remote database version
                    remote_conn = sqlite3.connect(str(remote_db_path))
                    remote_cursor = remote_conn.cursor()
                    remote_cursor.execute("SELECT metadata_value FROM database_metadata WHERE metadata_key = 'version'")
                    result = remote_cursor.fetchone()
                    if result:
                        remote_version = int(result[0])
                    remote_conn.close()
                except Exception as e:
                    logger.warning(f"Could not get remote database version: {e}")
                    remote_version = 0
                
                logger.info(f"Local version: {local_version}, Remote version: {remote_version}")
                
                # Check timestamps as backup
                remote_mtime = remote_db_path.stat().st_mtime
                local_mtime = local_db_path.stat().st_mtime
                
                # Only sync if: remote has changes (higher version) AND local has no changes (lower version)
                if remote_version > local_version:
                    logger.info(f"Remote has newer changes (v{remote_version} > v{local_version}) - copying from remote...")
                    local_db_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(remote_db_path, local_db_path)
                    logger.info(f"✓ Copied remote database to local: {local_db_path}")
                elif remote_version < local_version:
                    # This should not happen as local changes are synced immediately
                    # Sync local to remote to fix inconsistency
                    logger.warning(f"Detected inconsistency: local (v{local_version}) > remote (v{remote_version}). Syncing local to remote...")
                    self.sync_local_to_remote()
                elif remote_version == local_version:
                    # Same version but check timestamps for conflicts
                    time_diff = remote_mtime - local_mtime
                    
                    # If remote is significantly newer (> 1 second), there's a conflict
                    # Another client wrote to same version, so we should fetch remote
                    if time_diff > 1:
                        logger.warning(f"Version conflict detected (both v{local_version}): remote is {time_diff:.1f}s newer - fetching remote to resolve conflict...")
                        local_db_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(remote_db_path, local_db_path)
                        logger.info(f"✓ Copied remote database to resolve conflict: {local_db_path}")
                    elif time_diff < -1:
                        # Local is significantly newer, sync local to remote
                        logger.warning(f"Version conflict detected (both v{local_version}): local is {abs(time_diff):.1f}s newer - syncing local to remote...")
                        self.sync_local_to_remote()
                    else:
                        logger.info(f"Both databases at same version (v{local_version}) and similar timestamp - no sync needed")
                else:
                    logger.info("Local database is up-to-date, no sync needed")
            else:
                logger.warning("Remote database file not found")
            
        except Exception as e:
            logger.error(f"Failed to sync remote to local: {e}")
    
    def _sync_table_to_cache(self, table_name: str):
        """Sync a specific table from remote to local cache"""
        try:
            # Get data from remote database
            query = f"SELECT * FROM {table_name}"
            remote_result = self.remote_db.execute_query(query)
            
            if remote_result.get("success"):
                # Cache the data locally
                cache_key = f"remote_{table_name}"
                import json
                cache_data = json.dumps(remote_result["data"])
                
                # Set expiry time
                expires_at = datetime.now() + timedelta(seconds=self.cache_expiry)
                
                self.local_db.cache_data(cache_key, cache_data, expires_at.isoformat())
                self.local_db.update_sync_status(table_name, "success")
                
                logger.info(f"Synced {len(remote_result['data'])} records from {table_name}")
            else:
                self.local_db.update_sync_status(table_name, "error", remote_result.get("error", "Unknown error"))
                logger.error(f"Failed to sync {table_name}: {remote_result.get('error')}")
                
        except Exception as e:
            self.local_db.update_sync_status(table_name, "error", str(e))
            logger.error(f"Error syncing {table_name}: {e}")
    
    def execute_query(self, query: str, database_name: str = "default", use_cache: bool = True) -> Dict[str, Any]:
        """Execute query with hybrid strategy"""
        try:
            # Get current username from Flask's g object for authenticated requests
            try:
                from flask import g
                username = g.get('current_username')
            except:
                username = None
            
            # Determine query type
            query_upper = query.strip().upper()
            
            if query_upper.startswith('SELECT'):
                return self._handle_read_query(query, database_name, use_cache)
            else:
                return self._handle_write_query(query, database_name, username)
                
        except Exception as e:
            logger.error(f"Hybrid query execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": []
            }
    
    def _handle_read_query(self, query: str, database_name: str, use_cache: bool) -> Dict[str, Any]:
        """Handle read queries - execute on LOCAL database first"""
        try:
            # Always read from local database
            result = self.local_db.execute_query(query, database_name)
            
            # Cache the result if enabled and successful
            if result.get("success") and use_cache:
                cache_key = f"query_{hash(query)}"
                import json
                cache_data = json.dumps(result["data"])
                expires_at = datetime.now() + timedelta(seconds=self.cache_expiry)
                self.local_db.cache_data(cache_key, cache_data, expires_at.isoformat())
            
            return result
            
        except Exception as e:
            logger.error(f"Read query failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": []
            }
    
    def _handle_write_query(self, query: str, database_name: str, username: str = None) -> Dict[str, Any]:
        """Handle write queries - execute on LOCAL database first, then sync to remote"""
        try:
            # Before write: check if remote has newer changes that need to be synced first
            try:
                import sqlite3
                from pathlib import Path
                
                local_db_path = self.local_db.local_db_path
                remote_db_path = Path(self.remote_db.git_storage.local_repo_path) / "database" / "sakura_db.db"
                
                if remote_db_path.exists() and local_db_path.exists():
                    # Get current versions
                    local_version = 0
                    remote_version = 0
                    
                    try:
                        local_conn = sqlite3.connect(str(local_db_path))
                        local_cursor = local_conn.cursor()
                        local_cursor.execute("SELECT metadata_value FROM database_metadata WHERE metadata_key = 'version'")
                        result = local_cursor.fetchone()
                        if result:
                            local_version = int(result[0])
                        local_conn.close()
                    except:
                        pass
                    
                    try:
                        remote_conn = sqlite3.connect(str(remote_db_path))
                        remote_cursor = remote_conn.cursor()
                        remote_cursor.execute("SELECT metadata_value FROM database_metadata WHERE metadata_key = 'version'")
                        result = remote_cursor.fetchone()
                        if result:
                            remote_version = int(result[0])
                        remote_conn.close()
                    except:
                        pass
                    
                    # If remote is newer, fetch it first before allowing write
                    if remote_version > local_version:
                        logger.warning(f"Remote is newer (v{remote_version} > v{local_version}) before write. Fetching remote first...")
                        import shutil
                        shutil.copy2(remote_db_path, local_db_path)
                        logger.info("✓ Fetched remote changes before write")
            except Exception as sync_error:
                logger.warning(f"Failed to sync remote before write: {sync_error}")
            
            # Execute on LOCAL database first
            result = self.local_db.execute_query(query, database_name)
            
            # If successful, increment database version and sync to remote
            if result.get("success"):
                logger.info("Write operation successful on local database")
                
                # Increment database version to track changes
                new_version = self.local_db.increment_database_version()
                logger.info(f"Database version updated to: {new_version}")
                
                # Sync to remote in background thread
                try:
                    # Copy to remote location
                    import shutil
                    from pathlib import Path
                    
                    local_db_path = self.local_db.local_db_path
                    remote_db_path = Path(self.remote_db.git_storage.local_repo_path) / "database" / "sakura_db.db"
                    
                    if local_db_path.exists():
                        remote_db_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(local_db_path, remote_db_path)
                        logger.info("✓ Local changes synced to remote")
                        
                        # Commit to Git
                        commit_message = self._generate_commit_message(query)
                        git_token = None
                        if username:
                            git_token = self.remote_db.get_user_git_token(username)
                        
                        commit_success = self.remote_db.commit_changes(commit_message, git_token)
                        if commit_success:
                            logger.info(f"✓ Changes committed to Git as {username if username else 'system'}")
                        else:
                            logger.warning("Failed to commit changes to Git")
                except Exception as commit_error:
                    logger.error(f"Error syncing to remote: {commit_error}")
                
                # Clear relevant cache entries
                self._clear_relevant_cache(query)
            
            return result
            
        except Exception as e:
            logger.error(f"Write query failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": []
            }
    
    def _generate_commit_message(self, query: str) -> str:
        """Generate informative commit message from SQL query"""
        try:
            query_upper = query.strip().upper()
            
            # Extract operation and table name
            if query_upper.startswith('INSERT INTO'):
                parts = query.split('INSERT INTO')[1].strip().split()
                table_name = parts[0].replace('(', '').strip()
                operation = "Add"
                
                # Try to extract data for more context
                if 'username' in query:
                    # Extract username for user operations
                    import re
                    username_match = re.search(r"username['\"]?\s*=\s*['\"]?([^',\")]+)", query)
                    if username_match:
                        return f"{operation} user: {username_match.group(1)}"
                
            elif query_upper.startswith('UPDATE'):
                parts = query.split('UPDATE')[1].strip().split()
                table_name = parts[0].strip()
                operation = "Update"
                
                # Extract key information for context
                if 'password_hash' in query and 'users' in query_upper:
                    return "Update user password"
                if 'users' in query_upper:
                    # Try to extract username
                    import re
                    where_match = re.search(r"WHERE\s+username\s*=\s*['\"]?([^',\")]+)", query)
                    if where_match:
                        return f"{operation} user: {where_match.group(1)}"
                    return f"{operation} user record"
                
            elif query_upper.startswith('DELETE FROM'):
                parts = query.split('DELETE FROM')[1].strip().split()
                table_name = parts[0].strip()
                operation = "Delete"
                
                # Extract key information
                if 'users' in query_upper:
                    import re
                    where_match = re.search(r"WHERE\s+username\s*=\s*['\"]?([^',\")]+)", query)
                    if where_match:
                        return f"{operation} user: {where_match.group(1)}"
                    return f"{operation} user record"
            else:
                # Fallback for other operations
                return f"Database update: {table_name if 'table_name' in locals() else 'unknown table'}"
            
            return f"{operation} record in {table_name}"
            
        except Exception as e:
            logger.warning(f"Failed to generate commit message: {e}")
            return "Database update"

    def _clear_relevant_cache(self, query: str):
        """Clear cache entries related to the modified table"""
        try:
            query_upper = query.strip().upper()
            
            # Determine which table was modified
            if query_upper.startswith('INSERT INTO') or query_upper.startswith('UPDATE') or query_upper.startswith('DELETE FROM'):
                # Extract table name from query
                if 'INSERT INTO' in query_upper:
                    table_name = query_upper.split('INSERT INTO')[1].split()[0].strip()
                elif 'UPDATE' in query_upper:
                    table_name = query_upper.split('UPDATE')[1].split()[0].strip()
                elif 'DELETE FROM' in query_upper:
                    table_name = query_upper.split('DELETE FROM')[1].split()[0].strip()
                else:
                    return
                
                # Clear cache entries for this table
                self.local_db.clear_table_cache(table_name)
                logger.info(f"Cleared cache for table: {table_name}")
                
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
    
    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """Get user data combining local preferences and remote data"""
        try:
            # Get user preferences from local database
            preferences = self.local_db.get_user_preferences(user_id)
            
            # Get user data from remote database
            query = f"SELECT * FROM users WHERE id = {user_id}"
            remote_result = self.remote_db.execute_query(query)
            
            user_data = {}
            if remote_result.get("success") and remote_result.get("data"):
                user_data = remote_result["data"][0]
            
            # Merge with local preferences
            user_data["preferences"] = preferences
            
            return user_data
            
        except Exception as e:
            logger.error(f"Failed to get user data: {e}")
            return {}
    
    def set_user_preference(self, user_id: int, preference_key: str, preference_value: str) -> bool:
        """Set user preference in local database"""
        return self.local_db.set_user_preference(user_id, preference_key, preference_value)
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get overall sync status"""
        try:
            sync_statuses = self.local_db.get_all_sync_statuses()
            
            return {
                "success": True,
                "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
                "sync_running": self.sync_running,
                "sync_interval": self.sync_interval,
                "tables": sync_statuses
            }
            
        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def force_sync(self) -> bool:
        """Force immediate synchronization (local → remote)"""
        try:
            logger.info("Forcing immediate synchronization...")
            self.sync_local_to_remote()
            self.last_sync_time = datetime.now()
            logger.info("Force sync completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Force sync failed: {e}")
            return False
    
    def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries"""
        try:
            result = self.local_db.execute_query(
                "DELETE FROM local_cache WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP"
            )
            
            if result.get("success"):
                logger.info(f"Cleaned up {result.get('row_count', 0)} expired cache entries")
                return result.get("row_count", 0)
            
            return 0
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            return 0
    
    def list_databases(self) -> List[str]:
        """List available databases (for legacy compatibility)"""
        try:
            # Return the main database name
            return ["sakura_db"]
        except Exception as e:
            logger.error(f"Failed to list databases: {e}")
            return []
