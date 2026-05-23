import psycopg2
from psycopg2.extras import RealDictCursor
import os
from typing import List, Dict, Any, Optional
from src.infrastructure.configuration_manager import get_config_manager
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class PostgresDatabaseService:
    """Production PostgreSQL database service"""
    
    def __init__(self):
        self.config_manager = get_config_manager()
        
        # Get configuration values
        self.host = os.environ.get("DB_HOST", "localhost")
        self.port = os.environ.get("DB_PORT", "5432")
        self.db_name = os.environ.get("DB_NAME", "sakura_db")
        self.user = os.environ.get("DB_USER", "postgres")
        self.password = os.environ.get("DB_PASSWORD", "postgres")
        
        logger.info(f"PostgreSQL database service initialized for: {self.db_name} at {self.host}")
    
    def _get_connection(self):
        """Create a new database connection"""
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.db_name,
            user=self.user,
            password=self.password
        )

    def initialize(self) -> bool:
        """Initialize the database with required tables"""
        try:
            logger.info("Initializing PostgreSQL database...")
            self.ensure_tables_exist()
            logger.info("PostgreSQL database initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL database: {e}")
            return False
    
    def ensure_tables_exist(self) -> bool:
        """Ensure required database tables exist (compatible with PostgreSQL)"""
        try:
            # Create users table
            create_users_table = """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT,
                    secret_key_hash TEXT,
                    git_token_encrypted TEXT,
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    role VARCHAR(50) DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create test_cases table
            create_test_cases_table = """
                CREATE TABLE IF NOT EXISTS test_cases (
                    id SERIAL PRIMARY KEY,
                    test_case_id VARCHAR(255) UNIQUE NOT NULL,
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
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Create requirements table
            create_requirements_table = """
                CREATE TABLE IF NOT EXISTS requirements (
                    id SERIAL PRIMARY KEY,
                    requirement_id VARCHAR(255) UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    given TEXT,
                    when_action TEXT,
                    then_result TEXT,
                    requirement_type VARCHAR(50),
                    priority VARCHAR(50),
                    status VARCHAR(50) DEFAULT 'Draft',
                    assignee TEXT,
                    tags TEXT,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    version VARCHAR(50) DEFAULT '1.0'
                )
            """
            
            # Create database metadata table
            create_database_metadata_table = """
                CREATE TABLE IF NOT EXISTS database_metadata (
                    id SERIAL PRIMARY KEY,
                    metadata_key VARCHAR(255) UNIQUE NOT NULL,
                    metadata_value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            
            # Execute table creation queries
            self.execute_query(create_users_table)
            self.execute_query(create_test_cases_table)
            self.execute_query(create_requirements_table)
            self.execute_query(create_database_metadata_table)
            
            # Initialize version
            self.execute_query("""
                INSERT INTO database_metadata (metadata_key, metadata_value)
                VALUES ('version', '1')
                ON CONFLICT (metadata_key) DO NOTHING
            """)
            
            return True
        except Exception as e:
            logger.error(f"Failed to ensure PostgreSQL tables: {e}")
            return False

    def execute_query(self, query: str, database_name: str = "default", params: tuple = (), **kwargs) -> Dict[str, Any]:
        """Execute a query on PostgreSQL"""
        conn = None
        try:
            conn = self._get_connection()
            # Use RealDictCursor to mimic sqlite3.Row behavior (dict-like access)
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Convert SQLite specific syntax to PostgreSQL if needed
                # (Simple heuristic for the migration)
                query = query.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
                query = query.replace('DATETIME DEFAULT CURRENT_TIMESTAMP', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
                query = query.replace('INSERT OR IGNORE', 'INSERT') # Manual conflict handling would be better
                query = query.replace('INSERT OR REPLACE', 'INSERT') # Use ON CONFLICT instead for real apps
                
                cursor.execute(query, params)
                
                if query.strip().upper().startswith('SELECT'):
                    data = cursor.fetchall()
                    # Convert RealDict to normal dict for JSON serialization
                    data = [dict(row) for row in data]
                    return {
                        "success": True,
                        "data": data,
                        "row_count": len(data)
                    }
                else:
                    conn.commit()
                    return {
                        "success": True,
                        "row_count": cursor.rowcount,
                        "lastrowid": None # SERIAL doesn't easily return lastrowid like SQLite
                    }
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"PostgreSQL query failed: {e}")
            return {"success": False, "error": str(e), "data": []}
        finally:
            if conn:
                conn.close()
