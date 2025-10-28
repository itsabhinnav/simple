from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.schemas.design_ticket_schema import DesignTicketSchema, DesignTicketCreateSchema, DesignTicketUpdateSchema
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class IDesignTicketService(ABC):
    """Interface for design ticket business logic operations"""
    
    @abstractmethod
    def get_all_design_tickets(self) -> List[Dict[str, Any]]:
        """Get all design tickets with business logic"""
        pass
    
    @abstractmethod
    def get_design_ticket_by_id(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """Get design ticket by ID with business logic"""
        pass
    
    @abstractmethod
    def create_design_ticket(self, ticket_data: DesignTicketCreateSchema) -> Dict[str, Any]:
        """Create design ticket with business logic validation"""
        pass
    
    @abstractmethod
    def update_design_ticket(self, ticket_id: int, ticket_data: DesignTicketUpdateSchema) -> Optional[Dict[str, Any]]:
        """Update design ticket with business logic validation"""
        pass
    
    @abstractmethod
    def delete_design_ticket(self, ticket_id: int) -> bool:
        """Delete design ticket with business logic validation"""
        pass


class DesignTicketService(IDesignTicketService):
    """Concrete implementation of design ticket service with business logic"""
    
    def __init__(self, database_service):
        self.database_service = database_service
    
    def get_all_design_tickets(self) -> List[Dict[str, Any]]:
        """Get all design tickets"""
        try:
            query = """SELECT id, design_ticket_id, title, description, design_type, diagram_type, image_url,
                       priority, status, requirement_id, assignee, tags, created_by, created_at, updated_at 
                       FROM design_tickets ORDER BY created_at DESC"""
            result = self.database_service.execute_query(query, "default")
            data = result.get('data', [])
            return data
        except Exception as e:
            logger.error(f"Failed to get design tickets: {e}")
            raise Exception(f"Service error: Failed to get design tickets - {str(e)}")
    
    def get_design_ticket_by_id(self, ticket_id: int) -> Optional[Dict[str, Any]]:
        """Get design ticket by ID"""
        try:
            if not isinstance(ticket_id, int) or ticket_id <= 0:
                raise ValueError("Invalid design ticket ID")
            
            query = f"""SELECT id, design_ticket_id, title, description, design_type, diagram_type, image_url,
                       priority, status, requirement_id, assignee, tags, created_by, 
                       created_at, updated_at FROM design_tickets WHERE id = {ticket_id}"""
            result = self.database_service.execute_query(query, "default")
            tickets = result.get('data', [])
            return tickets[0] if tickets else None
        except Exception as e:
            logger.error(f"Failed to get design ticket: {e}")
            raise Exception(f"Service error: Failed to get design ticket - {str(e)}")
    
    def create_design_ticket(self, ticket_data: DesignTicketCreateSchema) -> Dict[str, Any]:
        """Create design ticket"""
        try:
            # Get current user from request context
            from flask import g
            created_by = g.get('current_username', 'system')
            
            logger.info(f"Creating design ticket with data: {ticket_data.dict()}")
            
            # Build SQL query
            columns = ['design_ticket_id', 'title', 'description', 'design_type', 'diagram_type', 
                      'image_url', 'priority', 'status', 'requirement_id', 'assignee', 'tags', 'created_by']
            values = [
                ticket_data.design_ticket_id,
                ticket_data.title,
                ticket_data.description,
                ticket_data.design_type,
                ticket_data.diagram_type,
                ticket_data.image_url,
                ticket_data.priority,
                ticket_data.status,
                ticket_data.requirement_id,
                ticket_data.assignee,
                ticket_data.tags,
                created_by
            ]
            
            placeholders = ', '.join(['?' for _ in values])
            column_names = ', '.join(columns)
            
            insert_query = f"INSERT INTO design_tickets ({column_names}, created_at, updated_at) VALUES ({placeholders}, datetime('now'), datetime('now'))"
            
            result = self.database_service.execute_query(insert_query, "default", tuple(values))
            
            if result.get('success'):
                # Retrieve the created design ticket
                ticket = self.get_design_ticket_by_id(result.get('last_row_id'))
                if ticket:
                    logger.info(f"Design ticket created successfully: {ticket['design_ticket_id']}")
                    return ticket
                else:
                    raise Exception("Failed to retrieve created design ticket")
            else:
                raise Exception("Failed to create design ticket")
                
        except Exception as e:
            logger.error(f"Failed to create design ticket: {e}")
            raise Exception(f"Service error: Failed to create design ticket - {str(e)}")
    
    def update_design_ticket(self, ticket_id: int, ticket_data: DesignTicketUpdateSchema) -> Optional[Dict[str, Any]]:
        """Update design ticket"""
        try:
            if not isinstance(ticket_id, int) or ticket_id <= 0:
                raise ValueError("Invalid design ticket ID")
            
            # Build update query dynamically based on provided data
            update_data = {k: v for k, v in ticket_data.dict().items() if v is not None}
            
            if not update_data:
                raise ValueError("No fields to update")
            
            # Add updated_at timestamp
            update_data['updated_at'] = "datetime('now')"
            
            set_clause = ', '.join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values())
            values.append(ticket_id)
            
            update_query = f"UPDATE design_tickets SET {set_clause} WHERE id = ?"
            
            result = self.database_service.execute_query(update_query, "default", tuple(values))
            
            if result.get('success'):
                # Retrieve the updated design ticket
                ticket = self.get_design_ticket_by_id(ticket_id)
                if ticket:
                    logger.info(f"Design ticket updated successfully: {ticket['design_ticket_id']}")
                    return ticket
                else:
                    raise Exception("Failed to retrieve updated design ticket")
            else:
                raise Exception("Failed to update design ticket")
                
        except Exception as e:
            logger.error(f"Failed to update design ticket: {e}")
            raise Exception(f"Service error: Failed to update design ticket - {str(e)}")
    
    def delete_design_ticket(self, ticket_id: int) -> bool:
        """Delete design ticket"""
        try:
            if not isinstance(ticket_id, int) or ticket_id <= 0:
                raise ValueError("Invalid design ticket ID")
            
            delete_query = f"DELETE FROM design_tickets WHERE id = {ticket_id}"
            result = self.database_service.execute_query(delete_query, "default")
            
            if result.get('success'):
                logger.info(f"Design ticket deleted successfully: ID {ticket_id}")
                return True
            else:
                logger.warning(f"Failed to delete design ticket: ID {ticket_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete design ticket: {e}")
            raise Exception(f"Service error: Failed to delete design ticket - {str(e)}")

