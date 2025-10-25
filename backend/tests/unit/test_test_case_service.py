"""
Unit Tests for Test Case Service

This module provides comprehensive unit tests for the TestCaseService class
to achieve 100% C0 and C1 coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Optional

from src.services.test_case_service import TestCaseService, ITestCaseService
from src.schemas.test_case_schema import TestCaseCreateSchema
from tests import create_test_case_data


class TestTestCaseService:
    """Test cases for TestCaseService"""
    
    def test_init(self):
        """Test service initialization"""
        mock_repository = Mock()
        service = TestCaseService(mock_repository)
        
        assert service.test_case_repository == mock_repository
    
    def test_get_all_test_cases_success(self):
        """Test successful retrieval of all test cases"""
        mock_repository = Mock()
        mock_test_cases = [
            {
                "id": 1,
                "test_case_id": "TC001",
                "test_name": "Test Case 1",
                "priority": "P1",
                "associated_requirement_id": "REQ001",
                "test_steps": "Step 1\nStep 2",
                "expected_result": "Expected result"
            },
            {
                "id": 2,
                "test_case_id": "TC002",
                "test_name": "Test Case 2",
                "priority": "P2",
                "associated_requirement_id": None,
                "test_steps": "Step 1",
                "expected_result": "Expected result"
            }
        ]
        mock_repository.find_all.return_value = mock_test_cases
        
        service = TestCaseService(mock_repository)
        result = service.get_all_test_cases()
        
        assert len(result) == 2
        assert result[0]["is_high_priority"] is True
        assert result[0]["has_requirements"] is True
        assert result[0]["test_complexity"] == "High"
        assert result[1]["is_high_priority"] is False
        assert result[1]["has_requirements"] is False
        assert result[1]["test_complexity"] == "Low"
    
    def test_get_all_test_cases_exception(self):
        """Test exception handling in get_all_test_cases"""
        mock_repository = Mock()
        mock_repository.find_all.side_effect = Exception("Database error")
        
        service = TestCaseService(mock_repository)
        
        with pytest.raises(Exception, match="Service error: Failed to get test cases"):
            service.get_all_test_cases()
    
    def test_get_test_case_by_id_success(self):
        """Test successful retrieval of test case by ID"""
        mock_repository = Mock()
        mock_test_case = {
            "id": 1,
            "test_case_id": "TC001",
            "test_name": "Test Case 1",
            "priority": "P1",
            "associated_requirement_id": "REQ001",
            "test_steps": "Step 1\nStep 2\nStep 3",
            "expected_result": "Expected result"
        }
        mock_repository.find_by_id.return_value = mock_test_case
        
        service = TestCaseService(mock_repository)
        result = service.get_test_case_by_id("TC001")
        
        assert result is not None
        assert result["is_high_priority"] is True
        assert result["has_requirements"] is True
        assert result["test_complexity"] == "High"
        mock_repository.find_by_id.assert_called_once_with("TC001")
    
    def test_get_test_case_by_id_not_found(self):
        """Test retrieval of non-existent test case"""
        mock_repository = Mock()
        mock_repository.find_by_id.return_value = None
        
        service = TestCaseService(mock_repository)
        result = service.get_test_case_by_id("TC999")
        
        assert result is None
        mock_repository.find_by_id.assert_called_once_with("TC999")
    
    def test_get_test_case_by_id_invalid_id(self):
        """Test retrieval with invalid ID"""
        mock_repository = Mock()
        
        service = TestCaseService(mock_repository)
        
        with pytest.raises(Exception, match="Service error: Failed to get test case"):
            service.get_test_case_by_id(None)
        
        with pytest.raises(Exception, match="Service error: Failed to get test case"):
            service.get_test_case_by_id(123)  # Not a string
    
    def test_get_test_case_by_id_exception(self):
        """Test exception handling in get_test_case_by_id"""
        mock_repository = Mock()
        mock_repository.find_by_id.side_effect = Exception("Database error")
        
        service = TestCaseService(mock_repository)
        
        with pytest.raises(Exception, match="Service error: Failed to get test case"):
            service.get_test_case_by_id("TC001")
    
    def test_get_test_cases_by_feature_success(self):
        """Test successful retrieval of test cases by feature"""
        mock_repository = Mock()
        mock_test_cases = [
            {
                "id": 1,
                "test_case_id": "TC001",
                "test_name": "Test Case 1",
                "feature": "Authentication",
                "priority": "P1",
                "associated_requirement_id": "REQ001",
                "test_steps": "Step 1\nStep 2",
                "expected_result": "Expected result"
            }
        ]
        mock_repository.find_by_feature.return_value = mock_test_cases
        
        service = TestCaseService(mock_repository)
        result = service.get_test_cases_by_feature("Authentication")
        
        assert len(result) == 1
        assert result[0]["is_high_priority"] is True
        assert result[0]["has_requirements"] is True
        assert result[0]["test_complexity"] == "High"
        mock_repository.find_by_feature.assert_called_once_with("Authentication")
    
    def test_get_test_cases_by_feature_empty(self):
        """Test retrieval of test cases by feature with no results"""
        mock_repository = Mock()
        mock_repository.find_by_feature.return_value = []
        
        service = TestCaseService(mock_repository)
        result = service.get_test_cases_by_feature("NonexistentFeature")
        
        assert result == []
        mock_repository.find_by_feature.assert_called_once_with("NonexistentFeature")
    
    def test_get_test_cases_by_feature_exception(self):
        """Test exception handling in get_test_cases_by_feature"""
        mock_repository = Mock()
        mock_repository.find_by_feature.side_effect = Exception("Database error")
        
        service = TestCaseService(mock_repository)
        
        with pytest.raises(Exception, match="Service error: Failed to get test cases by feature"):
            service.get_test_cases_by_feature("Authentication")
    
    def test_create_test_case_success(self):
        """Test successful test case creation"""
        mock_repository = Mock()
        mock_created_case = {
            "id": 1,
            "test_case_id": "TC001",
            "test_name": "Test Case 1",
            "priority": "P1",
            "associated_requirement_id": "REQ001",
            "test_steps": "Step 1\nStep 2",
            "expected_result": "Expected result"
        }
        mock_repository.create.return_value = mock_created_case
        
        service = TestCaseService(mock_repository)
        test_case_data = TestCaseCreateSchema(**create_test_case_data())
        result = service.create_test_case(test_case_data)
        
        assert result is not None
        assert result["is_high_priority"] is True
        assert result["has_requirements"] is True
        assert result["test_complexity"] == "High"
        mock_repository.create.assert_called_once_with(test_case_data)
    
    def test_create_test_case_exception(self):
        """Test exception handling in create_test_case"""
        mock_repository = Mock()
        mock_repository.create.side_effect = Exception("Database error")
        
        service = TestCaseService(mock_repository)
        test_case_data = TestCaseCreateSchema(**create_test_case_data())
        
        with pytest.raises(Exception, match="Service error: Failed to create test case"):
            service.create_test_case(test_case_data)
    
    def test_update_test_case_success(self):
        """Test successful test case update"""
        mock_repository = Mock()
        mock_updated_case = {
            "id": 1,
            "test_case_id": "TC001",
            "test_name": "Updated Test Case",
            "priority": "P2",
            "associated_requirement_id": None,
            "test_steps": "Step 1",
            "expected_result": "Updated result"
        }
        mock_repository.update.return_value = mock_updated_case
        
        service = TestCaseService(mock_repository)
        update_data = {"test_name": "Updated Test Case", "priority": "P2"}
        result = service.update_test_case("TC001", update_data)
        
        assert result is not None
        assert result["is_high_priority"] is False
        assert result["has_requirements"] is False
        assert result["test_complexity"] == "Low"
        mock_repository.update.assert_called_once_with("TC001", update_data)
    
    def test_update_test_case_not_found(self):
        """Test update of non-existent test case"""
        mock_repository = Mock()
        mock_repository.update.return_value = None
        
        service = TestCaseService(mock_repository)
        update_data = {"test_name": "Updated Test Case"}
        result = service.update_test_case("TC999", update_data)
        
        assert result is None
        mock_repository.update.assert_called_once_with("TC999", update_data)
    
    def test_update_test_case_exception(self):
        """Test exception handling in update_test_case"""
        mock_repository = Mock()
        mock_repository.update.side_effect = Exception("Database error")
        
        service = TestCaseService(mock_repository)
        update_data = {"test_name": "Updated Test Case"}
        
        with pytest.raises(Exception, match="Service error: Failed to update test case"):
            service.update_test_case("TC001", update_data)
    
    def test_delete_test_case_success(self):
        """Test successful test case deletion"""
        mock_repository = Mock()
        mock_repository.delete.return_value = True
        
        service = TestCaseService(mock_repository)
        result = service.delete_test_case("TC001")
        
        assert result is True
        mock_repository.delete.assert_called_once_with("TC001")
    
    def test_delete_test_case_not_found(self):
        """Test deletion of non-existent test case"""
        mock_repository = Mock()
        mock_repository.delete.return_value = False
        
        service = TestCaseService(mock_repository)
        result = service.delete_test_case("TC999")
        
        assert result is False
        mock_repository.delete.assert_called_once_with("TC999")
    
    def test_delete_test_case_exception(self):
        """Test exception handling in delete_test_case"""
        mock_repository = Mock()
        mock_repository.delete.side_effect = Exception("Database error")
        
        service = TestCaseService(mock_repository)
        
        with pytest.raises(Exception, match="Service error: Failed to delete test case"):
            service.delete_test_case("TC001")
    
    def test_calculate_test_complexity_high(self):
        """Test test complexity calculation for high complexity"""
        mock_repository = Mock()
        service = TestCaseService(mock_repository)
        
        test_case = {
            "test_steps": "Step 1\nStep 2\nStep 3\nStep 4\nStep 5",
            "expected_result": "Complex expected result with multiple conditions"
        }
        
        complexity = service._calculate_test_complexity(test_case)
        assert complexity == "High"
    
    def test_calculate_test_complexity_medium(self):
        """Test test complexity calculation for medium complexity"""
        mock_repository = Mock()
        service = TestCaseService(mock_repository)
        
        test_case = {
            "test_steps": "Step 1\nStep 2\nStep 3",
            "expected_result": "Medium complexity result"
        }
        
        complexity = service._calculate_test_complexity(test_case)
        assert complexity == "Medium"
    
    def test_calculate_test_complexity_low(self):
        """Test test complexity calculation for low complexity"""
        mock_repository = Mock()
        service = TestCaseService(mock_repository)
        
        test_case = {
            "test_steps": "Step 1",
            "expected_result": "Simple result"
        }
        
        complexity = service._calculate_test_complexity(test_case)
        assert complexity == "Low"
    
    def test_calculate_test_complexity_missing_fields(self):
        """Test test complexity calculation with missing fields"""
        mock_repository = Mock()
        service = TestCaseService(mock_repository)
        
        test_case = {}
        
        complexity = service._calculate_test_complexity(test_case)
        assert complexity == "Low"
    
    def test_calculate_test_complexity_none_values(self):
        """Test test complexity calculation with None values"""
        mock_repository = Mock()
        service = TestCaseService(mock_repository)
        
        test_case = {
            "test_steps": None,
            "expected_result": None
        }
        
        complexity = service._calculate_test_complexity(test_case)
        assert complexity == "Low"


class TestITestCaseService:
    """Test cases for ITestCaseService interface"""
    
    def test_interface_methods_exist(self):
        """Test that interface defines all required methods"""
        # This test ensures the interface is properly defined
        assert hasattr(ITestCaseService, 'get_all_test_cases')
        assert hasattr(ITestCaseService, 'get_test_case_by_id')
        assert hasattr(ITestCaseService, 'get_test_cases_by_feature')
        assert hasattr(ITestCaseService, 'create_test_case')
        assert hasattr(ITestCaseService, 'update_test_case')
        assert hasattr(ITestCaseService, 'delete_test_case')
    
    def test_interface_is_abstract(self):
        """Test that interface cannot be instantiated directly"""
        with pytest.raises(TypeError):
            ITestCaseService()
