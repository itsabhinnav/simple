#!/usr/bin/env python3
"""
Minimal Flask test for hybrid database system
"""

import sys
import os
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_flask_app():
    """Test Flask app creation and startup"""
    try:
        print("Testing Flask app...")
        
        # Test app creation
        from main import create_app
        app = create_app()
        print("✅ Flask app created successfully")
        
        # Test hybrid service initialization
        from src.infrastructure.dependency_injection import get_hybrid_database_service
        hybrid_service = get_hybrid_database_service()
        
        if hybrid_service.initialize():
            print("✅ Hybrid database service initialized")
        else:
            print("❌ Failed to initialize hybrid database service")
            return False
        
        # Test app configuration
        print(f"✅ App debug mode: {app.debug}")
        print(f"✅ App testing: {app.testing}")
        
        # Test routes
        with app.test_client() as client:
            response = client.get('/health')
            if response.status_code == 200:
                print("✅ Health endpoint working")
            else:
                print(f"❌ Health endpoint failed: {response.status_code}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_flask_app()
    if success:
        print("\n🎉 Flask app test completed successfully!")
    else:
        print("\n💥 Flask app test failed!")
        sys.exit(1)
