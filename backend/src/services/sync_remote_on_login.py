"""
Trigger remote database sync when user logs in with a Git token
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from src.infrastructure.logging_config import get_logger
import shutil

logger = get_logger(__name__)


def sync_remote_database(username: str, git_token: str, repo_url: str, local_repo_path: str) -> bool:
    """
    Fetch and sync remote database for a user who just logged in with their Git token.
    
    This happens after:
    1. User creates account with Git token
    2. User logs in for the first time
    3. User database operations trigger remote sync
    
    Args:
        username: Username of the logged-in user
        git_token: User's Git access token
        repo_url: Remote repository URL
        local_repo_path: Path to local repository
    
    Returns:
        bool: True if sync successful, False otherwise
    """
    try:
        logger.info(f"Starting remote database sync for user: {username}")
        
        local_repo = Path(local_repo_path)
        local_repo.mkdir(parents=True, exist_ok=True)
        
        # Check if repository exists
        if not (local_repo / ".git").exists():
            logger.info("Repository not initialized, cloning...")
            # Clone the repository
            clone_url = repo_url
            if git_token:
                # Use token for authentication
                clone_url = repo_url.replace("https://", f"https://oauth2:{git_token}@")
            
            result = subprocess.run(
                ["git", "clone", clone_url, str(local_repo)],
                capture_output=True,
                text=True,
                cwd=local_repo.parent
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to clone repository: {result.stderr}")
                return False
            
            logger.info("Repository cloned successfully")
        
        # Pull latest changes
        logger.info("Fetching latest changes from remote...")
        env = os.environ.copy()
        env['GIT_ASKPASS'] = 'echo'
        env['GIT_TERMINAL_PROMPT'] = '0'
        
        # Set up git remote with credentials
        if git_token:
            remote_url = repo_url.replace("https://", f"https://oauth2:{git_token}@")
            
            # Update remote URL
            subprocess.run(
                ["git", "remote", "set-url", "origin", remote_url],
                cwd=local_repo,
                capture_output=True,
                text=True
            )
        
        # Fetch and pull
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=local_repo,
            capture_output=True,
            text=True,
            env=env
        )
        
        if result.returncode == 0:
            logger.info("✓ Remote database synced successfully")
            
            # Copy database files from remote to sakura_db.db
            db_files = list(local_repo.glob("database/*.db"))
            # Resolve path relative to backend directory to avoid nested data folders
            backend_dir = Path(__file__).parent.parent.parent
            local_db_path = backend_dir / "data" / "local" / "dev" / "database"
            local_db_path.mkdir(parents=True, exist_ok=True)
            
            for db_file in db_files:
                # Always sync to sakura_db.db
                dest = local_db_path / "sakura_db.db"
                shutil.copy2(db_file, dest)
                logger.info(f"Synced: {db_file.name} -> sakura_db.db")
            
            return True
        else:
            logger.warning(f"Git pull had issues: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to sync remote database: {e}")
        return False


def get_user_git_token_from_db(username: str) -> Optional[str]:
    """Retrieve and decrypt user's Git token from database"""
    try:
        import sqlite3
        import base64
        
        # Resolve path relative to backend directory to avoid nested data folders
        backend_dir = Path(__file__).parent.parent.parent
        db_path = backend_dir / "data" / "local" / "dev" / "database" / "sakura_db.db"
        if not db_path.exists():
            logger.warning("Database not found")
            return None
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        cursor.execute("SELECT git_token_encrypted FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row and row[0]:
            # Decrypt the base64 encoded token
            encrypted_token = row[0]
            git_token = base64.b64decode(encrypted_token.encode('utf-8')).decode('utf-8')
            return git_token
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get Git token: {e}")
        return None


def should_sync_remote(username: str) -> bool:
    """
    Determine if remote database should be synced.
    This is true if:
    - User has a Git token
    - Remote repository exists
    - Local database is empty or outdated
    """
    try:
        # Check if user has a Git token
        git_token = get_user_git_token_from_db(username)
        if not git_token:
            logger.info(f"User {username} has no Git token, skipping remote sync")
            return False
        
        # Check if local database exists and has data
        # Resolve path relative to backend directory to avoid nested data folders
        backend_dir = Path(__file__).parent.parent.parent
        db_path = backend_dir / "data" / "local" / "dev" / "database" / "sakura_db.db"
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Check if users table has more than just the current user
            cursor.execute("SELECT COUNT(*) FROM users WHERE username != ?", (username,))
            count = cursor.fetchone()[0]
            
            conn.close()
            
            # If there are other users, assume remote is already synced
            if count > 0:
                logger.info("Remote database appears to be synced already")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking sync requirement: {e}")
        return False

