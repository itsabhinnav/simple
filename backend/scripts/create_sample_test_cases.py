#!/usr/bin/env python3
"""
Create Sample Test Cases

This script generates 2000 sample test cases and inserts them into the database.
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime
import random

# Resolve path relative to backend directory
backend_dir = Path(__file__).parent.parent
db_path = backend_dir / "data" / "local" / "dev" / "database" / "local.db"

if not db_path.exists():
    # Try alternative path
    db_path = backend_dir / "data" / "local" / "dev" / "database" / "sakura_db.db"

if not db_path.exists():
    print(f"Database not found!")
    print(f"Tried: {db_path}")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Test case templates and data pools
features = [
    "Authentication", "Dashboard", "User Management", "Permissions", "Settings",
    "Profile", "Notifications", "Search", "Filtering", "Export",
    "Import", "Reporting", "Analytics", "Billing", "Payment",
    "Checkout", "Cart", "Catalog", "Inventory", "Orders",
    "Shipping", "Delivery", "Tracking", "Returns", "Refunds",
    "Reviews", "Ratings", "Recommendations", "Wishlist", "Compare"
]

test_types = ["Positive", "Negative", "Boundary", "Performance"]
regions = ["NA", "EU", "APAC", "ME", "LATAM"]
brands = ["BrandA", "BrandB", "BrandC", "BrandD"]
vehicle_variants = ["Standard", "Premium", "Deluxe", "Enterprise"]
priorities = ["P1", "P2", "P3"]
testsuite_types = ["Smoke", "Regression", "Sanity", "End-to-End"]

sample_test_objectives = [
    "Verify user can successfully log in with valid credentials",
    "Verify user receives error message for invalid credentials",
    "Verify session timeout after 30 minutes of inactivity",
    "Verify user can reset password using email",
    "Verify user can update profile information",
    "Verify dashboard displays correct user data",
    "Verify user can create new record",
    "Verify user can edit existing record",
    "Verify user can delete record",
    "Verify user can search records by keyword",
    "Verify user can filter records by category",
    "Verify user can sort records by date",
    "Verify user can export data to CSV",
    "Verify user can import data from file",
    "Verify validation errors display correctly",
    "Verify API returns correct status codes",
    "Verify responsive design works on mobile",
    "Verify accessibility features are available",
    "Verify performance under load",
    "Verify security controls are enforced"
]

sample_preconditions = [
    "User is logged in",
    "User has admin privileges",
    "Database is initialized",
    "Test data is available",
    "Network connection is active",
    "Browser is on latest version",
    "Required permissions are granted",
    "Required modules are loaded",
    "System is in stable state",
    "No pending operations are running"
]

sample_procedures = [
    "Navigate to login page",
    "Enter username and password",
    "Click the submit button",
    "Verify redirect to dashboard",
    "Navigate to settings page",
    "Update configuration values",
    "Save changes",
    "Verify changes are persisted",
    "Navigate to user profile",
    "Update profile information",
    "Click save button",
    "Logout and login again",
    "Navigate to reports section",
    "Select date range",
    "Generate report",
    "Verify report data accuracy"
]

sample_expected_behaviors = [
    "User should be redirected to dashboard",
    "Error message should be displayed",
    "Success message should appear",
    "Record should be created",
    "Record should be updated",
    "Record should be deleted",
    "Validation error should be shown",
    "Confirmation dialog should appear",
    "Data should be loaded correctly",
    "Progress bar should be visible"
]

def generate_test_case_id(index, used_ids, feature):
    """Generate test case ID in format: TC_FEATURE_XXXX"""
    # Generate a unique ID by combining feature with index and a random component
    random_suffix = random.randint(10000, 99999)
    test_case_id = f"TC_{feature}_{index:05d}_{random_suffix}"
    
    # Ensure uniqueness
    while test_case_id in used_ids:
        random_suffix = random.randint(10000, 99999)
        test_case_id = f"TC_{feature}_{index:05d}_{random_suffix}"
    
    used_ids.add(test_case_id)
    return test_case_id

def generate_test_case(index, used_ids):
    """Generate a single test case with random but valid data"""
    # Use index to cycle through features for diversity
    feature = features[index % len(features)]
    test_case_id = generate_test_case_id(index, used_ids, feature)
    
    return {
        'test_case_id': test_case_id,
        'reference_document': f"DOC-{random.randint(100, 999)}",
        'associated_requirement_id': f"REQ-{random.randint(1, 100):03d}",
        'screen_id': f"SCREEN-{random.randint(1, 50)}",
        'feature': feature,
        'dr_applicable_screens': f"Screen{random.randint(1, 20)}",
        'dr_id': f"DR-{random.randint(1, 100)}",
        'test_objective': random.choice(sample_test_objectives),
        'preconditions': random.choice(sample_preconditions),
        'procedure': ". ".join(random.sample(sample_procedures, random.randint(3, 7))),
        'expected_behavior': random.choice(sample_expected_behaviors),
        'test_type': random.choice(test_types),
        'region': random.choice(regions),
        'brand': random.choice(brands),
        'vehicle_variant': random.choice(vehicle_variants),
        'vehicle_specification': f"Spec-{random.randint(100, 999)}",
        'env_dependency': random.choice(["Prod", "Test", "Dev", "Staging"]),
        'requirement_type': random.choice(["Functional", "Non-Functional", "Security"]),
        'regulation': f"REG-{random.randint(1, 20)}",
        'priority': random.choice(priorities),
        'testsuite_type': random.choice(testsuite_types),
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    }

def insert_test_case(cursor, test_case):
    """Insert a test case into the database"""
    try:
        cursor.execute("""
            INSERT INTO test_cases (
                test_case_id, reference_document, associated_requirement_id, screen_id,
                feature, dr_applicable_screens, dr_id, test_objective, preconditions,
                procedure, expected_behavior, test_type, region, brand, vehicle_variant,
                vehicle_specification, env_dependency, requirement_type, regulation,
                priority, testsuite_type, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_case['test_case_id'],
            test_case['reference_document'],
            test_case['associated_requirement_id'],
            test_case['screen_id'],
            test_case['feature'],
            test_case['dr_applicable_screens'],
            test_case['dr_id'],
            test_case['test_objective'],
            test_case['preconditions'],
            test_case['procedure'],
            test_case['expected_behavior'],
            test_case['test_type'],
            test_case['region'],
            test_case['brand'],
            test_case['vehicle_variant'],
            test_case['vehicle_specification'],
            test_case['env_dependency'],
            test_case['requirement_type'],
            test_case['regulation'],
            test_case['priority'],
            test_case['testsuite_type'],
            test_case['created_at'],
            test_case['updated_at']
        ))
        return True
    except sqlite3.IntegrityError as e:
        # Test case ID already exists, skip it
        return False
    except Exception as e:
        print(f"Error inserting test case {test_case['test_case_id']}: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("  Creating 2000 Sample Test Cases")
    print("="*60 + "\n")
    
    try:
        # Get current count
        cursor.execute("SELECT COUNT(*) FROM test_cases")
        current_count = cursor.fetchone()[0]
        print(f"Current test cases in database: {current_count}\n")
        
        target_count = 2000
        created = 0
        skipped = 0
        
        # Generate and insert test cases
        print("Generating test cases...")
        used_ids = set()
        for i in range(1, target_count + 1):
            test_case = generate_test_case(i, used_ids)
            
            if insert_test_case(cursor, test_case):
                created += 1
                if i % 100 == 0:
                    print(f"  Created {i}/{target_count} test cases...")
                    conn.commit()  # Commit in batches
            else:
                skipped += 1
        
        # Final commit
        conn.commit()
        
        print(f"\n[OK] Successfully created {created} test cases")
        if skipped > 0:
            print(f"[INFO] Skipped {skipped} duplicate test cases")
        
        # Get final count
        cursor.execute("SELECT COUNT(*) FROM test_cases")
        final_count = cursor.fetchone()[0]
        print(f"\nTotal test cases in database: {final_count}")
        
        # Show distribution by feature
        print("\nDistribution by feature:")
        cursor.execute("""
            SELECT feature, COUNT(*) as count 
            FROM test_cases 
            GROUP BY feature 
            ORDER BY count DESC 
            LIMIT 10
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")
        
        print("\n" + "="*60)
        print("  Sample Test Cases Creation Complete!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()

