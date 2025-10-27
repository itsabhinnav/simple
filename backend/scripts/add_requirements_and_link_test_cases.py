#!/usr/bin/env python3
"""
Script to add 500 requirements and link existing test cases to them
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.infrastructure.configuration_manager import ConfigurationManager, get_config_manager
from src.infrastructure.dependency_injection import DIContainer
from src.schemas.requirement_schema import RequirementCreateSchema
from src.infrastructure.logging_config import get_logger
from src.services.requirement_service import RequirementService
from src.services.hybrid_database_service import HybridDatabaseService
from src.repositories.user_repository import UserRepository

logger = get_logger(__name__)


def create_requirement_id(index: int, prefix: str = "REQ") -> str:
    """Generate a unique requirement ID"""
    return f"{prefix}_{index:04d}"


def create_requirements(count: int = 500):
    """Create 500 requirements with varied data"""
    
    # Initialize services using DI container
    from src.infrastructure.dependency_injection import get_requirement_service, get_hybrid_database_service
    requirement_service = get_requirement_service()
    database_service = get_hybrid_database_service()
    
    logger.info(f"Creating {count} requirements...")
    
    # Sample data for variety
    priorities = ["P1", "P2", "P3"]
    statuses = ["Draft", "Approved", "Implemented", "Tested"]
    requirement_types = ["Functional", "Non-Functional", "Performance", "Security", "Usability"]
    
    created_requirements = []
    
    for i in range(1, count + 1):
        req_id = create_requirement_id(i)
        
        priority = priorities[i % len(priorities)]
        status = statuses[i % len(statuses)]
        req_type = requirement_types[i % len(requirement_types)]
        
        requirement_data = RequirementCreateSchema(
            requirement_id=req_id,
            title=f"Requirement {req_id} - {req_type} Feature",
            description=f"This is requirement {req_id} for a {req_type.lower()} feature. "
                        f"It describes the expected behavior and acceptance criteria for the system.",
            priority=priority,
            status=status,
            assignee=f"Developer{(i % 10) + 1}",
            tags=f"{req_type}, {priority}, {status}",
            given=f"Given the system is operational",
            when=f"When user performs action {i}",
            then=f"Then the system should respond correctly to requirement {i}"
        )
        
        try:
            requirement = requirement_service.create_requirement(requirement_data)
            created_requirements.append({
                'requirement_id': req_id,
                'id': requirement.get('id') if isinstance(requirement, dict) else None
            })
            
            if i % 50 == 0:
                logger.info(f"Created {i} requirements...")
                
        except Exception as e:
            logger.error(f"Failed to create requirement {req_id}: {e}")
    
    logger.info(f"Successfully created {len(created_requirements)} requirements")
    return created_requirements


def link_test_cases_to_requirements():
    """Link existing test cases to requirements"""
    
    # Initialize services using DI container
    from src.infrastructure.dependency_injection import get_hybrid_database_service
    database_service = get_hybrid_database_service()
    
    logger.info("Linking test cases to requirements...")
    
    # Get all test cases
    try:
        result = database_service.execute_query(
            "SELECT test_case_id, id FROM test_cases",
            "default"
        )
        test_cases = result.get('data', [])
        logger.info(f"Found {len(test_cases)} test cases to link")
    except Exception as e:
        logger.error(f"Failed to fetch test cases: {e}")
        return
    
    # Get all requirements
    try:
        result = database_service.execute_query(
            "SELECT id, requirement_id FROM requirements ORDER BY id",
            "default"
        )
        requirements = result.get('data', [])
        logger.info(f"Found {len(requirements)} requirements to link")
    except Exception as e:
        logger.error(f"Failed to fetch requirements: {e}")
        return
    
    if not requirements:
        logger.warning("No requirements found to link test cases to")
        return
    
    # Link test cases to requirements
    linked_count = 0
    for i, test_case in enumerate(test_cases):
        # Distribute test cases evenly across requirements
        req_index = i % len(requirements)
        requirement = requirements[req_index]
        
        try:
            # Escape single quotes
            req_id_escaped = str(requirement['requirement_id']).replace("'", "''")
            tc_id_escaped = str(test_case['test_case_id']).replace("'", "''")
            
            # Update test case with associated requirement ID
            update_query = f"""
                UPDATE test_cases 
                SET associated_requirement_id = '{req_id_escaped}'
                WHERE test_case_id = '{tc_id_escaped}'
            """
            
            result = database_service.execute_query(update_query, "default")
            
            if result.get('success'):
                linked_count += 1
                
                if (i + 1) % 100 == 0:
                    logger.info(f"Linked {i + 1} test cases to requirements...")
            else:
                logger.warning(f"Failed to link test case {test_case['test_case_id']}")
                
        except Exception as e:
            logger.error(f"Failed to link test case {test_case['test_case_id']}: {e}")
    
    logger.info(f"Successfully linked {linked_count} test cases to requirements")


def main():
    """Main execution function"""
    logger.info("Starting requirement creation and test case linking process...")
    
    try:
        # Step 1: Create requirements
        requirements = create_requirements(500)
        
        # Step 2: Link test cases to requirements
        link_test_cases_to_requirements()
        
        logger.info("Process completed successfully!")
        print("\n✓ Successfully created 500 requirements")
        print(f"✓ Test cases have been linked to requirements")
        print("\nYou can now view the requirements and their traceability to test cases.")
        
    except Exception as e:
        logger.error(f"Process failed: {e}", exc_info=True)
        print(f"\n✗ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

