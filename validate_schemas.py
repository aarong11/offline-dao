#!/usr/bin/env python3
"""
JSON Schema Validator

This script validates all JSON schema files in the specified directory to ensure they:
1. Are syntactically valid JSON
2. Conform to the JSON Schema specification
3. Have correct references to other schemas
4. Maintain consistent naming patterns
5. Include all required fields

Usage:
    python validate_schemas.py [directory]

If directory is not specified, it defaults to ./schemas/
"""

import json
import os
import sys
import re
from pathlib import Path
from urllib.parse import urlparse
import jsonschema

# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.OKCYAN}ℹ {msg}{Colors.ENDC}")

def check_schema_basics(schema_path, schema):
    """Verify basic schema requirements."""
    issues = []
    
    # Check for $schema
    if "$schema" not in schema:
        issues.append(f"Missing $schema field in {schema_path}")
    
    # Check for $id
    if "$id" not in schema:
        issues.append(f"Missing $id field in {schema_path}")
    else:
        # Ensure $id matches filename pattern
        filename = os.path.basename(schema_path)
        expected_id_suffix = filename
        if not schema["$id"].endswith(filename):
            issues.append(f"$id {schema['$id']} does not match filename {filename}")
    
    # Check for title and description
    if "title" not in schema:
        issues.append(f"Missing title in {schema_path}")
    
    if "description" not in schema:
        issues.append(f"Missing description in {schema_path}")
    
    return issues

def validate_references(schema_path, schema, all_schemas):
    """Validate schema references to ensure they point to existing files."""
    issues = []
    schema_dir = os.path.dirname(schema_path)
    
    def check_refs(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "$ref" and isinstance(value, str):
                    # Handle internal reference
                    if value.startswith("#"):
                        # Internal reference within the same schema, no need to check
                        continue
                    
                    # Check for absolute URI reference
                    if urlparse(value).scheme:
                        # It's a URL, skip validation
                        continue
                    
                    # Check for relative path reference
                    ref_path = os.path.normpath(os.path.join(schema_dir, value))
                    if not os.path.exists(ref_path):
                        issues.append(f"Reference {value} in {schema_path}{path} points to non-existent file")
                else:
                    check_refs(value, f"{path}.{key}" if path else key)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                check_refs(item, f"{path}[{i}]")
    
    check_refs(schema)
    return issues

def validate_schema_against_metaschema(schema, schema_path):
    """Validate the schema against the JSON Schema meta-schema."""
    try:
        # Check which version of JSON Schema is being used
        schema_version = schema.get("$schema")
        if not schema_version:
            return ["No $schema specified"]
        
        # Use the jsonschema library to validate
        try:
            jsonschema.validators.validator_for(schema)(schema)
            return []
        except jsonschema.exceptions.SchemaError as e:
            return [f"Schema validation error in {schema_path}: {e}"]
    except Exception as e:
        return [f"Error validating {schema_path}: {e}"]

def validate_schema_file(schema_path, all_schemas):
    """Validate a single schema file."""
    try:
        with open(schema_path, 'r') as f:
            schema = json.load(f)
        
        issues = []
        
        # Check basic structure
        issues.extend(check_schema_basics(schema_path, schema))
        
        # Validate against meta-schema
        issues.extend(validate_schema_against_metaschema(schema, schema_path))
        
        # Validate references
        issues.extend(validate_references(schema_path, schema, all_schemas))
        
        return issues
    
    except json.JSONDecodeError as e:
        return [f"Invalid JSON in {schema_path}: {e}"]
    except Exception as e:
        return [f"Error processing {schema_path}: {e}"]

def find_all_schemas(schema_dir):
    """Find all JSON Schema files in the directory and subdirectories."""
    schema_files = []
    for root, _, files in os.walk(schema_dir):
        for file in files:
            if file.endswith('.schema.json'):
                schema_files.append(os.path.join(root, file))
    return schema_files

def main():
    # Determine schema directory
    if len(sys.argv) > 1:
        schema_dir = sys.argv[1]
    else:
        schema_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schemas')
    
    print_info(f"Validating schemas in {schema_dir}...")
    
    # Find all schema files
    schema_files = find_all_schemas(schema_dir)
    if not schema_files:
        print_error(f"No schema files found in {schema_dir}")
        return 1
    
    print_info(f"Found {len(schema_files)} schema files")
    
    # Dictionary to store all schemas for reference validation
    all_schemas = {}
    for schema_path in schema_files:
        try:
            with open(schema_path, 'r') as f:
                all_schemas[schema_path] = json.load(f)
        except json.JSONDecodeError:
            # Skip invalid JSON files for now, they'll be caught during validation
            pass
    
    # Validate all schema files
    all_issues = {}
    for schema_path in schema_files:
        issues = validate_schema_file(schema_path, all_schemas)
        if issues:
            all_issues[schema_path] = issues
    
    # Print validation results
    if all_issues:
        print_error(f"\nFound issues in {len(all_issues)} schema files:")
        for schema_path, issues in all_issues.items():
            print_error(f"\n{os.path.basename(schema_path)}:")
            for issue in issues:
                print_error(f"  - {issue}")
        return 1
    else:
        print_success(f"\nAll {len(schema_files)} schema files are valid!")
        return 0

if __name__ == "__main__":
    sys.exit(main())