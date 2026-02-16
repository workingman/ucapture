#!/bin/bash
# Upload receipt images to R2 bucket in parallel
set -e
cd "$(dirname "$0")"

BUCKET="expensify-receipts"
RECEIPT_DIR="export/receipts"
PARALLEL_JOBS=10  # Number of concurrent uploads

if [ ! -d "$RECEIPT_DIR" ]; then
    echo "ERROR: $RECEIPT_DIR not found. Run ./download_receipts.sh first."
    exit 1
fi

echo "=== Uploading Receipts to R2 (parallel) ==="
echo ""

TOTAL=$(ls -1 "$RECEIPT_DIR" | wc -l | tr -d ' ')
echo "Found $TOTAL receipts to upload"
echo "Running $PARALLEL_JOBS parallel uploads"
echo ""

# Create upload function for xargs
upload_one() {
    file="$1"
    filename=$(basename "$file")
    content_type=$(file -b --mime-type "$file")

    if wrangler r2 object put "$BUCKET/receipts/$filename" --file="$file" --content-type="$content_type" --remote 2>/dev/null; then
        echo "OK: $filename"
    else
        echo "FAILED: $filename" >&2
    fi
}
export -f upload_one
export BUCKET

# Use xargs for parallel execution
ls -1 "$RECEIPT_DIR"/* | xargs -P $PARALLEL_JOBS -I {} bash -c 'upload_one "$@"' _ {}

echo ""
echo "=== R2 Upload Complete ==="
