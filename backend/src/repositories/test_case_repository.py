from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from src.schemas.test_case_schema import TestCaseSchema, TestCaseCreateSchema


class ITestCaseRepository(ABC):
    """Interface for test case data access operations"""
    
    @abstractmethod
    def find_all(self) -> List[Dict[str, Any]]:
        """Get all test cases"""
        pass
    
    @abstractmethod
    def find_by_id(self, test_case_id: str) -> Optional[Dict[str, Any]]:
        """Get test case by ID"""
        pass
    
    @abstractmethod
    def find_by_feature(self, feature: str) -> List[Dict[str, Any]]:
        """Get test cases by feature"""
        pass
    
    @abstractmethod
    def create(self, test_case_data: TestCaseCreateSchema) -> Dict[str, Any]:
        """Create a new test case"""
        pass
    
    @abstractmethod
    def update(self, test_case_id: str, test_case_data: dict) -> Optional[Dict[str, Any]]:
        """Update test case data"""
        pass
    
    @abstractmethod
    def delete(self, test_case_id: str) -> bool:
        """Delete test case"""
        pass


class TestCaseRepository(ITestCaseRepository):
    """Concrete implementation of test case repository"""
    
    def __init__(self, database_service, table_name: str = "test_cases"):
        self.database_service = database_service
        self.table_name = table_name
    
    def find_all(self) -> List[Dict[str, Any]]:
        """Get all test cases from database"""
        try:
            result = self.database_service.execute_query(
                f"SELECT * FROM {self.table_name} ORDER BY id",
                "default"
            )
            return result.get('data', [])
        except Exception as e:
            raise Exception(f"Failed to fetch test cases: {str(e)}")
    
    def find_by_id(self, test_case_id: str) -> Optional[Dict[str, Any]]:
        """Get test case by ID"""
        try:
            result = self.database_service.execute_query(
                f"SELECT * FROM {self.table_name} WHERE test_case_id = '{test_case_id}'",
                "default"
            )
            test_cases = result.get('data', [])
            return test_cases[0] if test_cases else None
        except Exception as e:
            raise Exception(f"Failed to fetch test case {test_case_id}: {str(e)}")
    
    def find_by_feature(self, feature: str) -> List[Dict[str, Any]]:
        """Get test cases by feature"""
        try:
            result = self.database_service.execute_query(
                f"SELECT * FROM {self.table_name} WHERE feature LIKE '%{feature}%'",
                "default"
            )
            return result.get('data', [])
        except Exception as e:
            raise Exception(f"Failed to fetch test cases for feature {feature}: {str(e)}")
    
    def create(self, test_case_data: TestCaseCreateSchema) -> Dict[str, Any]:
        """Create a new test case"""
        try:
            # Convert schema to dict and prepare SQL
            test_case_dict = test_case_data.dict()
            
            # Filter out None values
            filtered_dict = {k: v for k, v in test_case_dict.items() if v is not None}
            
            if not filtered_dict:
                raise Exception("No valid data provided for test case creation")
            
            columns = ', '.join(filtered_dict.keys())
            values = ', '.join([f"'{v}'" if isinstance(v, str) else str(v) for v in filtered_dict.values()])

            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({values})"
            result = self.database_service.execute_query(query, "default")
            
            if not result.get("success"):
                raise Exception(f"Insert failed: {result.get('error', 'Unknown error')}")
            
            # Return the created test case data with additional fields
            created_test_case = test_case_dict.copy()
            created_test_case['id'] = result.get('lastrowid', None)
            created_test_case['created_at'] = result.get('created_at', None)
            created_test_case['updated_at'] = result.get('updated_at', None)
            
            return created_test_case
        except Exception as e:
            raise Exception(f"Failed to create test case: {str(e)}")
    
    def update(self, test_case_id: str, test_case_data: dict) -> Optional[Dict[str, Any]]:
        """Update test case data"""
        try:
            if not test_case_data:
                return self.find_by_id(test_case_id)
            
            set_clause = ', '.join([f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}" 
                                  for k, v in test_case_data.items()])
            
            query = f"UPDATE {self.table_name} SET {set_clause} WHERE test_case_id = '{test_case_id}'"
            result = self.database_service.execute_query(query, "default")
            
            if not result.get("success"):
                raise Exception(f"Update failed: {result.get('error', 'Unknown error')}")
            
            return self.find_by_id(test_case_id)
        except Exception as e:
            raise Exception(f"Failed to update test case {test_case_id}: {str(e)}")
    
    def delete(self, test_case_id: str) -> bool:
        """Delete test case"""
        try:
            query = f"DELETE FROM {self.table_name} WHERE test_case_id = '{test_case_id}'"
            result = self.database_service.execute_query(query, "default")
            return result.get("success", False)
        except Exception as e:
            raise Exception(f"Failed to delete test case {test_case_id}: {str(e)}")
