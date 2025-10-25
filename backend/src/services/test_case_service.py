from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.schemas.test_case_schema import TestCaseSchema, TestCaseCreateSchema
from src.repositories.test_case_repository import ITestCaseRepository
from src.infrastructure.logging_config import get_logger

logger = get_logger(__name__)


class ITestCaseService(ABC):
    """Interface for test case business logic operations"""
    
    @abstractmethod
    def get_all_test_cases(self) -> List[Dict[str, Any]]:
        """Get all test cases with business logic"""
        pass
    
    @abstractmethod
    def get_test_case_by_id(self, test_case_id: str) -> Optional[Dict[str, Any]]:
        """Get test case by ID with business logic"""
        pass
    
    @abstractmethod
    def get_test_cases_by_feature(self, feature: str) -> List[Dict[str, Any]]:
        """Get test cases by feature with business logic"""
        pass
    
    @abstractmethod
    def create_test_case(self, test_case_data: TestCaseCreateSchema) -> Dict[str, Any]:
        """Create test case with business logic validation"""
        pass
    
    @abstractmethod
    def update_test_case(self, test_case_id: str, test_case_data: dict) -> Optional[Dict[str, Any]]:
        """Update test case with business logic validation"""
        pass
    
    @abstractmethod
    def delete_test_case(self, test_case_id: str) -> bool:
        """Delete test case with business logic validation"""
        pass


class TestCaseService(ITestCaseService):
    """Concrete implementation of test case service with business logic"""
    
    def __init__(self, test_case_repository: ITestCaseRepository, git_database_service=None):
        self.test_case_repository = test_case_repository
        self.git_database_service = git_database_service
    
    def get_all_test_cases(self) -> List[Dict[str, Any]]:
        """Get all test cases with business logic"""
        try:
            test_cases = self.test_case_repository.find_all()
            
            # Apply business logic transformations
            for test_case in test_cases:
                # Add computed fields
                test_case['is_high_priority'] = test_case.get('priority') == 'P1'
                test_case['has_requirements'] = bool(test_case.get('associated_requirement_id'))
                test_case['test_complexity'] = self._calculate_test_complexity(test_case)
            
            return test_cases
        except Exception as e:
            raise Exception(f"Service error: Failed to get test cases - {str(e)}")
    
    def get_test_case_by_id(self, test_case_id: str) -> Optional[Dict[str, Any]]:
        """Get test case by ID with business logic"""
        try:
            if not test_case_id or not isinstance(test_case_id, str):
                raise ValueError("Invalid test case ID")
            
            test_case = self.test_case_repository.find_by_id(test_case_id)
            if test_case:
                # Apply business logic transformations
                test_case['is_high_priority'] = test_case.get('priority') == 'P1'
                test_case['has_requirements'] = bool(test_case.get('associated_requirement_id'))
                test_case['test_complexity'] = self._calculate_test_complexity(test_case)
            
            return test_case
        except Exception as e:
            raise Exception(f"Service error: Failed to get test case {test_case_id} - {str(e)}")
    
    def get_test_cases_by_feature(self, feature: str) -> List[Dict[str, Any]]:
        """Get test cases by feature with business logic"""
        try:
            if not feature or not isinstance(feature, str):
                raise ValueError("Invalid feature name")
            
            test_cases = self.test_case_repository.find_by_feature(feature)
            
            # Apply business logic transformations
            for test_case in test_cases:
                test_case['is_high_priority'] = test_case.get('priority') == 'P1'
                test_case['has_requirements'] = bool(test_case.get('associated_requirement_id'))
                test_case['test_complexity'] = self._calculate_test_complexity(test_case)
            
            return test_cases
        except Exception as e:
            raise Exception(f"Service error: Failed to get test cases for feature {feature} - {str(e)}")
    
    def create_test_case(self, test_case_data: TestCaseCreateSchema) -> Dict[str, Any]:
        """Create test case with business logic validation"""
        try:
            # Business logic validation
            self._validate_test_case_creation(test_case_data)
            
            # Check if test case ID already exists
            existing_test_case = self.test_case_repository.find_by_id(test_case_data.test_case_id)
            if existing_test_case:
                raise ValueError(f"Test case ID '{test_case_data.test_case_id}' already exists")
            
            # Create test case
            test_case = self.test_case_repository.create(test_case_data)
            
            # Apply business logic transformations
            if test_case:
                test_case['is_high_priority'] = test_case.get('priority') == 'P1'
                test_case['has_requirements'] = bool(test_case.get('associated_requirement_id'))
                test_case['test_complexity'] = self._calculate_test_complexity(test_case)
                
                # Commit changes to git if service is available
                if self.git_database_service:
                    try:
                        self.git_database_service.commit_changes(f"Create test case: {test_case_data.test_case_id}")
                    except Exception as e:
                        logger.warning(f"Failed to commit test case creation to git: {e}")
            
            return test_case
        except Exception as e:
            raise Exception(f"Service error: Failed to create test case - {str(e)}")
    
    def update_test_case(self, test_case_id: str, test_case_data: dict) -> Optional[Dict[str, Any]]:
        """Update test case with business logic validation"""
        try:
            if not test_case_id or not isinstance(test_case_id, str):
                raise ValueError("Invalid test case ID")
            
            # Check if test case exists
            existing_test_case = self.test_case_repository.find_by_id(test_case_id)
            if not existing_test_case:
                raise ValueError(f"Test case with ID {test_case_id} not found")
            
            # Business logic validation
            self._validate_test_case_update(test_case_data)
            
            # Update test case
            test_case = self.test_case_repository.update(test_case_id, test_case_data)
            
            # Apply business logic transformations
            if test_case:
                test_case['is_high_priority'] = test_case.get('priority') == 'P1'
                test_case['has_requirements'] = bool(test_case.get('associated_requirement_id'))
                test_case['test_complexity'] = self._calculate_test_complexity(test_case)
                
                # Commit changes to git if service is available
                if self.git_database_service:
                    try:
                        self.git_database_service.commit_changes(f"Update test case: {test_case_id}")
                    except Exception as e:
                        logger.warning(f"Failed to commit test case update to git: {e}")
            
            return test_case
        except Exception as e:
            raise Exception(f"Service error: Failed to update test case {test_case_id} - {str(e)}")
    
    def delete_test_case(self, test_case_id: str) -> bool:
        """Delete test case with business logic validation"""
        try:
            if not test_case_id or not isinstance(test_case_id, str):
                raise ValueError("Invalid test case ID")
            
            # Check if test case exists
            existing_test_case = self.test_case_repository.find_by_id(test_case_id)
            if not existing_test_case:
                raise ValueError(f"Test case with ID {test_case_id} not found")
            
            # Business logic: Check if test case is referenced by other entities
            # This could be expanded to check for dependencies
            
            # Delete test case
            success = self.test_case_repository.delete(test_case_id)
            
            # Commit changes to git if service is available and deletion was successful
            if success and self.git_database_service:
                try:
                    self.git_database_service.commit_changes(f"Delete test case: {test_case_id}")
                except Exception as e:
                    logger.warning(f"Failed to commit test case deletion to git: {e}")
            
            return success
        except Exception as e:
            raise Exception(f"Service error: Failed to delete test case {test_case_id} - {str(e)}")
    
    def _validate_test_case_creation(self, test_case_data: TestCaseCreateSchema) -> None:
        """Validate test case creation business rules"""
        # Validate test case ID format
        if not self._is_valid_test_case_id_format(test_case_data.test_case_id):
            raise ValueError("Test case ID must follow format: XX_FEATURE_XXX1")
        
        # Validate priority
        if test_case_data.priority and test_case_data.priority not in ['P1', 'P2', 'P3']:
            raise ValueError("Priority must be P1, P2, or P3")
        
        # Validate test type
        if test_case_data.test_type and test_case_data.test_type not in ['Positive', 'Negative', 'Boundary', 'Performance']:
            raise ValueError("Test type must be Positive, Negative, Boundary, or Performance")
    
    def _validate_test_case_update(self, test_case_data: dict) -> None:
        """Validate test case update business rules"""
        # Validate priority if provided
        if 'priority' in test_case_data and test_case_data['priority'] not in ['P1', 'P2', 'P3']:
            raise ValueError("Priority must be P1, P2, or P3")
        
        # Validate test type if provided
        if 'test_type' in test_case_data and test_case_data['test_type'] not in ['Positive', 'Negative', 'Boundary', 'Performance']:
            raise ValueError("Test type must be Positive, Negative, Boundary, or Performance")
    
    def _is_valid_test_case_id_format(self, test_case_id: str) -> bool:
        """Validate test case ID format: XX_FEATURE_XXX1"""
        if not test_case_id:
            return False
        import re
        pattern = r'^[A-Z]{2}_[A-Z_]+_\d+$'
        return bool(re.match(pattern, test_case_id))
    
    def _calculate_test_complexity(self, test_case: Dict[str, Any]) -> str:
        """Calculate test complexity based on various factors"""
        complexity_score = 0
        
        # Factor in procedure length
        procedure = test_case.get('procedure') or ''
        if len(procedure) > 1000:
            complexity_score += 2
        elif len(procedure) > 500:
            complexity_score += 1
        
        # Factor in preconditions
        preconditions = test_case.get('preconditions') or ''
        if len(preconditions) > 500:
            complexity_score += 1
        
        # Factor in expected behavior
        expected_behavior = test_case.get('expected_behavior') or ''
        if len(expected_behavior) > 500:
            complexity_score += 1
        
        # Factor in priority
        priority = test_case.get('priority') or ''
        if priority == 'P1':
            complexity_score += 1
        
        # Determine complexity level
        if complexity_score >= 4:
            return 'High'
        elif complexity_score >= 2:
            return 'Medium'
        else:
            return 'Low'
