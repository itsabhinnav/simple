#!/usr/bin/env python3
"""
Add 1000 Requirements via Backend API

This script creates 1000 requirements by calling the backend API.
"""

import requests
import random
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# API base URL
API_BASE_URL = "http://localhost:5000/api"

# Sample data
features = [
    "Authentication", "Authorization", "Dashboard", "User Profile", "Notifications",
    "Search", "Filtering", "Export", "Import", "Reporting", "Analytics", "Billing",
    "Payment", "Checkout", "Cart", "Catalog", "Inventory", "Orders", "Shipping",
    "Delivery", "Tracking", "Returns", "Refunds", "Reviews", "Ratings", "Security",
    "Audit", "Compliance", "Backup", "Recovery"
]

priority_levels = ["P1", "P2", "P3", "P4"]
statuses = ["Draft", "Approved", "Implemented", "Tested", "Closed"]
assignees = ["John Doe", "Jane Smith", "Alice Johnson", "Bob Wilson", "Sarah Brown", "Mike Davis"]
tags = ["feature", "enhancement", "bug", "security", "performance", "ui", "backend", "api", "integration"]

sample_givens = [
    "User has valid account credentials",
    "User is logged into the system",
    "User has required permissions",
    "Database is properly initialized",
    "Network connection is available",
    "System is in stable state",
    "Required hardware is connected",
    "Required modules are loaded",
    "Test data is available",
    "Environment is properly configured"
]

sample_whens = [
    "User clicks the submit button",
    "User enters valid credentials and clicks login",
    "User navigates to the settings page",
    "User selects the export option",
    "User fills out the form and submits",
    "User clicks the delete button",
    "User updates the configuration",
    "User selects a filter option",
    "User initiates the process",
    "User completes the workflow"
]

sample_thens = [
    "User should be redirected to the dashboard",
    "Success message should be displayed",
    "Record should be created successfully",
    "Data should be saved to database",
    "User should receive confirmation",
    "System should process the request",
    "Changes should be applied immediately",
    "Status should be updated correctly",
    "Notification should be sent",
    "Expected behavior should occur"
]

sample_descriptions = [
    "Implement feature for user to be able to perform the operation",
    "Add functionality to support the workflow",
    "Create interface for managing the resources",
    "Develop system to handle the requirements",
    "Build feature to improve user experience",
    "Enhance existing functionality with new capabilities",
    "Implement security measures for data protection",
    "Add validation to ensure data integrity",
    "Create reporting mechanism for analytics",
    "Develop integration with external systems"
]

def generate_requirement(index):
    """Generate a realistic requirement"""
    feature = random.choice(features)
    
    requirement_types = ["Functional", "HMI", "Safety", "Performance", "Usability"]
    
    return {
        "requirement_id": f"REQ-{feature.upper().replace(' ', '_')}-{index:04d}",
        "title": f"{feature} - Requirement {index}",
        "description": random.choice(sample_descriptions),
        "requirement_type": random.choice(requirement_types),
        "given": random.choice(sample_givens),
        "when_action": random.choice(sample_whens),
        "then_result": random.choice(sample_thens),
        "priority": random.choice(priority_levels),
        "status": random.choice(statuses),
        "assignee": random.choice(assignees),
        "tags": ", ".join(random.sample(tags, random.randint(1, 3)))
    }

def check_api_health():
    """Check if the API is available"""
    try:
        logging.info(f"Checking API health at: {API_BASE_URL}/../health")
        response = requests.get(f"{API_BASE_URL}/../health", timeout=10)
        logging.info(f"Health check response: {response.status_code}")
        if response.status_code == 200:
            logging.info("API health check passed")
            return True
        else:
            logging.warning(f"API health check failed with status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Cannot connect to API: {e}")
        return False
    except Exception as e:
        logging.error(f"Error during health check: {e}")
        return False

def create_requirement_via_api(requirement_data):
    """Create a requirement via the API"""
    try:
        logging.debug(f"Creating requirement: {requirement_data.get('requirement_id')}")
        response = requests.post(
            f"{API_BASE_URL}/requirements",
            json=requirement_data,
            timeout=30
        )
        
        logging.debug(f"Response status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            logging.debug(f"Response data: {result}")
            if result.get('success'):
                logging.debug(f"Successfully created requirement: {requirement_data.get('requirement_id')}")
                return True, None
            else:
                error_msg = result.get('error') or result.get('message', 'Unknown error')
                logging.warning(f"Failed to create requirement {requirement_data.get('requirement_id')}: {error_msg}")
                return False, error_msg
        else:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            error_msg = f"HTTP {response.status_code}: {error_data.get('message', error_data.get('error', 'Unknown error'))}"
            logging.warning(f"Request failed for {requirement_data.get('requirement_id')}: {error_msg}")
            return False, error_msg
    
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Cannot connect to backend API: {e}")
        return False, f"Cannot connect to backend API: {e}"
    except requests.exceptions.Timeout as e:
        logging.error(f"Request timeout: {e}")
        return False, f"Request timeout: {e}"
    except Exception as e:
        logging.error(f"Unexpected error creating requirement: {e}")
        return False, str(e)

def main():
    print("\n" + "="*70)
    print("  Adding 10 Requirements via Backend API")
    print("="*70 + "\n")
    
    # Check API health
    print("Checking API health...")
    if not check_api_health():
        print("❌ Backend API is not available!")
        print(f"   Please ensure the backend is running at {API_BASE_URL.replace('/api', '')}")
        print("   You can start it with: cd backend && python main.py")
        return 1
    
    print("✓ Backend API is running\n")
    
    print("Creating 10 requirements via API...")
    
    success_count = 0
    error_count = 0
    errors = []
    
    for i in range(1, 11):
        requirement = generate_requirement(i)
        success, error = create_requirement_via_api(requirement)
        
        if success:
            success_count += 1
        else:
            error_count += 1
            errors.append((requirement['requirement_id'], error))
        
        # Progress indicator
        logging.info(f"  Progress: {i}/10 requirements ({success_count} success, {error_count} errors)...")
    
    print(f"\n[OK] Created {success_count} requirements successfully")
    if error_count > 0:
        print(f"[ERROR] Failed to create {error_count} requirements")
        if errors and len(errors) <= 10:
            print("\nSample errors:")
            for req_id, error in errors[:10]:
                print(f"  {req_id}: {error}")
    
    # Verify count via API
    try:
        response = requests.get(f"{API_BASE_URL}/requirements", timeout=5)
        if response.status_code == 200:
            data = response.json()
            count = data.get('count', len(data.get('data', [])))
            print(f"\nTotal requirements in database: {count}")
    except Exception as e:
        print(f"\nCould not verify count: {e}")
    
    print("\n" + "="*70)
    print("  Complete!")
    print("="*70 + "\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

