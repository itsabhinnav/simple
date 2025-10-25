import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.interfaces.git_file_storage import IGitFileStorage
from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class GitDatabaseService:
    """Git-based database service for Sakura application"""
    
    def __init__(self, git_storage: IGitFileStorage):
        self.git_storage = git_storage
        self.config_manager = get_config_manager()
        
        # Get configuration values
        self.data_path = Path(self.config_manager.get_config("database.data_directory", "data"))
        self.cache_path = Path(self.config_manager.get_config("database.cache_directory", "data/cache"))
        self.database_name = self.config_manager.get_database_name()
        
        # Ensure directories exist
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.cache_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("Git database service initialized")
    
    def initialize(self) -> bool:
        """Initialize the service by cloning/fetching the repository"""
        try:
            logger.info("Initializing Git database service...")
            
            # Clone or fetch the repository
            if not self.git_storage.clone_or_fetch_repo():
                logger.error("Failed to clone/fetch repository")
                return False
            
            # Copy database files from git repo to data folder
            self._sync_databases_from_git()
            
            # Ensure required tables exist
            self.ensure_tables_exist()
            
            logger.info("Git database service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Git database service: {e}")
            return False
    
    def _sync_databases_from_git(self) -> None:
        """Sync database files from git repository to data folder"""
        try:
            # Get database file name from configuration
            db_filename = self.database_name if self.database_name.endswith('.db') else f"{self.database_name}.db"
            
            # Copy main database file
            if self.git_storage.file_exists(f"database/{db_filename}"):
                # Copy directly to cache path instead of using copy_file_to_data
                source_path = self.git_storage.local_repo_path / f"database/{db_filename}"
                dest_path = self.cache_path / db_filename
                
                # Ensure destination directory exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Only copy if local file doesn't exist or git file is newer
                if not dest_path.exists():
                    import shutil
                    shutil.copy2(source_path, dest_path)
                    logger.info(f"Synced database file: {db_filename}")
                else:
                    # Check if git file is newer than local file
                    import os
                    git_mtime = os.path.getmtime(source_path)
                    local_mtime = os.path.getmtime(dest_path)
                    
                    if git_mtime > local_mtime:
                        import shutil
                        shutil.copy2(source_path, dest_path)
                        logger.info(f"Synced database file (git newer): {db_filename}")
                    else:
                        logger.info(f"Local database file is newer, skipping sync: {db_filename}")
            else:
                logger.warning(f"Database file not found in git repo: database/{db_filename}")
                
        except Exception as e:
            logger.error(f"Failed to sync databases from git: {e}")
    
    def _sync_databases_to_git(self) -> bool:
        """Sync database files from data folder back to git repository"""
        try:
            # Get database file name from configuration
            db_filename = self.database_name if self.database_name.endswith('.db') else f"{self.database_name}.db"
            
            # Copy database file back to git repo
            source_path = self.cache_path / db_filename
            dest_path = self.git_storage.local_repo_path / f"database/{db_filename}"
            
            logger.info(f"Syncing database file: {db_filename}")
            logger.info(f"Source path: {source_path}")
            logger.info(f"Destination path: {dest_path}")
            logger.info(f"Source exists: {source_path.exists()}")
            logger.info(f"Destination parent exists: {dest_path.parent.exists()}")
            
            if source_path.exists():
                # Ensure destination directory exists
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                import shutil
                shutil.copy2(source_path, dest_path)
                logger.info(f"Synced database file back to git: {db_filename}")
                return True
            else:
                logger.warning(f"Database file not found in cache: {source_path}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to sync databases to git: {e}")
            return False
    
    def commit_changes(self, commit_message: str = "Update database") -> bool:
        """Commit database changes to git repository"""
        try:
            # First sync database files back to git repo
            if not self._sync_databases_to_git():
                logger.warning("No database changes to commit")
                return False
            
            # Commit and push changes
            success = self.git_storage.push_changes(commit_message)
            if success:
                logger.info(f"Successfully committed database changes: {commit_message}")
            else:
                logger.error("Failed to commit database changes to git")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to commit changes: {e}")
            return False
    
    def execute_query(self, query: str, database_name: str = "default") -> Dict[str, Any]:
        """Execute a query on the database"""
        try:
            # Get database file path
            db_filename = self.database_name if self.database_name.endswith('.db') else f"{self.database_name}.db"
            db_path = self.cache_path / db_filename
            
            if not db_path.exists():
                logger.error(f"Database file not found: {db_path}")
                return {"error": f"Database file not found: {db_path}", "data": []}
            
            # Connect to database
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            try:
                # Execute query
                cursor.execute(query)
                
                # Handle different query types
                if query.strip().upper().startswith(('SELECT', 'PRAGMA')):
                    # Fetch results for SELECT queries
                    rows = cursor.fetchall()
                    data = [dict(row) for row in rows]
                    result = {"success": True, "data": data, "row_count": len(data)}
                else:
                    # For INSERT, UPDATE, DELETE queries
                    conn.commit()
                    result = {"success": True, "data": [], "row_count": cursor.rowcount, "lastrowid": cursor.lastrowid}
                
                return result
                
            finally:
                cursor.close()
                conn.close()
                
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return {"success": False, "error": str(e), "data": []}
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get database information"""
        try:
            db_filename = self.database_name if self.database_name.endswith('.db') else f"{self.database_name}.db"
            db_path = self.cache_path / db_filename
            
            if not db_path.exists():
                return {"error": "Database file not found"}
            
            # Get file stats
            stat = db_path.stat()
            
            # Get table information
            tables_result = self.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row["name"] for row in tables_result.get("data", [])]
            
            return {
                "database_name": self.database_name,
                "file_path": str(db_path),
                "file_size": stat.st_size,
                "last_modified": stat.st_mtime,
                "tables": tables,
                "table_count": len(tables)
            }
            
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}
    
    def list_databases(self, environment: str = "default") -> List[Dict[str, Any]]:
        """List available databases"""
        try:
            databases = []
            db_files = list(self.cache_path.glob("*.db"))
            
            for db_file in db_files:
                stat = db_file.stat()
                databases.append({
                    "name": db_file.stem,
                    "file_path": str(db_file),
                    "size": stat.st_size,
                    "last_modified": stat.st_mtime,
                    "status": "available"
                })
            
            return databases
        except Exception as e:
            logger.error(f"Failed to list databases: {e}")
            return []
    
    def get_repo_status(self) -> Dict[str, Any]:
        """Get repository status"""
        try:
            return self.git_storage.get_repo_status()
        except Exception as e:
            logger.error(f"Failed to get repo status: {e}")
            return {"error": str(e)}
    
    def ensure_tables_exist(self) -> bool:
        """Ensure required database tables exist"""
        try:
            logger.info("Ensuring database tables exist...")
            
            # Get table names from configuration
            users_table = self.config_manager.get_table_name("users")
            test_cases_table = self.config_manager.get_table_name("test_cases")
            requirements_table = self.config_manager.get_table_name("requirements")
            
            # Create users table if it doesn't exist
            create_users_table = f"""
                CREATE TABLE IF NOT EXISTS {users_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    role TEXT DEFAULT 'user',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create test_cases table if it doesn't exist
            create_test_cases_table = f"""
                CREATE TABLE IF NOT EXISTS {test_cases_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_case_id TEXT UNIQUE NOT NULL,
                    requirement_id TEXT,
                    test_name TEXT NOT NULL,
                    feature TEXT,
                    test_type TEXT,
                    description TEXT,
                    preconditions TEXT,
                    test_steps TEXT,
                    expected_result TEXT,
                    test_category TEXT,
                    test_level TEXT,
                    test_environment TEXT,
                    test_data TEXT,
                    test_priority TEXT,
                    test_status TEXT,
                    test_execution_type TEXT,
                    test_automation_status TEXT,
                    test_priority_level TEXT,
                    test_suite TEXT,
                    created_by TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create requirements table if it doesn't exist
            create_requirements_table = f"""
                CREATE TABLE IF NOT EXISTS {requirements_table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requirement_id TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT,
                    status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Execute table creation queries
            self.execute_query(create_users_table)
            self.execute_query(create_test_cases_table)
            self.execute_query(create_requirements_table)
            
            logger.info("Database tables ensured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure tables exist: {e}")
            return False
    
    def create_sample_data(self) -> bool:
        """Create sample data in the database"""
        try:
            logger.info("Creating sample data...")
            
            # First ensure tables exist
            if not self.ensure_tables_exist():
                logger.error("Failed to ensure tables exist")
                return False
            
            # Get table names from configuration
            users_table = self.config_manager.get_table_name("users")
            test_cases_table = self.config_manager.get_table_name("test_cases")
            
            # Insert sample users
            sample_users = [
                ('admin', 'admin@sakura.com', 'Admin', 'User', 'admin'),
                ('testuser1', 'test1@sakura.com', 'Test', 'User1', 'user'),
                ('testuser2', 'test2@sakura.com', 'Test', 'User2', 'user')
            ]
            
            for user in sample_users:
                insert_user = f"""
                    INSERT OR IGNORE INTO {users_table} (username, email, first_name, last_name, role) VALUES
                    ('{user[0]}', '{user[1]}', '{user[2]}', '{user[3]}', '{user[4]}')
                """
                self.execute_query(insert_user)
            
            logger.info("Sample data created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create sample data: {e}")
            return False