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
            
            # Start periodic sync
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
    
    def _sync_worker(self):
        """Worker thread for periodic synchronization"""
        while self.sync_running:
            try:
                logger.info("Starting periodic sync...")
                self.sync_remote_to_local()
                self.last_sync_time = datetime.now()
                logger.info(f"Periodic sync completed at {self.last_sync_time}")
                
                # Wait for next sync interval
                time.sleep(self.sync_interval)
                
            except Exception as e:
                logger.error(f"Error in periodic sync: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def sync_remote_to_local(self):
        """Synchronize remote database to local cache"""
        try:
            logger.info("Syncing remote database to local cache...")
            
            # Sync users table
            self._sync_table_to_cache("users")
            
            # Sync test_cases table
            self._sync_table_to_cache("test_cases")
            
            # Sync requirements table
            self._sync_table_to_cache("requirements")
            
            logger.info("Remote to local sync completed")
            
        except Exception as e:
            logger.error(f"Failed to sync remote to local: {e}")
    
    def _sync_table_to_cache(self, table_name: str):
        """Sync a specific table from remote to local cache"""
        try:
            # Get data from remote database
            query = f"SELECT * FROM {table_name}"
            remote_result = self.remote_db.execute_query(query)
            
            if remote_result["success"]:
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
        """Handle read queries with caching strategy"""
        try:
            # Try to get from cache first if enabled
            if use_cache:
                cache_key = f"query_{hash(query)}"
                cached_data = self.local_db.get_cached_data(cache_key)
                
                if cached_data:
                    import json
                    data = json.loads(cached_data)
                    logger.debug(f"Returning cached data for query: {query[:50]}...")
                    return {
                        "success": True,
                        "data": data,
                        "row_count": len(data),
                        "cached": True
                    }
            
            # Execute on remote database
            result = self.remote_db.execute_query(query, database_name)
            
            # Cache the result if successful
            if result["success"] and use_cache:
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
        """Handle write queries with immediate sync"""
        try:
            # Execute on remote database
            result = self.remote_db.execute_query(query, database_name)
            
            # If successful, trigger immediate sync and wait for completion
            if result["success"]:
                logger.info("Write operation successful, triggering immediate sync...")
                self._trigger_immediate_sync_and_wait()
                
                # Commit changes to git repository with informative message
                logger.info("Committing changes to git repository...")
                try:
                    # Generate informative commit message from query
                    commit_message = self._generate_commit_message(query)
                    
                    # Get user's Git token if username is provided
                    git_token = None
                    if username:
                        git_token = self.remote_db.get_user_git_token(username)
                    
                    commit_success = self.remote_db.commit_changes(commit_message, git_token)
                    if commit_success:
                        logger.info(f"Successfully committed changes to git as {username if username else 'system'}")
                    else:
                        logger.warning("Failed to commit changes to git")
                except Exception as commit_error:
                    logger.error(f"Error during git commit: {commit_error}")
                
                # Clear relevant cache entries to ensure fresh data on next read
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
    
    def _trigger_immediate_sync_and_wait(self):
        """Trigger immediate synchronization and wait for completion"""
        import threading
        import time

        sync_completed = threading.Event()
        sync_error = None
        
        def sync_worker():
            nonlocal sync_error
            try:
                self.sync_remote_to_local()
                logger.info("Immediate sync completed")
            except Exception as e:
                logger.error(f"Immediate sync failed: {e}")
                sync_error = e
            finally:
                sync_completed.set()
        
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()
        
        # Wait for sync to complete (with timeout)
        if sync_completed.wait(timeout=30):  # 30 second timeout
            if sync_error:
                logger.warning(f"Sync completed with error: {sync_error}")
        else:
            logger.warning("Sync timed out after 30 seconds")
    
    def _trigger_immediate_sync(self):
        """Trigger immediate synchronization in a separate thread"""
        def sync_worker():
            try:
                self.sync_remote_to_local()
                logger.info("Immediate sync completed")
            except Exception as e:
                logger.error(f"Immediate sync failed: {e}")
        
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()
    
    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """Get user data combining local preferences and remote data"""
        try:
            # Get user preferences from local database
            preferences = self.local_db.get_user_preferences(user_id)
            
            # Get user data from remote database
            query = f"SELECT * FROM users WHERE id = {user_id}"
            remote_result = self.remote_db.execute_query(query)
            
            user_data = {}
            if remote_result["success"] and remote_result["data"]:
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
        """Force immediate synchronization"""
        try:
            logger.info("Forcing immediate synchronization...")
            self.sync_remote_to_local()
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
            
            if result["success"]:
                logger.info(f"Cleaned up {result['row_count']} expired cache entries")
                return result["row_count"]
            
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
