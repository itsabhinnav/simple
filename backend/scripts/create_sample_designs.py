#!/usr/bin/env python3
"""
Script to create 300 sample design tickets and link them to requirements
Multiple requirements can link to the same design (many-to-one relationship)
"""
import os
import sys
import random
import string
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from src.infrastructure.dependency_injection import get_hybrid_database_service
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)

# Sample data for design generation
DESIGN_TYPES = [
    "Sequence Diagram",
    "Use Case Diagram",
    "State Flow Diagram",
    "Architecture Diagram",
    "ER Diagram",
    "Flowchart",
    "Wireframe",
    "Mockup",
    "Component Diagram",
    "Deployment Diagram"
]

DIAGRAM_TYPES = [
    "Sequence Diagram",
    "Use Case Diagram",
    "State Machine",
    "Activity Diagram",
    "Class Diagram",
    "Component Diagram",
    "Deployment Diagram",
    "ER Diagram",
    "Network Diagram",
    "User Flow",
    "Mockup",
    "Wireframe",
    "Prototype",
    "Concept Art",
    "Technical Drawing"
]

STATUSES = ["Draft", "Review", "Approved", "Archived", "In Progress"]
PRIORITIES = ["P1", "P2", "P3", "P4"]
ASSIGNEES = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Henry"]

DESIGN_PREFIXES = ["DES", "DGN", "DSN", "ARC"]

DESCRIPTIONS = [
    "High-level architecture design for the user authentication module",
    "Sequence diagram showing the interaction between API and database",
    "State flow for the shopping cart checkout process",
    "Database schema design for the user profile system",
    "Component interaction diagram for the payment gateway integration",
    "Use case diagram for the reporting functionality",
    "Deployment architecture for the production environment",
    "Network topology for the hybrid cloud setup",
    "ER diagram for the inventory management system",
    "Wireframe for the mobile app login screen"
]

TITLES = [
    "Authentication Flow Design",
    "Database Schema for User Management",
    "API Integration Sequence",
    "Payment Gateway Architecture",
    "User Interface Mockup",
    "System State Flow Diagram",
    "Cloud Deployment Design",
    "Component Interaction Map",
    "Network Topology Diagram",
    "User Journey Wireframe"
]

def generate_design_id(index: int) -> str:
    """Generate a unique design ID"""
    prefix = random.choice(DESIGN_PREFIXES)
    return f"{prefix}-{index:04d}"

def create_sample_designs(count: int = 300):
    """Create 300 sample designs"""
    database_service = get_hybrid_database_service()
    
    logger.info(f"Creating {count} sample designs...")
    
    # Get all existing requirements
    try:
        result = database_service.execute_query(
            "SELECT requirement_id, id FROM requirements ORDER BY id",
            "default"
        )
        requirements = result.get('data', [])
        logger.info(f"Found {len(requirements)} requirements to link to")
    except Exception as e:
        logger.error(f"Failed to fetch requirements: {e}")
        return
    
    if not requirements:
        logger.error("No requirements found. Please create requirements first.")
        return
    
    created_count = 0
    
    for i in range(1, count + 1):
        try:
            # Generate design data
            design_id = generate_design_id(i)
            title = random.choice(TITLES) + f" {i}"
            description = random.choice(DESCRIPTIONS)
            design_type = random.choice(DESIGN_TYPES)
            diagram_type = random.choice(DIAGRAM_TYPES)
            
            # Image URL placeholder
            image_url = f"/data/local/dev/images/{design_id.lower()}.png"
            
            # Link to a random requirement (many requirements can link to same design)
            linked_req = random.choice(requirements)
            requirement_id = linked_req['requirement_id']
            
            # Random metadata
            priority = random.choice(PRIORITIES)
            status = random.choice(STATUSES)
            assignee = random.choice(ASSIGNEES)
            
            # Tags
            tags = f"{design_type}, {diagram_type}"
            
            created_by = "system"
            created_at = datetime.now() - timedelta(days=random.randint(0, 90))
            
            # Insert design using parameterized query with direct connection
            # We'll use a direct DB connection since execute_query doesn't support params
            db_path = Path(__file__).parent.parent / "data" / "local" / "dev" / "database" / "sakura_db.db"
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO design_tickets (
                        design_ticket_id, title, description, design_type, diagram_type,
                        image_url, linked_requirement_id, priority, status, assignee, tags,
                        created_by, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    design_id,
                    title,
                    description,
                    design_type,
                    diagram_type,
                    image_url,
                    requirement_id,
                    priority,
                    status,
                    assignee,
                    tags,
                    created_by,
                    created_at,
                    created_at  # updated_at same as created_at
                ))
                conn.commit()
                result = {"success": True, "lastrowid": cursor.lastrowid}
            finally:
                cursor.close()
                conn.close()
            
            if result.get('success'):
                created_count += 1
                
                if created_count % 50 == 0:
                    logger.info(f"Created {created_count} designs...")
            else:
                logger.warning(f"Failed to create design {design_id}")
                
        except Exception as e:
            logger.error(f"Failed to create design #{i}: {e}")
    
    logger.info(f"Successfully created {created_count} designs")
    return created_count

def link_designs_to_requirements():
    """Update requirements to link back to designs (bi-directional)"""
    database_service = get_hybrid_database_service()
    
    logger.info("Creating bi-directional links from requirements to designs...")
    
    # Get all designs with their linked requirements
    try:
        result = database_service.execute_query(
            "SELECT design_ticket_id, linked_requirement_id FROM design_tickets",
            "default"
        )
        designs = result.get('data', [])
        logger.info(f"Found {len(designs)} designs to link")
    except Exception as e:
        logger.error(f"Failed to fetch designs: {e}")
        return
    
    # Group designs by requirement
    from collections import defaultdict
    req_to_designs = defaultdict(list)
    for design in designs:
        req_id = design['linked_requirement_id']
        if req_id:
            req_to_designs[req_id].append(design['design_ticket_id'])
    
    # Update each requirement with its linked design IDs
    updated_count = 0
    for req_id, design_ids in req_to_designs.items():
        try:
            # Store multiple design IDs as comma-separated
            design_ids_str = ', '.join(design_ids[:10])  # Limit to 10 to avoid field overflow
            
            # First check if design_ticket_id column exists
            check_query = "PRAGMA table_info(requirements)"
            result = database_service.execute_query(check_query, "default")
            columns = [col[1] for col in result.get('data', [])]
            
            if 'design_ticket_id' in columns:
                # Update requirement with linked design IDs
                req_id_escaped = str(req_id).replace("'", "''")
                design_ids_escaped = str(design_ids_str).replace("'", "''")
                
                update_query = f"""
                    UPDATE requirements 
                    SET design_ticket_id = '{design_ids_escaped}'
                    WHERE requirement_id = '{req_id_escaped}'
                """
                
                result = database_service.execute_query(update_query, "default")
                
                if result.get('success'):
                    updated_count += 1
                    
                    if updated_count % 50 == 0:
                        logger.info(f"Updated {updated_count} requirements...")
            
        except Exception as e:
            logger.error(f"Failed to update requirement {req_id}: {e}")
    
    logger.info(f"Successfully updated {updated_count} requirements with design links")

def main():
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("Creating Sample Design Tickets")
    logger.info("=" * 60)
    
    # Create designs
    designs_created = create_sample_designs(300)
    
    if designs_created:
        # Link designs to requirements (bi-directional)
        link_designs_to_requirements()
        
        logger.info("=" * 60)
        logger.info(f"Successfully created {designs_created} design tickets")
        logger.info("Designs are linked to requirements with bi-directional traceability")
        logger.info("=" * 60)
    else:
        logger.error("Failed to create any designs")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

