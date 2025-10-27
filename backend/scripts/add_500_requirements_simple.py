#!/usr/bin/env python3
"""
Simple script to add 500 requirements and link test cases - direct database access
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import sqlite3
from pathlib import Path

def create_requirement_id(index: int, prefix: str = "REQ") -> str:
    """Generate a unique requirement ID"""
    return f"{prefix}_{index:04d}"


def main():
    """Main execution function"""
    
    # Connect to local database
    db_path = Path(__file__).parent.parent / "data" / "local" / "dev" / "database" / "sakura_db.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return 1
    
    print(f"📂 Connecting to database: {db_path}")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Step 1: Create 500 requirements
        print("\n📋 Creating 500 requirements...")
        
        priorities = ["P1", "P2", "P3"]
        statuses = ["Draft", "Approved", "Implemented", "Tested"]
        requirement_types = ["Functional", "Non-Functional", "Performance", "Security", "Usability"]
        
        created_count = 0
        for i in range(1, 501):
            req_id = create_requirement_id(i)
            
            priority = priorities[i % len(priorities)]
            status = statuses[i % len(statuses)]
            req_type = requirement_types[i % len(requirement_types)]
            
            try:
                cursor.execute("""
                    INSERT INTO requirements 
                    (requirement_id, title, description, given, when_action, then_result, 
                     priority, status, assignee, tags, requirement_type, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    req_id,
                    f"Requirement {req_id} - {req_type} Feature",
                    f"This is requirement {req_id} for a {req_type.lower()} feature. "
                    f"It describes the expected behavior and acceptance criteria for the system.",
                    f"Given the system is operational",
                    f"When user performs action {i}",
                    f"Then the system should respond correctly to requirement {i}",
                    priority,
                    status,
                    f"Developer{(i % 10) + 1}",
                    f"{req_type}, {priority}, {status}",
                    req_type,
                    "system"
                ))
                created_count += 1
                
                if i % 50 == 0:
                    print(f"  ✓ Created {i} requirements...")
                    
            except sqlite3.IntegrityError as e:
                # Requirement already exists, skip
                continue
            except Exception as e:
                print(f"  ⚠ Warning creating requirement {req_id}: {e}")
        
        conn.commit()
        print(f"\n✅ Successfully created {created_count} requirements")
        
        # Step 2: Link test cases to requirements
        print("\n🔗 Linking test cases to requirements...")
        
        # Get all requirements
        cursor.execute("SELECT id, requirement_id FROM requirements ORDER BY id")
        requirements = cursor.fetchall()
        
        if not requirements:
            print("  ⚠ No requirements found to link")
            return 1
        
        # Get all test cases
        cursor.execute("SELECT test_case_id, id FROM test_cases")
        test_cases = cursor.fetchall()
        
        if not test_cases:
            print("  ⚠ No test cases found")
            return 1
        
        print(f"  📊 Found {len(test_cases)} test cases and {len(requirements)} requirements")
        
        # Link test cases to requirements
        linked_count = 0
        for i, (tc_id, tc_db_id) in enumerate(test_cases):
            # Distribute test cases evenly across requirements
            req_index = i % len(requirements)
            req_db_id, req_id = requirements[req_index]
            
            try:
                cursor.execute("""
                    UPDATE test_cases 
                    SET associated_requirement_id = ?
                    WHERE test_case_id = ?
                """, (req_id, tc_id))
                linked_count += 1
                
                if (i + 1) % 500 == 0:
                    print(f"  ✓ Linked {i + 1} test cases...")
                    
            except Exception as e:
                print(f"  ⚠ Warning linking test case {tc_id}: {e}")
        
        conn.commit()
        print(f"\n✅ Successfully linked {linked_count} test cases to requirements")
        
        # Summary
        cursor.execute("SELECT COUNT(*) FROM requirements")
        total_reqs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM test_cases WHERE associated_requirement_id IS NOT NULL")
        linked_tcs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM test_cases")
        total_tcs = cursor.fetchone()[0]
        
        print("\n" + "="*60)
        print("📊 SUMMARY")
        print("="*60)
        print(f"Requirements in database: {total_reqs}")
        print(f"Test cases in database: {total_tcs}")
        print(f"Linked test cases: {linked_tcs}")
        print(f"Link coverage: {linked_tcs/total_tcs*100:.1f}%" if total_tcs > 0 else "N/A")
        print("="*60)
        
        print("\n✅ Process completed successfully!")
        print("   You can now view requirements and test cases with full traceability.")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        conn.close()


if __name__ == "__main__":
    exit(main())

