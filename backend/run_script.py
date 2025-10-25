#!/usr/bin/env python3
"""
Script Runner

This script provides easy access to all utility scripts from the project root.
"""

import os
import sys
import argparse
from pathlib import Path

# Script categories and their available scripts
SCRIPTS = {
    'database': {
        'init': 'scripts/database/init_database.py',
        'sync': 'scripts/database/sync_database.py',
        'check': 'scripts/database/check_database_content.py'
    },
    'testing': {
        'comprehensive': 'scripts/testing/comprehensive_test.py',
        'database-service': 'scripts/testing/test_database_service.py'
    },
    'config': {
        'test': 'scripts/config/test_configuration.py',
        'test-loading': 'scripts/config/test_config_loading.py',
        'demo': 'scripts/config/demo_configuration.py'
    },
    'utils': {
        'status': 'scripts/utils/final_status_check.py'
    }
}

def list_scripts():
    """List all available scripts"""
    print("📋 Available Scripts:")
    print("=" * 50)
    
    for category, scripts in SCRIPTS.items():
        print(f"\n📁 {category.upper()}:")
        for name, path in scripts.items():
            print(f"  - {name}: {path}")

def run_script(category, script_name):
    """Run a specific script"""
    if category not in SCRIPTS:
        print(f"❌ Unknown category: {category}")
        print("Available categories:", list(SCRIPTS.keys()))
        return 1
    
    if script_name not in SCRIPTS[category]:
        print(f"❌ Unknown script: {script_name}")
        print(f"Available scripts in {category}:", list(SCRIPTS[category].keys()))
        return 1
    
    script_path = SCRIPTS[category][script_name]
    
    if not Path(script_path).exists():
        print(f"❌ Script not found: {script_path}")
        return 1
    
    print(f"🚀 Running: {script_path}")
    print("=" * 50)
    
    # Run the script
    os.system(f"python {script_path}")
    return 0

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Run Sakura utility scripts')
    parser.add_argument('category', nargs='?', help='Script category')
    parser.add_argument('script', nargs='?', help='Script name')
    parser.add_argument('--list', '-l', action='store_true', help='List all available scripts')
    
    args = parser.parse_args()
    
    if args.list or (not args.category and not args.script):
        list_scripts()
        return 0
    
    if not args.category or not args.script:
        print("❌ Both category and script name are required")
        print("Use --list to see available scripts")
        return 1
    
    return run_script(args.category, args.script)

if __name__ == "__main__":
    sys.exit(main())
