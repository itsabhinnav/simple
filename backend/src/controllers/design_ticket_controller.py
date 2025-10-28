from flask import Blueprint, request, jsonify
from typing import Dict, Any
from src.services.design_ticket_service import IDesignTicketService
from src.schemas.design_ticket_schema import DesignTicketCreateSchema, DesignTicketUpdateSchema
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class DesignTicketController:
    """Controller for design ticket-related API endpoints"""
    
    def __init__(self, design_ticket_service: IDesignTicketService):
        self.design_ticket_service = design_ticket_service
    
    def get_all_design_tickets(self) -> Dict[str, Any]:
        """GET /api/design-tickets - Get all design tickets"""
        try:
            design_tickets = self.design_ticket_service.get_all_design_tickets()
            return jsonify({
                "success": True,
                "message": "Design tickets retrieved successfully",
                "data": design_tickets,
                "count": len(design_tickets)
            }), 200
        except Exception as e:
            logger.error(f"Failed to retrieve design tickets: {e}")
            return jsonify({
                "success": False,
                "error": "Failed to retrieve design tickets",
                "message": str(e)
            }), 500
    
    def get_design_ticket_by_id(self, ticket_id: int) -> Dict[str, Any]:
        """GET /api/design-tickets/<id> - Get design ticket by ID"""
        try:
            design_ticket = self.design_ticket_service.get_design_ticket_by_id(ticket_id)
            if design_ticket:
                return jsonify({
                    "success": True,
                    "message": "Design ticket retrieved successfully",
                    "data": design_ticket
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Design ticket not found",
                    "message": f"Design ticket with ID {ticket_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.error(f"Failed to retrieve design ticket: {e}")
            return jsonify({
                "success": False,
                "error": "Failed to retrieve design ticket",
                "message": str(e)
            }), 500
    
    def create_design_ticket(self) -> Dict[str, Any]:
        """POST /api/design-tickets - Create a new design ticket"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            logger.info(f"Creating design ticket with data: {data}")
            
            design_ticket_data = DesignTicketCreateSchema(**data)
            design_ticket = self.design_ticket_service.create_design_ticket(design_ticket_data)
            
            return jsonify({
                "success": True,
                "message": "Design ticket created successfully",
                "data": design_ticket
            }), 201
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.error(f"Failed to create design ticket: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to create design ticket",
                "message": str(e)
            }), 500
    
    def update_design_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """PUT /api/design-tickets/<id> - Update a design ticket"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            logger.info(f"Updating design ticket {ticket_id} with data: {data}")
            
            design_ticket_data = DesignTicketUpdateSchema(**data)
            design_ticket = self.design_ticket_service.update_design_ticket(ticket_id, design_ticket_data)
            
            if design_ticket:
                return jsonify({
                    "success": True,
                    "message": "Design ticket updated successfully",
                    "data": design_ticket
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Design ticket not found",
                    "message": f"Design ticket with ID {ticket_id} not found"
                }), 404
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.error(f"Failed to update design ticket: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to update design ticket",
                "message": str(e)
            }), 500
    
    def delete_design_ticket(self, ticket_id: int) -> Dict[str, Any]:
        """DELETE /api/design-tickets/<id> - Delete a design ticket"""
        try:
            success = self.design_ticket_service.delete_design_ticket(ticket_id)
            
            if success:
                return jsonify({
                    "success": True,
                    "message": "Design ticket deleted successfully"
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Design ticket not found",
                    "message": f"Design ticket with ID {ticket_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.error(f"Failed to delete design ticket: {e}")
            return jsonify({
                "success": False,
                "error": "Failed to delete design ticket",
                "message": str(e)
            }), 500


def create_design_ticket_blueprint(design_ticket_service: IDesignTicketService) -> Blueprint:
    """Create and configure design ticket blueprint"""
    dt_bp = Blueprint('design_tickets', __name__, url_prefix='/api/design-tickets')
    controller = DesignTicketController(design_ticket_service)
    
    # Register routes
    dt_bp.route('/', methods=['GET'])(controller.get_all_design_tickets)
    dt_bp.route('/', methods=['POST'])(controller.create_design_ticket)
    dt_bp.route('/<int:ticket_id>', methods=['GET'])(controller.get_design_ticket_by_id)
    dt_bp.route('/<int:ticket_id>', methods=['PUT'])(controller.update_design_ticket)
    dt_bp.route('/<int:ticket_id>', methods=['DELETE'])(controller.delete_design_ticket)
    
    return dt_bp

