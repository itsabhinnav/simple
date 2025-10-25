#!/usr/bin/env python3
"""
Simple Test Runner for Sakura Backend

This script provides an easy way to run the comprehensive test suite
with coverage reporting.
"""

import sys
import os
import subprocess
from pathlib import Path

def main():
    """Main test runner function"""
    print("🧪 Sakura Backend Test Suite")
    print("=" * 50)
    
    # Check if we're in the right directory
    if not Path("src").exists():
        print("❌ Error: Please run this script from the backend directory")
        print("   Expected to find 'src' directory")
        sys.exit(1)
    
    # Check if tests directory exists
    if not Path("tests").exists():
        print("❌ Error: Tests directory not found")
        print("   Please ensure tests are properly set up")
        sys.exit(1)
    
    # Install test dependencies if needed
    print("📦 Checking test dependencies...")
    try:
        import pytest
        import coverage
        print("✅ Test dependencies found")
    except ImportError:
        print("📥 Installing test dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements-test.txt"], check=True)
        print("✅ Test dependencies installed")
    
    # Run tests with coverage
    print("\n🚀 Running tests with coverage...")
    print("-" * 50)
    
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=src",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "--cov-report=xml:coverage.xml",
        "--cov-fail-under=100"
    ]
    
    try:
        result = subprocess.run(cmd, check=True)
        
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("📊 Coverage reports generated:")
        print("   - Terminal: Coverage summary above")
        print("   - HTML: htmlcov/index.html")
        print("   - XML: coverage.xml")
        print("=" * 50)
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 50)
        print("❌ TESTS FAILED!")
        print(f"Exit code: {e.returncode}")
        print("Check the output above for details")
        print("=" * 50)
        
        return e.returncode
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
