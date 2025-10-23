from flask import Blueprint, request, jsonify
from typing import Dict, Any
from src.services.test_case_service import ITestCaseService
from src.schemas.test_case_schema import TestCaseCreateSchema
from src.schemas.api_schema import ErrorResponseSchema, SuccessResponseSchema


class TestCaseController:
    """Controller for test case-related API endpoints"""
    
    def __init__(self, test_case_service: ITestCaseService):
        self.test_case_service = test_case_service
    
    def get_all_test_cases(self) -> Dict[str, Any]:
        """GET /api/test-cases - Get all test cases"""
        try:
            test_cases = self.test_case_service.get_all_test_cases()
            return jsonify({
                "success": True,
                "message": "Test cases retrieved successfully",
                "data": test_cases,
                "count": len(test_cases)
            }), 200
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to retrieve test cases",
                "message": str(e)
            }), 500
    
    def get_test_case_by_id(self, test_case_id: str) -> Dict[str, Any]:
        """GET /api/test-cases/<test_case_id> - Get test case by ID"""
        try:
            test_case = self.test_case_service.get_test_case_by_id(test_case_id)
            if test_case:
                return jsonify({
                    "success": True,
                    "message": "Test case retrieved successfully",
                    "data": test_case
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Test case not found",
                    "message": f"Test case with ID {test_case_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to retrieve test case",
                "message": str(e)
            }), 500
    
    def get_test_cases_by_feature(self) -> Dict[str, Any]:
        """GET /api/test-cases/feature/<feature> - Get test cases by feature"""
        try:
            feature = request.args.get('feature')
            if not feature:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Feature parameter is required"
                }), 400
            
            test_cases = self.test_case_service.get_test_cases_by_feature(feature)
            return jsonify({
                "success": True,
                "message": f"Test cases for feature '{feature}' retrieved successfully",
                "data": test_cases,
                "count": len(test_cases)
            }), 200
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to retrieve test cases",
                "message": str(e)
            }), 500
    
    def create_test_case(self) -> Dict[str, Any]:
        """POST /api/test-cases - Create a new test case"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            # Validate data using schema
            test_case_data = TestCaseCreateSchema(**data)
            test_case = self.test_case_service.create_test_case(test_case_data)
            
            return jsonify({
                "success": True,
                "message": "Test case created successfully",
                "data": test_case
            }), 201
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to create test case",
                "message": str(e)
            }), 500
    
    def update_test_case(self, test_case_id: str) -> Dict[str, Any]:
        """PUT /api/test-cases/<test_case_id> - Update test case"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Invalid request",
                    "message": "Request body is required"
                }), 400
            
            test_case = self.test_case_service.update_test_case(test_case_id, data)
            
            if test_case:
                return jsonify({
                    "success": True,
                    "message": "Test case updated successfully",
                    "data": test_case
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Test case not found",
                    "message": f"Test case with ID {test_case_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Validation error",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to update test case",
                "message": str(e)
            }), 500
    
    def delete_test_case(self, test_case_id: str) -> Dict[str, Any]:
        """DELETE /api/test-cases/<test_case_id> - Delete test case"""
        try:
            success = self.test_case_service.delete_test_case(test_case_id)
            if success:
                return jsonify({
                    "success": True,
                    "message": "Test case deleted successfully"
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": "Test case not found",
                    "message": f"Test case with ID {test_case_id} not found"
                }), 404
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": "Invalid request",
                "message": str(e)
            }), 400
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Failed to delete test case",
                "message": str(e)
            }), 500


def create_test_case_blueprint(test_case_service: ITestCaseService) -> Blueprint:
    """Create and configure test case blueprint"""
    test_case_bp = Blueprint('test_cases', __name__, url_prefix='/api/test-cases')
    controller = TestCaseController(test_case_service)
    
    # Register routes
    test_case_bp.route('/', methods=['GET'])(controller.get_all_test_cases)
    test_case_bp.route('/', methods=['POST'])(controller.create_test_case)
    test_case_bp.route('/<test_case_id>', methods=['GET'])(controller.get_test_case_by_id)
    test_case_bp.route('/<test_case_id>', methods=['PUT'])(controller.update_test_case)
    test_case_bp.route('/<test_case_id>', methods=['DELETE'])(controller.delete_test_case)
    test_case_bp.route('/feature', methods=['GET'])(controller.get_test_cases_by_feature)
    
    return test_case_bp
