from flask import Blueprint, request, jsonify
from typing import Dict, Any
from src.services.requirement_service import IRequirementService
from src.schemas.requirement_schema import RequirementCreateSchema, RequirementUpdateSchema
from src.middleware.admin_middleware import require_admin
from src.infrastructure.logging_config import get_logger
from src.controllers._bulk_import_routes import attach_bulk_import_routes

logger = get_logger(__name__)


class RequirementController:
    """Controller for requirement-related API endpoints"""
    
    def __init__(self, requirement_service: IRequirementService):
        self.requirement_service = requirement_service
    
    def get_all_requirements(self) -> Dict[str, Any]:
        """GET /api/requirements - Get all requirements"""
        try:
            requirements = self.requirement_service.get_all_requirements()
            return jsonify({
                "success": True,
                "message": "Requirements retrieved successfully",
                "data": requirements,
                "count": len(requirements)
            }), 200
        except Exception as e:
            logger.error(f"Failed to retrieve requirements: {e}")
            return jsonify({
                "success": False,
                "error": "Failed to retrieve requirements",
                "message": str(e)
            }), 500
    
    def get_requirement_by_id(self, req_id: int) -> Dict[str, Any]:
        """GET /api/requirements/<id> - Get requirement by ID"""
        try:
            requirement = self.requirement_service.get_requirement_by_id(req_id)
            if requirement:
                return jsonify({
                    "success": True,
                    "message": "Requirement retrieved successfully",
                    "data": requirement
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Requirement not found",
                    "message": f"Requirement with ID {req_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.error(f"Failed to retrieve requirement: {e}")
            return jsonify({
                "success": False,
                "error": "Failed to retrieve requirement",
                "message": str(e)
            }), 500
    
    def create_requirement(self) -> Dict[str, Any]:
        """POST /api/requirements - Create a new requirement"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            logger.info(f"Creating requirement with data: {data}")
            
            # Accept legacy column names (`when_action`/`then_result`) so the
            # requirements modal and any older clients keep working without a
            # synchronised release. Detail page already renames client-side.
            if 'when_action' in data and 'when' not in data:
                data['when'] = data.pop('when_action')
            if 'then_result' in data and 'then' not in data:
                data['then'] = data.pop('then_result')
            
            requirement_data = RequirementCreateSchema(**data)
            requirement = self.requirement_service.create_requirement(requirement_data)
            
            return jsonify({
                "success": True,
                "message": "Requirement created successfully",
                "data": requirement
            }), 201
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.error(f"Failed to create requirement: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": "Failed to create requirement",
                "message": str(e)
            }), 500
    
    def update_requirement(self, req_id: int) -> Dict[str, Any]:
        """PUT /api/requirements/<id> - Update requirement"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400

            # Accept the legacy column names used by the requirements list
            # modal (`when_action`, `then_result`) and remap them to the
            # logical schema fields (`when`, `then`). The detail page already
            # renames client-side but the modal `onSubmit` did not, which
            # caused the keys to be silently dropped by Pydantic.
            if 'when_action' in data and 'when' not in data:
                data['when'] = data.pop('when_action')
            if 'then_result' in data and 'then' not in data:
                data['then'] = data.pop('then_result')

            requirement_data = RequirementUpdateSchema(**data)
            requirement = self.requirement_service.update_requirement(req_id, requirement_data)
            
            if requirement:
                return jsonify({
                    "success": True,
                    "message": "Requirement updated successfully",
                    "data": requirement
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Requirement not found",
                    "message": f"Requirement with ID {req_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.error(f"Failed to update requirement: {e}")
            return jsonify({
                "success": False,
                "error": "Failed to update requirement",
                "message": str(e)
            }), 500
    
    def delete_requirement(self, req_id: int) -> Dict[str, Any]:
        """DELETE /api/requirements/<id> - Delete requirement"""
        try:
            success = self.requirement_service.delete_requirement(req_id)
            if success:
                return jsonify({
                    "success": True,
                    "message": "Requirement deleted successfully"
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Requirement not found",
                    "message": f"Requirement with ID {req_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            logger.error(f"Failed to delete requirement: {e}")
            return jsonify({
                "success": False,
                "error": "Failed to delete requirement",
                "message": str(e)
            }), 500


def create_requirement_blueprint(requirement_service: IRequirementService) -> Blueprint:
    """Create and configure requirement blueprint"""
    req_bp = Blueprint('requirements', __name__, url_prefix='/api/requirements')
    controller = RequirementController(requirement_service)
    
    # Register routes. Bulk-import routes (`/import`, `/import/preview`,
    # `/import/fields`) MUST be attached before the `/<int:req_id>`
    # catch-alls so Flask's router doesn't treat the literal string
    # "import" as an integer ID.
    req_bp.route('/', methods=['GET'])(controller.get_all_requirements)
    req_bp.route('/', methods=['POST'])(controller.create_requirement)
    attach_bulk_import_routes(req_bp, "requirements")
    req_bp.route('/<int:req_id>', methods=['GET'])(controller.get_requirement_by_id)
    req_bp.route('/<int:req_id>', methods=['PUT'])(controller.update_requirement)
    req_bp.route('/<int:req_id>', methods=['DELETE'])(controller.delete_requirement)
    
    return req_bp


