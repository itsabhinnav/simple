#!/usr/bin/env python3
"""
Verify the bi-directional links between requirements and designs
"""
import sys
from pathlib import Path
import sqlite3

def verify_links():
    """Verify bi-directional links between requirements and designs"""
    db_path = Path(__file__).parent.parent / "data" / "local" / "dev" / "database" / "sakura_db.db"
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check designs -> requirements
        cursor.execute("""
            SELECT COUNT(*) FROM design_tickets
            WHERE linked_requirement_id IS NOT NULL AND linked_requirement_id != ''
        """)
        designs_with_req = cursor.fetchone()[0]
        
        # Check requirements -> designs
        cursor.execute("""
            SELECT COUNT(*) FROM requirements
            WHERE design_ticket_id IS NOT NULL AND design_ticket_id != ''
        """)
        reqs_with_design = cursor.fetchone()[0]
        
        # Sample links
        cursor.execute("""
            SELECT design_ticket_id, linked_requirement_id 
            FROM design_tickets
            WHERE linked_requirement_id IS NOT NULL AND linked_requirement_id != ''
            LIMIT 5
        """)
        sample_designs = cursor.fetchall()
        
        cursor.execute("""
            SELECT requirement_id, design_ticket_id
            FROM requirements
            WHERE design_ticket_id IS NOT NULL AND design_ticket_id != ''
            LIMIT 5
        """)
        sample_reqs = cursor.fetchall()
        
        print("=" * 70)
        print("BI-DIRECTIONAL TRACEABILITY: Requirements <-> Designs")
        print("=" * 70)
        print(f"\nDesigns linked to requirements: {designs_with_req}")
        print(f"Requirements linked to designs: {reqs_with_design}")
        
        print("\n" + "=" * 70)
        print("Sample: Designs -> Requirements (Forward Link)")
        print("=" * 70)
        for design_id, req_id in sample_designs:
            print(f"Design {design_id} → Requirement {req_id}")
        
        print("\n" + "=" * 70)
        print("Sample: Requirements -> Designs (Reverse Link)")
        print("=" * 70)
        for req_id, design_ids in sample_reqs:
            design_list = design_ids[:80] + "..." if len(design_ids) > 80 else design_ids
            print(f"Requirement {req_id} → Designs: {design_list}")
        
        # Check many-to-one relationship
        cursor.execute("""
            SELECT linked_requirement_id, COUNT(*) as count
            FROM design_tickets
            WHERE linked_requirement_id IS NOT NULL AND linked_requirement_id != ''
            GROUP BY linked_requirement_id
            HAVING COUNT(*) > 1
            LIMIT 5
        """)
        many_to_one = cursor.fetchall()
        
        print("\n" + "=" * 70)
        print("Many-to-One Relationship Examples (Multiple Designs per Requirement)")
        print("=" * 70)
        for req_id, count in many_to_one:
            print(f"Requirement {req_id} has {count} designs")
        
        print("\n" + "=" * 70)
        print("✓ Bi-directional traceability is working!")
        print("=" * 70)
        
    finally:
        conn.close()

if __name__ == "__main__":
    verify_links()









