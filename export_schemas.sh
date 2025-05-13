#!/bin/bash
# filepath: /Users/a/Documents/export_schemas.sh

# export_schemas.sh - Export all JSON schema files with headers and content

# Default values
DEFAULT_DIR="$(pwd)"
SCHEMAS_DIR="/Users/a/Documents/schemas"
OUTPUT_FILE="schema_full.json"
WITH_TEXT=false
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
DATE_TODAY=$(date "+%Y-%m-%d")

# Help function
show_help() {
  echo "Usage: $0 [-o output_file] [-d schemas_directory] [-p default_directory] [--with-text] [-h]"
  echo "  -o  Output file path (default: schema_full.json)"
  echo "  -d  Directory containing schemas (default: /Users/a/Documents/schemas)"
  echo "  -p  Default directory for output if not specified (default: current directory)"
  echo "  --with-text  Include text headers and descriptions (default: false)"
  echo "  -h  Show this help message"
}

# Parse command line options
while [[ $# -gt 0 ]]; do
  case $1 in
    -o) OUTPUT_FILE="$2"; shift 2 ;;
    -d) SCHEMAS_DIR="$2"; shift 2 ;;
    -p) DEFAULT_DIR="$2"; shift 2 ;;
    --with-text) WITH_TEXT=true; shift ;;
    -h) show_help; exit 0 ;;
    -*) echo "Unknown option: $1"; show_help; exit 1 ;;
    *) break ;;
  esac
done

# Use default directory if output file doesn't include a path
if [[ ! "$OUTPUT_FILE" == */* ]]; then
  OUTPUT_FILE="$DEFAULT_DIR/$OUTPUT_FILE"
  echo "Using default directory: $OUTPUT_FILE"
fi

# Check if schemas directory exists
if [ ! -d "$SCHEMAS_DIR" ]; then
  echo "Error: Schemas directory '$SCHEMAS_DIR' not found."
  exit 1
fi

# Clear or create the output file
> "$OUTPUT_FILE"

echo "Exporting schemas from $SCHEMAS_DIR to $OUTPUT_FILE..."

if [ "$WITH_TEXT" = true ]; then
  # Text format with headers
  echo "Export started at: $TIMESTAMP" >> "$OUTPUT_FILE"
  echo "Date: $DATE_TODAY" >> "$OUTPUT_FILE"
  echo "==== SCHEMA EXPORT ====" >> "$OUTPUT_FILE"
  echo "" >> "$OUTPUT_FILE"
else
  # Start a JSON array
  echo "[" >> "$OUTPUT_FILE"
  first_file=true
fi

# Find all JSON files and process them
find "$SCHEMAS_DIR" -type f -name "*.json" | sort | while read -r file; do
  echo "Processing: $file"
  file_timestamp=$(date -r "$file" "+%Y-%m-%d %H:%M:%S")
  
  if [ "$WITH_TEXT" = true ]; then
    # Text format with headers
    # Add the file path as a header with timestamp
    echo "$file (Last Modified: $file_timestamp)" >> "$OUTPUT_FILE"
    echo "==== FILE: $file" >> "$OUTPUT_FILE"
    
    # Add the file content
    cat "$file" >> "$OUTPUT_FILE"
    
    # Add a separator
    echo -e "\n==== END OF FILE ====\n" >> "$OUTPUT_FILE"
  else
    # JSON format - Add comma before each object except the first
    if [ "$first_file" = true ]; then
      first_file=false
    else
      echo "," >> "$OUTPUT_FILE"
    fi
    
    # For JSON output, format the file content
    if command -v jq &> /dev/null; then
      # Add file metadata to the JSON content
      jq --arg file "$file" --arg timestamp "$file_timestamp" '. + {__meta: {file: $file, timestamp: $timestamp}}' "$file" >> "$OUTPUT_FILE"
    else
      # If jq is not available, output raw JSON
      cat "$file" >> "$OUTPUT_FILE"
    fi
  fi
done

if [ "$WITH_TEXT" = true ]; then
  # Add export completion timestamp for text mode
  echo "==== EXPORT COMPLETE ====" >> "$OUTPUT_FILE"
  echo "Finished at: $(date "+%Y-%m-%d %H:%M:%S")" >> "$OUTPUT_FILE"
else
  # Close the JSON array
  echo -e "\n]" >> "$OUTPUT_FILE"
fi

# Make the script executable
chmod +x "$0"

echo "✅ Schema export complete! Output saved to $OUTPUT_FILE"
echo "   Export date: $DATE_TODAY at $(date "+%H:%M:%S")"
echo "   Total files: $(find "$SCHEMAS_DIR" -type f -name "*.json" | wc -l | tr -d ' ')"
echo "   Format: $([ "$WITH_TEXT" = true ] && echo "TEXT" || echo "JSON")"