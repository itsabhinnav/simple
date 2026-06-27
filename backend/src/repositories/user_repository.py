from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from src.schemas.user_schema import UserSchema, UserCreateSchema, UserUpdateSchema


class IUserRepository(ABC):
    """Interface for user data access operations"""
    
    @abstractmethod
    def find_all(self) -> List[Dict[str, Any]]:
        """Get all users"""
        pass
    
    @abstractmethod
    def find_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        pass
    
    @abstractmethod
    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        pass
    
    @abstractmethod
    def create(self, user_data: UserCreateSchema) -> Dict[str, Any]:
        """Create a new user"""
        pass
    
    @abstractmethod
    def update(self, user_id: int, user_data: UserUpdateSchema) -> Optional[Dict[str, Any]]:
        """Update user data"""
        pass
    
    @abstractmethod
    def delete(self, user_id: int) -> bool:
        """Delete user"""
        pass


class UserRepository(IUserRepository):
    """Concrete implementation of user repository"""
    
    def __init__(self, database_service, table_name: str = "users"):
        self.database_service = database_service
        self.table_name = table_name
    
    def find_all(self) -> List[Dict[str, Any]]:
        """Get all users from database"""
        try:
            result = self.database_service.execute_query(
                f"SELECT * FROM {self.table_name} ORDER BY id",
                "default"
            )
            return result.get('data', [])
        except Exception as e:
            raise Exception(f"Failed to fetch users: {str(e)}")
    
    def find_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            # Sanitize user_id to prevent SQL injection
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError("Invalid user ID")
            
            result = self.database_service.execute_query(
                f"SELECT * FROM {self.table_name} WHERE id = {user_id}",
                "default"
            )
            users = result.get('data', [])
            return users[0] if users else None
        except Exception as e:
            raise Exception(f"Failed to fetch user {user_id}: {str(e)}")
    
    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        try:
            # Sanitize username to prevent SQL injection
            if not isinstance(username, str) or not username.strip():
                raise ValueError("Invalid username")
            
            # Escape single quotes in username
            escaped_username = username.replace("'", "''")
            
            result = self.database_service.execute_query(
                f"SELECT * FROM {self.table_name} WHERE username = '{escaped_username}'",
                "default"
            )
            users = result.get('data', [])
            return users[0] if users else None
        except Exception as e:
            raise Exception(f"Failed to fetch user {username}: {str(e)}")
    
    def create(self, user_data: Union[UserCreateSchema, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Create a new user"""
        try:
            if isinstance(user_data, dict):
                user_dict = user_data.copy()
            elif hasattr(user_data, "model_dump"):
                user_dict = user_data.model_dump()
            else:
                user_dict = user_data.dict()
            
            filtered_dict = {k: v for k, v in user_dict.items() if v is not None}
            
            if not filtered_dict:
                return None
            
            sanitized_dict = {}
            for key, value in filtered_dict.items():
                if isinstance(value, str):
                    sanitized_dict[key] = value.replace("'", "''")
                else:
                    sanitized_dict[key] = value
            
            columns = ', '.join(sanitized_dict.keys())
            values = ', '.join([f"'{v}'" if isinstance(v, str) else str(v) for v in sanitized_dict.values()])

            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({values})"
            result = self.database_service.execute_query(query, "default")
            
            if not result.get("success"):
                return None
            
            created_user = user_dict.copy()
            created_user['id'] = result.get('lastrowid', None)
            created_user['created_at'] = result.get('created_at', None)
            created_user['updated_at'] = result.get('updated_at', None)
            
            return created_user
        except Exception:
            return None
    
    def update(self, user_id: int, user_data: Union[UserUpdateSchema, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Update user data"""
        try:
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError("Invalid user ID")

            if isinstance(user_data, dict):
                user_dict = user_data.copy()
            elif hasattr(user_data, "model_dump"):
                user_dict = user_data.model_dump(exclude_unset=True)
            else:
                user_dict = user_data.dict(exclude_unset=True)

            if not user_dict:
                return None
            
            sanitized_dict = {}
            for key, value in user_dict.items():
                if isinstance(value, str):
                    sanitized_dict[key] = value.replace("'", "''")
                else:
                    sanitized_dict[key] = value
            
            set_clause = ', '.join([f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}" 
                                  for k, v in sanitized_dict.items()])
            
            query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = {user_id}"
            result = self.database_service.execute_query(query, "default")
            
            if not result.get("success"):
                return None
            if result.get("row_count", 1) == 0:
                return None

            return {**user_dict, "id": user_id}
        except Exception:
            return None
    
    def delete(self, user_id: int) -> bool:
        """Delete user"""
        try:
            # Sanitize user_id to prevent SQL injection
            if not isinstance(user_id, int) or user_id <= 0:
                raise ValueError("Invalid user ID")
            
            query = f"DELETE FROM {self.table_name} WHERE id = {user_id}"
            result = self.database_service.execute_query(query, "default")
            if not result.get("success", False):
                return False
            return result.get("row_count", 1) > 0
        except Exception as e:
            raise Exception(f"Failed to delete user {user_id}: {str(e)}")
