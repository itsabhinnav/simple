#!/usr/bin/env python3
"""
Test script for hybrid database system
"""

import sys
import os
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_hybrid_database():
    """Test the hybrid database system"""
    try:
        print("Testing hybrid database system...")
        
        # Test imports
        from src.infrastructure.dependency_injection import get_hybrid_database_service
        print("✅ Imports successful")
        
        # Get hybrid service
        hybrid_service = get_hybrid_database_service()
        print("✅ Hybrid service created")
        
        # Test initialization
        if hybrid_service.initialize():
            print("✅ Hybrid database service initialized successfully")
            
            # Test sync status
            status = hybrid_service.get_sync_status()
            print(f"✅ Sync status: {status}")
            
            # Test local database
            local_service = hybrid_service.local_db
            print(f"✅ Local database path: {local_service.local_db_path}")
            
            # Test remote database
            remote_service = hybrid_service.remote_db
            print(f"✅ Remote database service available")
            
            return True
        else:
            print("❌ Failed to initialize hybrid database service")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_hybrid_database()
    if success:
        print("\n🎉 Hybrid database system test completed successfully!")
    else:
        print("\n💥 Hybrid database system test failed!")
        sys.exit(1)
