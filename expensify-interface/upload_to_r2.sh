#!/bin/bash
# Upload receipt images to R2 bucket
set -e
cd "$(dirname "$0")"

BUCKET="expensify-receipts"
RECEIPT_DIR="export/receipts"

if [ ! -d "$RECEIPT_DIR" ]; then
    echo "ERROR: $RECEIPT_DIR not found. Run ./download_receipts.sh first."
    exit 1
fi

echo "=== Uploading Receipts to R2 ==="
echo ""

TOTAL=$(ls -1 "$RECEIPT_DIR" | wc -l | tr -d ' ')
echo "Found $TOTAL receipts to upload"
echo ""

COUNT=0
FAILED=0

for file in "$RECEIPT_DIR"/*; do
    filename=$(basename "$file")
    COUNT=$((COUNT + 1))

    echo -n "[$COUNT/$TOTAL] $filename... "

    if wrangler r2 object put "$BUCKET/receipts/$filename" --file="$file" --content-type="$(file -b --mime-type "$file")" --remote 2>/dev/null; then
        echo "OK"
    else
        echo "FAILED"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "=== R2 Upload Complete ==="
echo "  Uploaded: $((COUNT - FAILED))"
echo "  Failed: $FAILED"
