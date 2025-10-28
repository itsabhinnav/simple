#!/usr/bin/env python3
"""
Script to link requirements to designs (bi-directional)
Updates requirements table with design_ticket_id field
"""
import sys
from pathlib import Path
import sqlite3

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def link_requirements_to_designs():
    """Link requirements to their associated designs"""
    db_path = Path(__file__).parent.parent / "data" / "local" / "dev" / "database" / "sakura_db.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return False
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Get all designs grouped by linked requirement
        cursor.execute("""
            SELECT linked_requirement_id, GROUP_CONCAT(design_ticket_id) as design_ids
            FROM design_tickets
            WHERE linked_requirement_id IS NOT NULL AND linked_requirement_id != ''
            GROUP BY linked_requirement_id
        """)
        
        design_groups = cursor.fetchall()
        print(f"Found {len(design_groups)} requirement groups with designs")
        
        updated_count = 0
        
        for req_id, design_ids in design_groups:
            try:
                # Escape single quotes in requirement ID
                req_id_escaped = str(req_id).replace("'", "''")
                
                # Update requirement with design IDs
                query = f"""
                    UPDATE requirements 
                    SET design_ticket_id = '{design_ids}'
                    WHERE requirement_id = '{req_id_escaped}'
                """
                
                cursor.execute(query)
                updated_count += 1
                
                if updated_count % 50 == 0:
                    print(f"Updated {updated_count} requirements...")
                    
            except Exception as e:
                print(f"Error updating requirement {req_id}: {e}")
                continue
        
        conn.commit()
        print(f"\n✓ Successfully linked {updated_count} requirements to designs")
        
        # Verify the links
        cursor.execute("""
            SELECT COUNT(*) FROM requirements 
            WHERE design_ticket_id IS NOT NULL AND design_ticket_id != ''
        """)
        linked_count = cursor.fetchone()[0]
        print(f"✓ Total linked requirements: {linked_count}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Linking Requirements to Designs")
    print("=" * 60)
    success = link_requirements_to_designs()
    sys.exit(0 if success else 1)

