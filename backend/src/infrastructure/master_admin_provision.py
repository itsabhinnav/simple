"""
Master Admin Account Provisioning

This module provides functionality to automatically create a master admin account
on application startup if it doesn't exist. The master admin account has:
- Username: admin
- Password: admin
- Role: admin
"""

from werkzeug.security import generate_password_hash
import base64
from src.infrastructure.logging_config import get_logger
from src.infrastructure.dependency_injection import get_user_service, get_local_database_service

logger = get_logger(__name__)

# Master admin credentials
MASTER_ADMIN_USERNAME = "admin"
MASTER_ADMIN_PASSWORD = "admin"
MASTER_ADMIN_EMAIL = "admin@sakura.com"
MASTER_ADMIN_FIRST_NAME = "System"
MASTER_ADMIN_LAST_NAME = "Administrator"
MASTER_ADMIN_ROLE = "admin"
MASTER_ADMIN_SECRET_KEY = "sakura_master_admin_secret_2024"
MASTER_ADMIN_GIT_TOKEN = "master_admin_gitlab_token_placeholder"  # Placeholder token


def provision_master_admin():
    """
    Provision the master admin account if it doesn't exist.
    This function is called during application startup to ensure
    the master admin account is always available.
    
    Returns:
        bool: True if admin was created or already exists, False on error
    """
    try:
        logger.info("Checking for master admin account...")
        
        # Get user service to check if admin exists
        user_service = get_user_service()
        
        # Check if admin user already exists
        existing_admin = user_service.user_repository.find_by_username(MASTER_ADMIN_USERNAME)
        
        if existing_admin:
            logger.info(f"Master admin account '{MASTER_ADMIN_USERNAME}' already exists")
            return True
        
        # Admin doesn't exist, create it
        logger.info(f"Creating master admin account '{MASTER_ADMIN_USERNAME}'...")
        
        # Get local database service for direct database access
        local_db_service = get_local_database_service()
        
        # Hash password and secret key
        password_hash = generate_password_hash(MASTER_ADMIN_PASSWORD)
        secret_key_hash = generate_password_hash(MASTER_ADMIN_SECRET_KEY)
        
        # Encrypt Git token (base64 encoding)
        git_token_encrypted = base64.b64encode(
            MASTER_ADMIN_GIT_TOKEN.encode('utf-8')
        ).decode('utf-8')
        
        # Escape values to prevent SQL injection
        def escape_sql_string(value):
            """Escape SQL string to prevent injection"""
            if value is None:
                return "''"
            escaped = str(value).replace("'", "''")
            return f"'{escaped}'"
        
        # Build INSERT query
        query = f"""
            INSERT INTO users 
            (username, email, password_hash, secret_key_hash, git_token_encrypted, 
             first_name, last_name, role)
            VALUES (
                {escape_sql_string(MASTER_ADMIN_USERNAME)},
                {escape_sql_string(MASTER_ADMIN_EMAIL)},
                {escape_sql_string(password_hash)},
                {escape_sql_string(secret_key_hash)},
                {escape_sql_string(git_token_encrypted)},
                {escape_sql_string(MASTER_ADMIN_FIRST_NAME)},
                {escape_sql_string(MASTER_ADMIN_LAST_NAME)},
                {escape_sql_string(MASTER_ADMIN_ROLE)}
            )
        """
        
        # Execute query
        result = local_db_service.execute_query(query, "default")
        
        if result.get("success"):
            logger.info(f"✓ Master admin account '{MASTER_ADMIN_USERNAME}' created successfully")
            logger.info(f"  Username: {MASTER_ADMIN_USERNAME}")
            logger.info(f"  Password: {MASTER_ADMIN_PASSWORD}")
            logger.info(f"  Role: {MASTER_ADMIN_ROLE}")
            logger.warning("  ⚠ WARNING: Please change the default password after first login!")
            return True
        else:
            error_msg = result.get('error', 'Unknown error')
            # Check if error is due to table not existing (shouldn't happen, but handle gracefully)
            if "no such table" in str(error_msg).lower() or "does not exist" in str(error_msg).lower():
                logger.warning(f"Users table may not exist yet. Master admin will be created after database initialization.")
                return False
            logger.error(f"Failed to create master admin account: {error_msg}")
            return False
            
    except Exception as e:
        logger.error(f"Error provisioning master admin account: {str(e)}")
        logger.exception(e)
        return False

