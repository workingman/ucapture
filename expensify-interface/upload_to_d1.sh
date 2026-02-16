#!/bin/bash
# Upload exported data to D1 database
set -e
cd "$(dirname "$0")"

if [ ! -f "export/expensify_export.json" ]; then
    echo "ERROR: export/expensify_export.json not found. Run ./export.sh first."
    exit 1
fi

echo "=== Uploading to D1 ==="
echo ""

# Generate SQL from JSON
echo "Step 1: Generating SQL statements..."
python3 << 'PYTHON'
import json
import os
from datetime import datetime

with open('export/expensify_export.json') as f:
    data = json.load(f)

def sql_escape(s):
    if s is None:
        return ''
    return str(s).replace("'", "''")

now = datetime.utcnow().isoformat() + 'Z'

# Generate SQL
with open('export/upload.sql', 'w') as sql:
    # No explicit transaction - D1 handles this

    # Insert reports (without raw_json to keep rows smaller)
    sql.write("-- Reports\n")
    for report in data['reports']:
        # Store report metadata only (not the full expense list) in raw_json
        report_meta = {k: v for k, v in report.items() if k != 'expenses'}
        sql.write(f"""INSERT OR REPLACE INTO reports (report_id, report_name, total, currency, status, created_date, submitted_date, approved_date, reimbursed_date, raw_json, synced_at)
VALUES ('{sql_escape(report['reportID'])}', '{sql_escape(report['reportName'])}', {report['total']}, '{sql_escape(report['currency'])}', '{sql_escape(report['status'])}', '{sql_escape(report['created'])}', '{sql_escape(report['submitted'])}', '{sql_escape(report['approved'])}', '{sql_escape(report['reimbursed'])}', '{sql_escape(json.dumps(report_meta))}', '{now}');\n""")

    sql.write("\n-- Expenses\n")
    expense_count = 0
    for report in data['reports']:
        for expense in report['expenses']:
            expense_count += 1

            # Determine receipt extension
            filename = expense.get('receiptFilename', '')
            ext = os.path.splitext(filename)[1] if filename else ''
            r2_key = f"receipts/{expense['transactionID']}{ext}" if filename else ''

            sql.write(f"""INSERT OR REPLACE INTO expenses (transaction_id, merchant, amount, converted_amount, currency, category, tag, created_date, comment, billable, reimbursable, receipt_id, receipt_filename, receipt_type, r2_receipt_key, raw_json, synced_at)
VALUES ('{sql_escape(expense['transactionID'])}', '{sql_escape(expense['merchant'])}', {expense['amount']}, {expense['convertedAmount']}, '{sql_escape(expense['currency'])}', '{sql_escape(expense['category'])}', '{sql_escape(expense['tag'])}', '{sql_escape(expense['created'])}', '{sql_escape(expense['comment'])}', {1 if expense['billable'] else 0}, {1 if expense['reimbursable'] else 0}, '{sql_escape(expense['receiptID'])}', '{sql_escape(expense['receiptFilename'])}', '{sql_escape(expense['receiptType'])}', '{r2_key}', '{sql_escape(json.dumps(expense))}', '{now}');\n""")

            # Insert report-expense relationship
            sql.write(f"""INSERT OR REPLACE INTO report_expenses (report_id, transaction_id)
VALUES ('{sql_escape(report['reportID'])}', '{sql_escape(expense['transactionID'])}');\n""")

    # Log the sync
    sql.write(f"""\n-- Sync log
INSERT INTO sync_log (started_at, completed_at, status, expenses_synced, receipts_synced, errors)
VALUES ('{now}', '{now}', 'completed', {expense_count}, 0, NULL);\n""")

    # No explicit commit needed

print(f"  Generated SQL for {len(data['reports'])} reports and {expense_count} expenses")
print(f"  Saved to export/upload.sql")
PYTHON

echo ""
echo "Step 2: Uploading to D1..."
wrangler d1 execute expensify-backup --remote --file=export/upload.sql

echo ""
echo "Step 3: Verifying upload..."
wrangler d1 execute expensify-backup --remote --command="SELECT 'reports' as table_name, COUNT(*) as count FROM reports UNION ALL SELECT 'expenses', COUNT(*) FROM expenses UNION ALL SELECT 'report_expenses', COUNT(*) FROM report_expenses;"

echo ""
echo "=== D1 Upload Complete ==="
