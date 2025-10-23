import sqlite3
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.interfaces.git_file_storage import IGitFileStorage
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class GitDatabaseService:
    """Git-based database service for Sakura application"""
    
    def __init__(self, git_storage: IGitFileStorage):
        self.git_storage = git_storage
        self.data_path = Path("data")
        self.data_path.mkdir(exist_ok=True)
        
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
            
            logger.info("Git database service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Git database service: {e}")
            return False
    
    def _sync_databases_from_git(self) -> None:
        """Sync database files from git repository to local data folder"""
        try:
            # List all .db files in the repository (including subdirectories)
            db_files = self.git_storage.list_files("**/*.db")
            
            for db_file in db_files:
                # Copy to data folder with same name
                dest_file = Path(db_file).name
                if self.git_storage.copy_file_to_data(db_file, dest_file):
                    logger.info(f"Synced database file: {db_file} -> {dest_file}")
                else:
                    logger.warning(f"Failed to sync database file: {db_file}")
            
            # If no .db files found, create a default one
            if not db_files:
                logger.info("No database files found in repository, creating default database")
                self._create_default_database()
                
        except Exception as e:
            logger.error(f"Failed to sync databases from git: {e}")
    
    def _create_default_database(self) -> None:
        """Create a default database if none exists"""
        try:
            default_db_path = self.data_path / "enhanced_sample_db.db"
            
            # Create database with basic tables
            conn = sqlite3.connect(default_db_path)
            cursor = conn.cursor()
            
            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    role TEXT DEFAULT 'user',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create test_cases table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_case_id TEXT UNIQUE NOT NULL,
                    reference_document TEXT,
                    associated_requirement_id TEXT,
                    screen_id TEXT,
                    feature TEXT,
                    dr_applicable_screens TEXT,
                    dr_id TEXT,
                    test_objective TEXT,
                    preconditions TEXT,
                    procedure TEXT,
                    expected_behavior TEXT,
                    test_type TEXT,
                    region TEXT,
                    brand TEXT,
                    vehicle_variant TEXT,
                    vehicle_specification TEXT,
                    env_dependency TEXT,
                    requirement_type TEXT,
                    regulation TEXT,
                    priority TEXT,
                    testsuite_type TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert sample data
            cursor.execute('''
                INSERT OR IGNORE INTO users (username, email, first_name, last_name, role) VALUES
                ('admin', 'admin@sakura.com', 'Admin', 'User', 'admin'),
                ('testuser1', 'test1@sakura.com', 'Test', 'User1', 'user'),
                ('testuser2', 'test2@sakura.com', 'Test', 'User2', 'user')
            ''')
            
            cursor.execute('''
                INSERT OR IGNORE INTO test_cases (test_case_id, feature, test_objective, priority) VALUES
                ('TC_AUTH_001', 'Authentication', 'Verify user login functionality', 'P1'),
                ('TC_AUTH_002', 'Authentication', 'Verify user logout functionality', 'P2'),
                ('TC_DASH_001', 'Dashboard', 'Verify dashboard data display', 'P1')
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info(f"Created default database: {default_db_path}")
            
        except Exception as e:
            logger.error(f"Failed to create default database: {e}")
    
    def list_databases(self, environment: str = "default") -> List[str]:
        """List available database files"""
        try:
            db_files = []
            for file_path in self.data_path.glob("*.db"):
                db_files.append(file_path.stem)
            
            logger.info(f"Found {len(db_files)} database files")
            return db_files
            
        except Exception as e:
            logger.error(f"Failed to list databases: {e}")
            return []
    
    def get_database_info(self, database_name: str, environment: str = "default") -> Dict[str, Any]:
        """Get information about a specific database"""
        try:
            db_path = self.data_path / f"{database_name}.db"
            
            if not db_path.exists():
                raise FileNotFoundError(f"Database {database_name} not found")
            
            # Get file info
            stat = db_path.stat()
            
            # Get database info
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Get row counts for each table
            row_counts = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_counts[table] = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "name": database_name,
                "size": stat.st_size,
                "last_modified": stat.st_mtime,
                "tables": tables,
                "row_counts": row_counts
            }
            
        except Exception as e:
            logger.error(f"Failed to get database info for {database_name}: {e}")
            raise
    
    def sync_database(self, database_name: str, environment: str = "default") -> Dict[str, Any]:
        """Sync database with git repository"""
        try:
            logger.info(f"Syncing database {database_name} with git repository")
            
            # Copy database file to git repo
            db_file = f"{database_name}.db"
            if self.git_storage.copy_file_from_data(db_file, db_file):
                logger.info(f"Copied {db_file} to git repository")
                
                # Push changes to remote
                if self.git_storage.push_changes(f"Update {db_file}"):
                    logger.info(f"Pushed {db_file} to remote repository")
                    return {
                        "success": True,
                        "message": f"Database {database_name} synced successfully"
                    }
                else:
                    logger.error(f"Failed to push {db_file} to remote")
                    return {
                        "success": False,
                        "message": f"Failed to push {db_file} to remote repository"
                    }
            else:
                logger.error(f"Failed to copy {db_file} to git repository")
                return {
                    "success": False,
                    "message": f"Failed to copy {db_file} to git repository"
                }
                
        except Exception as e:
            logger.error(f"Failed to sync database {database_name}: {e}")
            return {
                "success": False,
                "message": f"Failed to sync database {database_name}: {str(e)}"
            }
    
    def execute_query(self, query: str, environment: str = "default") -> Dict[str, Any]:
        """Execute a SQL query on the database"""
        try:
            # Use the first available database file
            db_files = list(self.data_path.glob("*.db"))
            if not db_files:
                raise FileNotFoundError("No database files found in data directory")
            
            # Use the first database file
            db_path = db_files[0]
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Execute query
            cursor.execute(query)
            
            # Get results
            if query.strip().upper().startswith('SELECT'):
                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                
                result = {
                    "columns": columns,
                    "data": [dict(zip(columns, row)) for row in rows],
                    "row_count": len(rows)
                }
            else:
                conn.commit()
                result = {
                    "message": "Query executed successfully",
                    "affected_rows": cursor.rowcount
                }
            
            conn.close()
            
            logger.info(f"Query executed successfully: {query[:50]}...")
            return result
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def get_repo_status(self) -> Dict[str, Any]:
        """Get git repository status"""
        return self.git_storage.get_repo_status()
    
    def pull_latest_changes(self) -> bool:
        """Pull latest changes from git repository"""
        try:
            logger.info("Pulling latest changes from git repository")
            
            if self.git_storage.clone_or_fetch_repo():
                self._sync_databases_from_git()
                logger.info("Successfully pulled latest changes")
                return True
            else:
                logger.error("Failed to pull latest changes")
                return False
                
        except Exception as e:
            logger.error(f"Failed to pull latest changes: {e}")
            return False
