#!/usr/bin/env python3
"""
Initialize Great Expectations programmatically since CLI is not working
"""

import os

import great_expectations as gx


def init_great_expectations():
    """Initialize Great Expectations project"""
    try:
        # Get current directory
        project_root = os.getcwd()
        print(f"Initializing Great Expectations in: {project_root}")

        # Initialize Great Expectations context
        gx.get_context()
        print("✅ Great Expectations context created successfully!")

        # Create great_expectations directory structure if it doesn't exist
        ge_dir = os.path.join(project_root, "great_expectations")
        if not os.path.exists(ge_dir):
            os.makedirs(ge_dir, exist_ok=True)
            print(f"✅ Created directory: {ge_dir}")

        print("🎉 Great Expectations initialization complete!")
        print("You can now use Great Expectations for data validation.")

    except Exception as e:
        print(f"❌ Error initializing Great Expectations: {e}")
        return False

    return True


if __name__ == "__main__":
    init_great_expectations()
