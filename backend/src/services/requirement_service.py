from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.schemas.requirement_schema import RequirementSchema, RequirementCreateSchema, RequirementUpdateSchema
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class IRequirementService(ABC):
    """Interface for requirement business logic operations"""
    
    @abstractmethod
    def get_all_requirements(self) -> List[Dict[str, Any]]:
        """Get all requirements with business logic"""
        pass
    
    @abstractmethod
    def get_requirement_by_id(self, req_id: int) -> Optional[Dict[str, Any]]:
        """Get requirement by ID with business logic"""
        pass
    
    @abstractmethod
    def create_requirement(self, requirement_data: RequirementCreateSchema) -> Dict[str, Any]:
        """Create requirement with business logic validation"""
        pass
    
    @abstractmethod
    def update_requirement(self, req_id: int, requirement_data: RequirementUpdateSchema) -> Optional[Dict[str, Any]]:
        """Update requirement with business logic validation"""
        pass
    
    @abstractmethod
    def delete_requirement(self, req_id: int) -> bool:
        """Delete requirement with business logic validation"""
        pass


class RequirementService(IRequirementService):
    """Concrete implementation of requirement service with business logic"""
    
    def __init__(self, database_service):
        self.database_service = database_service
    
    def get_all_requirements(self) -> List[Dict[str, Any]]:
        """Get all requirements"""
        try:
            query = """SELECT id, requirement_id, title, description, given, when_action, then_result, 
                       priority, status, assignee, tags, created_by, created_at, updated_at 
                       FROM requirements ORDER BY created_at DESC"""
            result = self.database_service.execute_query(query, "default")
            data = result.get('data', [])
            return data
        except Exception as e:
            logger.error(f"Failed to get requirements: {e}")
            raise Exception(f"Service error: Failed to get requirements - {str(e)}")
    
    def get_requirement_by_id(self, req_id: int) -> Optional[Dict[str, Any]]:
        """Get requirement by ID"""
        try:
            if not isinstance(req_id, int) or req_id <= 0:
                raise ValueError("Invalid requirement ID")
            
            query = f"""SELECT id, requirement_id, title, description, given, when_action, 
                       then_result, priority, status, assignee, tags, created_by, 
                       created_at, updated_at FROM requirements WHERE id = {req_id}"""
            result = self.database_service.execute_query(query, "default")
            requirements = result.get('data', [])
            return requirements[0] if requirements else None
        except Exception as e:
            logger.error(f"Failed to get requirement: {e}")
            raise Exception(f"Service error: Failed to get requirement - {str(e)}")
    
    def create_requirement(self, requirement_data: RequirementCreateSchema) -> Dict[str, Any]:
        """Create requirement"""
        try:
            # Get current user from request context
            from flask import g
            created_by = g.get('current_username', 'system')
            
            logger.info(f"Creating requirement with data: {requirement_data.dict()}")
            
            # Prepare values with proper escaping
            desc_val = (requirement_data.description or '').replace("'", "''")
            given_val = (requirement_data.given or '').replace("'", "''")
            when_val = (requirement_data.when or '').replace("'", "''")
            then_val = (requirement_data.then or '').replace("'", "''")
            title_val = (requirement_data.title or '').replace("'", "''")
            req_id_val = (requirement_data.requirement_id or '').replace("'", "''")
            assignee_val = (requirement_data.assignee or '').replace("'", "''")
            tags_val = (requirement_data.tags or '').replace("'", "''")
            
            # Prepare query with all fields
            query = f"""
                INSERT INTO requirements 
                (requirement_id, title, description, given, when_action, then_result, priority, status, assignee, tags, created_by)
                VALUES 
                ('{req_id_val}', '{title_val}', '{desc_val}', '{given_val}', '{when_val}', '{then_val}', 
                 '{requirement_data.priority or 'P2'}', '{requirement_data.status or 'Draft'}', '{assignee_val}', '{tags_val}', '{created_by}')
            """
            
            logger.info(f"Executing query: {query}")
            result = self.database_service.execute_query(query, "default")
            
            if result.get("success"):
                # Get the created requirement
                get_query = f"""SELECT id, requirement_id, title, description, priority, status, created_by, 
                              created_at, updated_at FROM requirements WHERE requirement_id = '{requirement_data.requirement_id}'"""
                get_result = self.database_service.execute_query(get_query, "default")
                reqs = get_result.get('data', [])
                if reqs:
                    logger.info(f"Successfully created requirement with ID: {reqs[0].get('id')}")
                    return reqs[0]
                else:
                    logger.warning("Requirement created but not found in database")
                    return requirement_data.dict()
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"Query execution failed: {error_msg}")
                raise Exception(f"Failed to create requirement: {error_msg}")
        except Exception as e:
            logger.error(f"Failed to create requirement: {e}", exc_info=True)
            raise Exception(f"Service error: Failed to create requirement - {str(e)}")
    
    def update_requirement(self, req_id: int, requirement_data: RequirementUpdateSchema) -> Optional[Dict[str, Any]]:
        """Update requirement"""
        try:
            if not isinstance(req_id, int) or req_id <= 0:
                raise ValueError("Invalid requirement ID")
            
            # Build update query dynamically
            updates = []
            req_dict = requirement_data.dict(exclude_unset=True)
            
            for key, value in req_dict.items():
                if value is not None:
                    # Escape single quotes in string values
                    val = str(value).replace("'", "''") if isinstance(value, str) else value
                    updates.append(f"{key} = '{val}'")
            
            if not updates:
                return None
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            updates_str = ", ".join(updates)
            
            query = f"UPDATE requirements SET {updates_str} WHERE id = {req_id}"
            result = self.database_service.execute_query(query, "default")
            
            if result.get("success"):
                return self.get_requirement_by_id(req_id)
            return None
        except Exception as e:
            logger.error(f"Failed to update requirement: {e}")
            raise Exception(f"Service error: Failed to update requirement - {str(e)}")
    
    def delete_requirement(self, req_id: int) -> bool:
        """Delete requirement"""
        try:
            if not isinstance(req_id, int) or req_id <= 0:
                raise ValueError("Invalid requirement ID")
            
            query = f"DELETE FROM requirements WHERE id = {req_id}"
            result = self.database_service.execute_query(query, "default")
            return result.get("success", False)
        except Exception as e:
            logger.error(f"Failed to delete requirement: {e}")
            raise Exception(f"Service error: Failed to delete requirement - {str(e)}")

