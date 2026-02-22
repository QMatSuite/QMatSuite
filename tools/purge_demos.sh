#!/bin/bash
# Purge all generated demo outputs before regeneration
# This script removes all .yml demo files but preserves .json reference artifacts

cd "$(dirname "$0")/.."

RESOURCES_DIR="src/quantumvitas/resources"
DEMO_DIR="${RESOURCES_DIR}/demo_projects"

if [ ! -d "$DEMO_DIR" ]; then
  echo "ERROR: Demo directory not found: $DEMO_DIR"
  exit 1
fi

echo "Purging generated demo outputs..."

# Remove all .yml demo files
find "$DEMO_DIR" -name "*.yml" -type f -delete

# Remove import reports (will be regenerated)
rm -f "$DEMO_DIR/import_report.json"
rm -f "$DEMO_DIR/import_report.md"

# Remove generated_inputs directory if it exists
rm -rf "$DEMO_DIR/generated_inputs"

echo "✓ Purged all demo outputs"
echo "  Note: .json reference artifacts are preserved"
