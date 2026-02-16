#!/bin/bash
# Download all receipt images from Expensify using browser auth cookie

set -e
cd "$(dirname "$0")"

if [ -z "$1" ]; then
    echo "Usage: ./download_receipts.sh <authToken>"
    echo ""
    echo "Get authToken from browser:"
    echo "  1. Open Expensify in Chrome"
    echo "  2. DevTools (F12) > Application > Cookies > expensify.com"
    echo "  3. Copy the 'authToken' value"
    exit 1
fi

AUTH_TOKEN="$1"

if [ ! -f "export/receipt_list.json" ]; then
    echo "ERROR: export/receipt_list.json not found. Run ./export.sh first."
    exit 1
fi

mkdir -p export/receipts

TOTAL=$(python3 -c "import json; print(len(json.load(open('export/receipt_list.json'))))")
echo "=== Downloading $TOTAL receipts ==="
echo ""

python3 << PYTHON
import json
import subprocess
import os
import sys

with open('export/receipt_list.json') as f:
    receipts = json.load(f)

success = 0
failed = 0
skipped = 0

for i, r in enumerate(receipts, 1):
    filename = r['filename']
    url = r['url']
    txn_id = r['transactionID']

    # Determine output filename (use transaction ID to avoid duplicates)
    ext = os.path.splitext(filename)[1] or '.jpg'
    outfile = f"export/receipts/{txn_id}{ext}"

    # Skip if already downloaded
    if os.path.exists(outfile) and os.path.getsize(outfile) > 0:
        skipped += 1
        continue

    print(f"[{i}/{len(receipts)}] {filename}...", end=" ", flush=True)

    result = subprocess.run([
        'curl', '-s', '-f',
        '-b', f'authToken=$AUTH_TOKEN',
        '-o', outfile,
        url
    ], capture_output=True)

    if result.returncode == 0 and os.path.exists(outfile) and os.path.getsize(outfile) > 100:
        print("OK")
        success += 1
    else:
        print("FAILED")
        failed += 1
        # Remove empty/invalid file
        if os.path.exists(outfile):
            os.remove(outfile)

print("")
print(f"=== Download Complete ===")
print(f"  Success: {success}")
print(f"  Skipped (already exists): {skipped}")
print(f"  Failed: {failed}")
PYTHON
