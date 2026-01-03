#!/bin/bash
# Purge all generated demo outputs before regeneration
# This script removes all .yml demo files but preserves .json reference artifacts

cd "$(dirname "$0")/.."

echo "Purging generated demo outputs..."

# Remove all .yml demo files
find resources/demo_projects -name "*.yml" -type f -delete

# Remove import reports (will be regenerated)
rm -f resources/demo_projects/import_report.json
rm -f resources/demo_projects/import_report.md

# Remove generated_inputs directory if it exists
rm -rf resources/demo_projects/generated_inputs

echo "✓ Purged all demo outputs"
echo "  Note: .json reference artifacts are preserved"

