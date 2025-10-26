import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Resolve path relative to backend directory
backend_dir = Path(__file__).parent.parent
db_path = backend_dir / "data" / "local" / "local.db"

if not db_path.exists():
    print(f"Database not found at {db_path}!")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Sample requirements with Given-When-Then format
sample_requirements = [
    {
        'requirement_id': 'REQ-001',
        'title': 'User Authentication',
        'description': 'Users must be able to log in with username and password',
        'given': 'User has valid credentials and is on the login page',
        'when': 'User enters valid username and password and clicks login button',
        'then': 'User is redirected to the dashboard and a session is created',
        'priority': 'P1',
        'status': 'Approved',
        'assignee': 'John Doe',
        'tags': 'authentication, security, login'
    },
    {
        'requirement_id': 'REQ-002',
        'title': 'Password Reset',
        'description': 'Users must be able to reset forgotten passwords',
        'given': 'User has forgotten their password and clicks "Forgot Password"',
        'when': 'User enters username and secret key to verify identity',
        'then': 'User is allowed to set a new password and can log in with new credentials',
        'priority': 'P1',
        'status': 'Tested',
        'assignee': 'Jane Smith',
        'tags': 'password, recovery, security'
    },
    {
        'requirement_id': 'REQ-003',
        'title': 'Create Requirement',
        'description': 'Users must be able to create new requirements with Given-When-Then format',
        'given': 'User is logged in and navigates to Requirements page',
        'when': 'User fills in requirement details (Given, When, Then) and submits',
        'then': 'Requirement is created and displayed in the requirements list',
        'priority': 'P1',
        'status': 'Implemented',
        'assignee': 'Mike Johnson',
        'tags': 'requirements, CRUD, functionality'
    },
    {
        'requirement_id': 'REQ-004',
        'title': 'Filter Requirements',
        'description': 'Users must be able to filter requirements by status, priority, and assignee',
        'given': 'User is on the Requirements page with multiple requirements',
        'when': 'User selects filter options (status/priority/assignee) from dropdowns',
        'then': 'Only requirements matching the selected filters are displayed',
        'priority': 'P2',
        'status': 'Approved',
        'assignee': 'Sarah Williams',
        'tags': 'filtering, search, UX'
    },
    {
        'requirement_id': 'REQ-005',
        'title': 'Git Integration',
        'description': 'Database changes must be synchronized with remote Git repository',
        'given': 'User creates, updates, or deletes a requirement in the local database',
        'when': 'The operation completes successfully',
        'then': 'Changes are automatically committed to Git with an informative message and pushed to remote',
        'priority': 'P1',
        'status': 'Tested',
        'assignee': 'Alex Brown',
        'tags': 'git, sync, version-control'
    },
    {
        'requirement_id': 'REQ-006',
        'title': 'Requirement Cards Display',
        'description': 'Requirements must be displayed in a JIRA-like card format',
        'given': 'User navigates to the Requirements page',
        'when': 'Requirements are loaded from the database',
        'then': 'Each requirement is displayed as a card showing title, status, priority, and Given-When-Then sections',
        'priority': 'P2',
        'status': 'Tested',
        'assignee': 'Emma Davis',
        'tags': 'UI, design, cards'
    },
    {
        'requirement_id': 'REQ-007',
        'title': 'Search Requirements',
        'description': 'Users must be able to search requirements by title, ID, or description',
        'given': 'User is on the Requirements page',
        'when': 'User types text into the search box',
        'then': 'Requirements matching the search term are filtered and displayed in real-time',
        'priority': 'P2',
        'status': 'Approved',
        'assignee': 'Tom Wilson',
        'tags': 'search, filtering, UX'
    },
    {
        'requirement_id': 'REQ-008',
        'title': 'Edit Requirement',
        'description': 'Users must be able to edit existing requirements',
        'given': 'User is viewing the Requirements page',
        'when': 'User clicks the edit button on a requirement card',
        'then': 'A modal opens with the requirement details pre-filled, allowing modifications',
        'priority': 'P1',
        'status': 'Approved',
        'assignee': 'Lisa Anderson',
        'tags': 'CRUD, editing, modal'
    }
]

try:
    print("Creating sample requirements...\n")
    
    for req in sample_requirements:
        # Check if requirement already exists
        cursor.execute(
            "SELECT id FROM requirements WHERE requirement_id = ?",
            (req['requirement_id'],)
        )
        existing = cursor.fetchone()
        
        if existing:
            print(f"  Requirement {req['requirement_id']} already exists, skipping...")
        else:
            cursor.execute("""
                INSERT INTO requirements 
                (requirement_id, title, description, given, when_action, then_result, 
                 priority, status, assignee, tags, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                req['requirement_id'],
                req['title'],
                req['description'],
                req['given'],
                req['when'],
                req['then'],
                req['priority'],
                req['status'],
                req['assignee'],
                req['tags'],
                'system',
                datetime.now(),
                datetime.now()
            ))
            print(f"✓ Created requirement: {req['requirement_id']} - {req['title']}")
    
    conn.commit()
    print("\n✓ Sample requirements created successfully!")
    
    # Count requirements
    cursor.execute("SELECT COUNT(*) FROM requirements")
    count = cursor.fetchone()[0]
    print(f"  Total requirements in database: {count}")
    
except Exception as e:
    print(f"Error: {e}")
    conn.rollback()
finally:
    conn.close()

