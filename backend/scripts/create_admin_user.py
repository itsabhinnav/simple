#!/usr/bin/env python3
"""
Create default admin user for Sakura
Run this script to create an admin user in the database
"""

import os
import sys
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash
import base64

def create_admin_user():
    """Create admin user in the database"""
    
    # Resolve path relative to script location
    backend_dir = Path(__file__).parent.parent
    db_path = backend_dir / "data" / "local" / "local.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}. Please run the application first to initialize the database.")
        return False
    
    # Admin credentials (you can change these)
    username = "admin"
    email = "admin@sakura.com"
    password = "admin123"  # CHANGE THIS IN PRODUCTION!
    secret_key = "sakura_admin_secret_key_2024"
    git_token = f"admin_gitlab_token_for_{username}"  # Use real token in production
    
    # Hash passwords
    password_hash = generate_password_hash(password)
    secret_key_hash = generate_password_hash(secret_key)
    
    # Encrypt Git token
    git_token_encrypted = base64.b64encode(git_token.encode('utf-8')).decode('utf-8')
    
    # Connect to database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if admin user already exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"Admin user '{username}' already exists!")
            answer = input("Do you want to update the password? (y/n): ")
            if answer.lower() == 'y':
                cursor.execute(
                    """
                    UPDATE users 
                    SET password_hash = ?, 
                        secret_key_hash = ?,
                        git_token_encrypted = ?,
                        role = 'admin',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE username = ?
                    """,
                    (password_hash, secret_key_hash, git_token_encrypted, username)
                )
                conn.commit()
                print(f"✓ Admin user '{username}' password updated!")
            else:
                print("Skipped password update.")
            return True
        
        # Create admin user
        cursor.execute(
            """
            INSERT INTO users 
            (username, email, password_hash, secret_key_hash, git_token_encrypted, role, first_name, last_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, email, password_hash, secret_key_hash, git_token_encrypted, 'admin', 'System', 'Administrator')
        )
        conn.commit()
        
        print("="*60)
        print("  Admin user created successfully!")
        print("="*60)
        print(f"\nUsername: {username}")
        print(f"Email: {email}")
        print(f"Password: {password}")
        print(f"Role: admin")
        print("\n⚠ WARNING: Please change the password after first login!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  Sakura - Create Admin User")
    print("="*60 + "\n")
    
    success = create_admin_user()
    
    if success:
        print("\n✓ Setup complete!")
        print("\nYou can now login with:")
        print("  Username: admin")
        print("  Password: admin123\n")
    else:
        print("\n❌ Setup failed!\n")
        sys.exit(1)

