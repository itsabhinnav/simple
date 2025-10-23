from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
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
    
    def __init__(self, database_service):
        self.database_service = database_service
    
    def find_all(self) -> List[Dict[str, Any]]:
        """Get all users from database"""
        try:
            result = self.database_service.execute_query(
                "SELECT * FROM users ORDER BY id",
                "default"
            )
            return result.get('data', [])
        except Exception as e:
            raise Exception(f"Failed to fetch users: {str(e)}")
    
    def find_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            result = self.database_service.execute_query(
                f"SELECT * FROM users WHERE id = {user_id}",
                "default"
            )
            users = result.get('data', [])
            return users[0] if users else None
        except Exception as e:
            raise Exception(f"Failed to fetch user {user_id}: {str(e)}")
    
    def find_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        try:
            result = self.database_service.execute_query(
                f"SELECT * FROM users WHERE username = '{username}'",
                "default"
            )
            users = result.get('data', [])
            return users[0] if users else None
        except Exception as e:
            raise Exception(f"Failed to fetch user {username}: {str(e)}")
    
    def create(self, user_data: UserCreateSchema) -> Dict[str, Any]:
        """Create a new user"""
        try:
            # Convert schema to dict and prepare SQL
            user_dict = user_data.dict()
            columns = ', '.join(user_dict.keys())
            values = ', '.join([f"'{v}'" if isinstance(v, str) else str(v) for v in user_dict.values()])
            
            query = f"INSERT INTO users ({columns}) VALUES ({values})"
            result = self.database_service.execute_query(query, "default")
            
            # Get the created user
            return self.find_by_username(user_data.username)
        except Exception as e:
            raise Exception(f"Failed to create user: {str(e)}")
    
    def update(self, user_id: int, user_data: UserUpdateSchema) -> Optional[Dict[str, Any]]:
        """Update user data"""
        try:
            # Convert schema to dict and prepare SQL
            user_dict = user_data.dict(exclude_unset=True)
            if not user_dict:
                return self.find_by_id(user_id)
            
            set_clause = ', '.join([f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}" 
                                  for k, v in user_dict.items()])
            
            query = f"UPDATE users SET {set_clause} WHERE id = {user_id}"
            self.database_service.execute_query(query, "default")
            
            return self.find_by_id(user_id)
        except Exception as e:
            raise Exception(f"Failed to update user {user_id}: {str(e)}")
    
    def delete(self, user_id: int) -> bool:
        """Delete user"""
        try:
            query = f"DELETE FROM users WHERE id = {user_id}"
            self.database_service.execute_query(query, "default")
            return True
        except Exception as e:
            raise Exception(f"Failed to delete user {user_id}: {str(e)}")
