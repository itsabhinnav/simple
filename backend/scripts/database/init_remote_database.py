#!/usr/bin/env python3
"""
Initialize Remote Sakura Database with Requirements and Test Cases Tables

This script creates a remote database file with sample requirements and test cases.
The database can then be committed to Git for remote synchronization.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

def create_sakura_database():
    """Create the Sakura database with requirements and test_cases tables"""
    
    # Resolve path relative to backend directory
    backend_dir = Path(__file__).parent.parent.parent
    remote_dir = backend_dir / "data" / "remote" / "dev"
    remote_dir.mkdir(parents=True, exist_ok=True)
    
    # Database file path
    db_path = remote_dir / "database" / "sakura_db.db"
    
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()
        print(f"Removed existing database: {db_path}")
    
    # Create database connection
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    print("Creating Sakura database...")
    
    # Create requirements table
    cursor.execute('''
        CREATE TABLE requirements (
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
    
    # Create test_cases table
    cursor.execute('''
        CREATE TABLE test_cases (
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
            test_type TEXT CHECK(test_type IN ('Positive', 'Negative', 'Boundary', 'Performance', 'Security')),
            region TEXT,
            brand TEXT,
            vehicle_variant TEXT,
            vehicle_specification TEXT,
            env_dependency TEXT,
            requirement_type TEXT CHECK(requirement_type IN ('Functional', 'HMI', 'Safety', 'Performance', 'Usability')),
            regulation TEXT,
            priority TEXT CHECK(priority IN ('P1', 'P2', 'P3', 'P4')),
            testsuite_type TEXT CHECK(testsuite_type IN ('Sanity', 'Smoke', 'Regression', 'Integration', 'System')),
            status TEXT CHECK(status IN ('Draft', 'Review', 'Approved', 'Executed', 'Failed', 'Passed')) DEFAULT 'Draft',
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (associated_requirement_id) REFERENCES requirements(requirement_id)
        )
    ''')
    
    # Insert sample requirements data
    requirements_data = [
        ('REQ_AUTH_001', 'User Authentication', 'System shall authenticate users using username and password', 'Functional', 'P1', 'Approved', 'admin'),
        ('REQ_AUTH_002', 'Password Security', 'Passwords shall meet minimum security requirements', 'Safety', 'P1', 'Approved', 'admin'),
        ('REQ_DASH_001', 'Dashboard Display', 'System shall display user dashboard with relevant information', 'Functional', 'P2', 'Draft', 'admin'),
        ('REQ_HMI_001', 'User Interface', 'Interface shall be intuitive and user-friendly', 'HMI', 'P2', 'Draft', 'admin'),
        ('REQ_PERF_001', 'Response Time', 'System shall respond within 2 seconds for standard operations', 'Performance', 'P3', 'Draft', 'admin')
    ]
    
    cursor.executemany('''
        INSERT INTO requirements (requirement_id, title, description, requirement_type, priority, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', requirements_data)
    
    # Insert sample test cases data
    test_cases_data = [
        ('TC_AUTH_001', 'REQ_AUTH_001', 'Login Screen', 'Authentication', 'Verify user login with valid credentials', 'User has valid account', '1. Enter valid username\n2. Enter valid password\n3. Click Login button', 'User should be logged in successfully', 'Positive', 'Global', 'All', 'All', 'All', 'None', 'Functional', 'None', 'P1', 'Sanity', 'admin'),
        ('TC_AUTH_002', 'REQ_AUTH_001', 'Login Screen', 'Authentication', 'Verify login failure with invalid credentials', 'User has invalid credentials', '1. Enter invalid username\n2. Enter invalid password\n3. Click Login button', 'System should display error message', 'Negative', 'Global', 'All', 'All', 'All', 'None', 'Functional', 'None', 'P1', 'Sanity', 'admin'),
        ('TC_AUTH_003', 'REQ_AUTH_002', 'Password Field', 'Authentication', 'Verify password strength validation', 'User is on registration page', '1. Enter weak password\n2. Click Submit', 'System should show password strength requirements', 'Positive', 'Global', 'All', 'All', 'All', 'None', 'Safety', 'None', 'P1', 'Smoke', 'admin'),
        ('TC_DASH_001', 'REQ_DASH_001', 'Dashboard', 'Dashboard', 'Verify dashboard loads correctly', 'User is logged in', '1. Navigate to dashboard\n2. Verify all elements load', 'Dashboard should display all widgets and data', 'Positive', 'Global', 'All', 'All', 'All', 'None', 'Functional', 'None', 'P2', 'Sanity', 'admin'),
        ('TC_HMI_001', 'REQ_HMI_001', 'Navigation Menu', 'User Interface', 'Verify navigation menu usability', 'User is on main page', '1. Click on menu items\n2. Verify navigation works', 'Menu should be responsive and intuitive', 'Positive', 'Global', 'All', 'All', 'All', 'None', 'HMI', 'None', 'P2', 'Smoke', 'admin')
    ]
    
    cursor.executemany('''
        INSERT INTO test_cases (test_case_id, associated_requirement_id, screen_id, feature, test_objective, preconditions, procedure, expected_behavior, test_type, region, brand, vehicle_variant, vehicle_specification, env_dependency, requirement_type, regulation, priority, testsuite_type, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', test_cases_data)
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print(f"✅ Remote database created successfully: {db_path}")
    print(f"📊 Requirements table: {len(requirements_data)} records")
    print(f"🧪 Test cases table: {len(test_cases_data)} records")
    print(f"\n📝 Next steps:")
    print(f"   1. Review the database at: {db_path}")
    print(f"   2. Commit the database to Git if needed")
    print(f"   3. Push to remote repository to share with the team")
    
    return str(db_path)

if __name__ == "__main__":
    create_sakura_database()
