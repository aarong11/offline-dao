#!/bin/bash
# export_resources.sh - Export all resource schema files with optional full content dump
# Default values
DEFAULT_DIR="$(pwd)"
SCHEMAS_DIR="/Users/a/Documents/schemas/resources"
OUTPUT_FILE="resources_export.json"
FULL_EXPORT=false
WITH_TEXT=false
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
DATE_TODAY=$(date "+%Y-%m-%d")

# Help function
show_help() {
  echo "Usage: $0 [-o output_file] [-d schemas_directory] [-p default_directory] [--full] [--with-text] [-h]"
  echo "  -o  Output file path (default: resources_export.json)"
  echo "  -d  Directory containing resource schemas (default: /Users/a/Documents/schemas/resources)"
  echo "  -p  Default directory for output if not specified (default: current directory)"
  echo "  --full  Include full schema content in the export (default: false)"
  echo "  --with-text  Include text headers and descriptions (default: false)"
  echo "  -h  Show this help message"
}

# Parse command line options
while [[ $# -gt 0 ]]; do
  case $1 in
    -o) OUTPUT_FILE="$2"; shift 2 ;;
    -d) SCHEMAS_DIR="$2"; shift 2 ;;
    -p) DEFAULT_DIR="$2"; shift 2 ;;
    --full) FULL_EXPORT=true; shift ;;
    --with-text) WITH_TEXT=true; shift ;;
    -h) show_help; exit 0 ;;
    *) show_help; exit 1 ;;
  esac
done

# Use default directory if output file doesn't include a path
if [[ ! "$OUTPUT_FILE" == */* ]]; then
  OUTPUT_FILE="$DEFAULT_DIR/$OUTPUT_FILE"
  echo "Using default directory: $OUTPUT_FILE"
fi

# Check if schemas directory exists
if [ ! -d "$SCHEMAS_DIR" ]; then
  echo "Error: Resource schemas directory '$SCHEMAS_DIR' not found."
  exit 1
fi

# Clear or create the output file
> "$OUTPUT_FILE"

# Start JSON output
if [ "$WITH_TEXT" = true ]; then
  echo "Exporting resource schemas from $SCHEMAS_DIR to $OUTPUT_FILE..."
  echo "Export started at: $TIMESTAMP" >> "$OUTPUT_FILE"
  echo "Date: $DATE_TODAY" >> "$OUTPUT_FILE"
  echo "==== RESOURCE SCHEMAS EXPORT ====" >> "$OUTPUT_FILE"
  echo "" >> "$OUTPUT_FILE"
else
  # Start a JSON array
  echo "[" >> "$OUTPUT_FILE"
  first_file=true
fi

# Find all resource JSON schema files and process them
find "$SCHEMAS_DIR" -type f -name "*.schema.json" | sort | while read -r file; do
  echo "Processing: $file"
  file_timestamp=$(date -r "$file" "+%Y-%m-%d %H:%M:%S")
  
  if [ "$WITH_TEXT" = true ]; then
    # Text-based output with headers and descriptions
    if command -v jq &> /dev/null; then
      title=$(jq -r '.title // "No title"' "$file")
      description=$(jq -r '.description // "No description"' "$file")
      
      # Add the file info with title and description
      echo "$file (Last Modified: $file_timestamp)" >> "$OUTPUT_FILE"
      echo "Title: $title" >> "$OUTPUT_FILE"
      echo "Description: $description" >> "$OUTPUT_FILE"
      
      # If full export is requested, include the complete schema content
      if [ "$FULL_EXPORT" = true ]; then
        echo "==== FILE CONTENT: $file" >> "$OUTPUT_FILE"
        cat "$file" >> "$OUTPUT_FILE"
        echo -e "\n==== END OF FILE CONTENT ====\n" >> "$OUTPUT_FILE"
      else
        # Just list the top-level properties if not full export
        echo "Top-level properties:" >> "$OUTPUT_FILE"
        jq -r '.allOf[1].properties | keys[]' "$file" 2>/dev/null | while read -r prop; do
          echo "  - $prop" >> "$OUTPUT_FILE"
        done
      fi
    else
      # Fallback if jq is not available
      echo "$file (Last Modified: $file_timestamp)" >> "$OUTPUT_FILE"
      
      if [ "$FULL_EXPORT" = true ]; then
        echo "==== FILE CONTENT: $file" >> "$OUTPUT_FILE"
        cat "$file" >> "$OUTPUT_FILE"
        echo -e "\n==== END OF FILE CONTENT ====\n" >> "$OUTPUT_FILE"
      fi
    fi
    
    # Add a separator
    echo -e "-----------------------------\n" >> "$OUTPUT_FILE"
  else
    # JSON-only output
    # Add comma before each object except the first
    if [ "$first_file" = true ]; then
      first_file=false
    else
      echo "," >> "$OUTPUT_FILE"
    fi
    
    # For JSON output, format the file content
    if [ "$FULL_EXPORT" = true ]; then
      # Add file metadata to the JSON content
      if command -v jq &> /dev/null; then
        jq --arg file "$file" --arg timestamp "$file_timestamp" '. + {__meta: {file: $file, timestamp: $timestamp}}' "$file" >> "$OUTPUT_FILE"
      else
        # If jq is not available, output raw JSON
        cat "$file" >> "$OUTPUT_FILE"
      fi
    else
      # Include just a summary with file reference
      if command -v jq &> /dev/null; then
        jq --arg file "$file" --arg timestamp "$file_timestamp" '{__meta: {file: $file, timestamp: $timestamp}, title: .title, description: .description, type: .type}' "$file" >> "$OUTPUT_FILE"
      else
        # Minimal fallback without jq
        echo "{\"file\": \"$file\", \"timestamp\": \"$file_timestamp\"}" >> "$OUTPUT_FILE"
      fi
    fi
  fi
done

if [ "$WITH_TEXT" = true ]; then
  # Add export completion timestamp for text mode
  echo "==== EXPORT COMPLETE ====" >> "$OUTPUT_FILE"
  echo "Finished at: $(date "+%Y-%m-%d %H:%M:%S")" >> "$OUTPUT_FILE"
  echo "Export mode: $([ "$FULL_EXPORT" = true ] && echo "FULL" || echo "SUMMARY")" >> "$OUTPUT_FILE"
else
  # Close the JSON array
  echo -e "\n]" >> "$OUTPUT_FILE"
fi

# Make the script executable
chmod +x "$0"

echo "✅ Resource schemas export complete! Output saved to $OUTPUT_FILE"
echo "   Export date: $DATE_TODAY at $(date "+%H:%M:%S")"
echo "   Total resource schemas: $(find "$SCHEMAS_DIR" -type f -name "*.schema.json" | wc -l | tr -d ' ')"
echo "   Export mode: $([ "$FULL_EXPORT" = true ] && echo "FULL" || echo "SUMMARY"), Format: $([ "$WITH_TEXT" = true ] && echo "TEXT" || echo "JSON")"