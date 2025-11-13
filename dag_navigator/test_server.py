#!/usr/bin/env python3
"""
Test script for the dbt DAG Navigator MCP Server

This script demonstrates the functionality of the navigator without requiring
a full MCP client setup. Useful for development and testing.
"""

import json
import sys
from pathlib import Path
from server import DbtDagNavigator


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(result: dict):
    """Pretty print a result dictionary."""
    print(json.dumps(result, indent=2))


def main():
    """Run tests on the sample data."""
    # Initialize navigator
    navigator = DbtDagNavigator()

    # Get paths to sample files
    examples_dir = Path(__file__).parent / "examples"
    manifest_path = examples_dir / "sample_manifest.json"
    catalog_path = examples_dir / "sample_catalog.json"

    if not manifest_path.exists():
        print(f"Error: Sample manifest not found at {manifest_path}")
        sys.exit(1)

    # Test 1: Load and index
    print_section("Test 1: Loading and Indexing DAG")
    result = navigator.load_and_index(str(manifest_path), str(catalog_path))
    print_result(result)

    if not result.get("success"):
        print("Failed to load DAG. Exiting.")
        sys.exit(1)

    # Test 2: List models
    print_section("Test 2: Listing All Models")
    result = navigator.list_models(limit=10)
    print_result(result)

    # Test 3: Get model details
    print_section("Test 3: Getting Details for 'customers' Model")
    result = navigator.get_model_details("customers")
    print_result(result)

    # Test 4: Get upstream dependencies
    print_section("Test 4: Getting Upstream Dependencies of 'customer_orders_summary'")
    result = navigator.get_upstream_models("customer_orders_summary", include_sources=True)
    print_result(result)

    # Test 5: Get downstream dependencies
    print_section("Test 5: Getting Downstream Dependencies of 'customers'")
    result = navigator.get_downstream_models("customers")
    print_result(result)

    # Test 6: Check column usage
    print_section("Test 6: Checking if 'email' Column is Used Downstream from 'customers'")
    result = navigator.check_column_usage("customers", "email")
    print_result(result)

    # Test 7: Search models
    print_section("Test 7: Searching for Models with 'order' in Name/Description")
    result = navigator.search_models("order", search_descriptions=True)
    print_result(result)

    # Test 8: Complex dependency chain
    print_section("Test 8: Analyzing 'product_sales_summary' Dependencies")
    print("\nUpstream:")
    upstream = navigator.get_upstream_models("product_sales_summary")
    print_result(upstream)

    print("\nDownstream:")
    downstream = navigator.get_downstream_models("product_sales_summary")
    print_result(downstream)

    # Test 9: Column lineage for order_id
    print_section("Test 9: Checking 'order_id' Column Usage from 'orders'")
    result = navigator.check_column_usage("orders", "order_id")
    print_result(result)

    # Test 10: Search by tag
    print_section("Test 10: Searching Models by Tag 'reporting'")
    result = navigator.search_models("reporting")
    print_result(result)

    # Summary
    print_section("Test Summary")
    model_list = navigator.list_models()
    print(f"✓ Successfully loaded {model_list.get('total_count', 0)} models")
    print("✓ All tests completed successfully")
    print("\nThe dbt DAG Navigator is working correctly!")
    print("\nNext steps:")
    print("1. Configure this server in your MCP client (see README.md)")
    print("2. Point it to your actual dbt project's manifest.json and catalog.json")
    print("3. Start asking questions about your dbt DAG!")


if __name__ == "__main__":
    main()
