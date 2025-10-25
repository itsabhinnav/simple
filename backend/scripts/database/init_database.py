#!/usr/bin/env python3
"""
Database Initialization Script

This script initializes the database with the necessary tables and sample data.
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from src.infrastructure.configuration_manager import get_config_manager
from src.services.git_database_service import GitDatabaseService
from src.implementations.git_file_storage import GitFileStorage


def initialize_database():
    """Initialize the database with tables and sample data"""
    print("🗄️ Initializing Sakura Database...")
    
    # Get configuration
    config_manager = get_config_manager()
    
    # Get database configuration
    db_name = config_manager.get_database_name()
    cache_dir = Path(config_manager.get_config("database.cache_directory", "data/cache"))
    data_dir = Path(config_manager.get_config("database.data_directory", "data"))
    
    # Ensure directories exist
    cache_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Database file path
    db_path = cache_dir / f"{db_name}.db"
    
    print(f"📁 Database Path: {db_path}")
    print(f"📊 Database Name: {db_name}")
    
    # Create database connection
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Get table names from configuration
        users_table = config_manager.get_table_name("users")
        test_cases_table = config_manager.get_table_name("test_cases")
        requirements_table = config_manager.get_table_name("requirements")
        
        print(f"📋 Table Names:")
        print(f"  Users: {users_table}")
        print(f"  Test Cases: {test_cases_table}")
        print(f"  Requirements: {requirements_table}")
        
        # Create users table
        print(f"\n👥 Creating {users_table} table...")
        cursor.execute(f'''
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
        ''')
        
        # Create test_cases table
        print(f"🧪 Creating {test_cases_table} table...")
        cursor.execute(f'''
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
        ''')
        
        # Create requirements table
        print(f"📝 Creating {requirements_table} table...")
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {requirements_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requirement_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                requirement_type TEXT CHECK(requirement_type IN ('Functional', 'HMI', 'Safety', 'Performance', 'Usability')),
                priority TEXT CHECK(priority IN ('P1', 'P2', 'P3', 'P4')),
                status TEXT CHECK(status IN ('Draft', 'Approved', 'Implemented', 'Tested', 'Closed')) DEFAULT 'Draft',
                created_by TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                version TEXT DEFAULT '1.0'
            )
        ''')
        
        # Insert sample users
        print(f"\n👤 Inserting sample users...")
        sample_users = [
            ('admin', 'admin@sakura.com', 'Admin', 'User', 'admin'),
            ('testuser1', 'test1@sakura.com', 'Test', 'User1', 'user'),
            ('testuser2', 'test2@sakura.com', 'Test', 'User2', 'user'),
            ('developer', 'dev@sakura.com', 'Developer', 'User', 'developer'),
            ('tester', 'tester@sakura.com', 'Test', 'Engineer', 'tester')
        ]
        
        for user in sample_users:
            cursor.execute(f'''
                INSERT OR IGNORE INTO {users_table} (username, email, first_name, last_name, role) 
                VALUES (?, ?, ?, ?, ?)
            ''', user)
        
        # Insert sample requirements
        print(f"📝 Inserting sample requirements...")
        sample_requirements = [
            ('REQ_AUTH_001', 'User Authentication', 'System shall authenticate users using username and password', 'Functional', 'P1', 'Approved', 'admin'),
            ('REQ_AUTH_002', 'Password Security', 'Passwords shall meet minimum security requirements', 'Safety', 'P1', 'Approved', 'admin'),
            ('REQ_DASH_001', 'Dashboard Display', 'System shall display user dashboard with relevant information', 'Functional', 'P2', 'Draft', 'admin'),
            ('REQ_HMI_001', 'User Interface', 'Interface shall be intuitive and user-friendly', 'HMI', 'P2', 'Draft', 'admin'),
            ('REQ_PERF_001', 'Response Time', 'System shall respond within 2 seconds for standard operations', 'Performance', 'P3', 'Draft', 'admin')
        ]
        
        for req in sample_requirements:
            cursor.execute(f'''
                INSERT OR IGNORE INTO {requirements_table} 
                (requirement_id, title, description, requirement_type, priority, status, created_by) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', req)
        
        # Insert sample test cases
        print(f"🧪 Inserting sample test cases...")
        sample_test_cases = [
            ('TC_AUTH_001', 'REQ_AUTH_001', 'Login Screen', 'Authentication', 'Verify user login with valid credentials', 'User has valid account', '1. Enter valid username\n2. Enter valid password\n3. Click Login button', 'User should be logged in successfully', 'Positive', 'Global', 'All', 'All', 'All', 'None', 'Functional', 'None', 'P1', 'Sanity', 'admin'),
            ('TC_AUTH_002', 'REQ_AUTH_001', 'Login Screen', 'Authentication', 'Verify login failure with invalid credentials', 'User has invalid credentials', '1. Enter invalid username\n2. Enter invalid password\n3. Click Login button', 'System should display error message', 'Negative', 'Global', 'All', 'All', 'All', 'None', 'Functional', 'None', 'P1', 'Sanity', 'admin'),
            ('TC_AUTH_003', 'REQ_AUTH_002', 'Password Field', 'Authentication', 'Verify password strength validation', 'User is on registration page', '1. Enter weak password\n2. Click Submit', 'System should show password strength requirements', 'Positive', 'Global', 'All', 'All', 'All', 'None', 'Safety', 'None', 'P1', 'Smoke', 'admin'),
            ('TC_DASH_001', 'REQ_DASH_001', 'Dashboard', 'Dashboard', 'Verify dashboard loads correctly', 'User is logged in', '1. Navigate to dashboard\n2. Verify all elements load', 'Dashboard should display all widgets and data', 'Positive', 'Global', 'All', 'All', 'All', 'None', 'Functional', 'None', 'P2', 'Sanity', 'admin'),
            ('TC_HMI_001', 'REQ_HMI_001', 'Navigation Menu', 'User Interface', 'Verify navigation menu usability', 'User is on main page', '1. Click on menu items\n2. Verify navigation works', 'Menu should be responsive and intuitive', 'Positive', 'Global', 'All', 'All', 'All', 'None', 'HMI', 'None', 'P2', 'Smoke', 'admin')
        ]
        
        for tc in sample_test_cases:
            cursor.execute(f'''
                INSERT OR IGNORE INTO {test_cases_table} 
                (test_case_id, requirement_id, test_name, feature, description, preconditions, test_steps, expected_result, test_category, test_level, test_environment, test_data, test_priority, test_status, test_execution_type, test_automation_status, test_priority_level, test_suite, created_by) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', tc)
        
        # Commit changes
        conn.commit()
        
        # Verify tables were created
        print(f"\n✅ Database initialization complete!")
        print(f"📊 Database file: {db_path}")
        print(f"📏 File size: {db_path.stat().st_size} bytes")
        
        # Show table counts
        cursor.execute(f"SELECT COUNT(*) FROM {users_table}")
        user_count = cursor.fetchone()[0]
        print(f"👥 Users: {user_count}")
        
        cursor.execute(f"SELECT COUNT(*) FROM {test_cases_table}")
        tc_count = cursor.fetchone()[0]
        print(f"🧪 Test Cases: {tc_count}")
        
        cursor.execute(f"SELECT COUNT(*) FROM {requirements_table}")
        req_count = cursor.fetchone()[0]
        print(f"📝 Requirements: {req_count}")
        
        # Show all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"\n📋 Tables in database:")
        for table in tables:
            print(f"  - {table[0]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        conn.rollback()
        return False
        
    finally:
        cursor.close()
        conn.close()


def main():
    """Main function"""
    print("🚀 Sakura Database Initialization")
    print("=" * 40)
    
    try:
        success = initialize_database()
        
        if success:
            print("\n🎉 Database initialization successful!")
            print("🔗 You can now use the API endpoints:")
            print("  - http://localhost:5000/api/databases")
            print("  - http://localhost:5000/api/users")
            print("  - http://localhost:5000/api/test-cases")
            print("  - http://localhost:5000/api/requirements")
        else:
            print("\n❌ Database initialization failed!")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
