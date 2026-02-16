#!/bin/bash
# Expensify Full Export Script
# Exports all reports/expenses as JSON and downloads receipt images

set -e
cd "$(dirname "$0")"

PARTNER_USER_ID="aa_geoff_dgbi_ca"
PARTNER_USER_SECRET="632b5433aeadf54ca721fc9bd3a446ad27ac995c"
API_URL="https://integrations.expensify.com/Integration-Server/ExpensifyIntegrations"

# All 34 report IDs
REPORT_IDS="R009FSdHreTs,R00SQ6YNDY2j,R00D5BOPBFvO,R00KVv1wdh6Z,R007D1Kpw4wz,R00RT06m8yOR,R008fCRtW7Si,R005s7rTO96j,R00AXrIm93mh,R00AU7OzKLWM,R00IYcqLFja6,42633717,42724205,43359662,45970863,54478608,58650619,R00000065tuN,R00000065tvb,R00000065tvl,90064686,59219428,56553250,55659724,52025296,51767590,51766389,42631416,44594824,43868288,42631424,42633661,R00NZhoCoBJH"

# Output directories
mkdir -p export/receipts

echo "=== Expensify Full Export ==="
echo ""

# Step 1: Create JSON export template
cat > export/json_template.ftl << 'TEMPLATE'
{
  "exportedAt": "${.now?iso_utc}",
  "reports": [
<#list reports as report>
    {
      "reportID": "${report.reportID!}",
      "reportName": "${report.reportName!?json_string}",
      "total": ${report.total!0},
      "currency": "${report.currency!}",
      "status": "${report.status!}",
      "created": "${report.created!}",
      "submitted": "${report.submitted!}",
      "approved": "${report.approved!}",
      "reimbursed": "${report.reimbursed!}",
      "policyID": "${report.policyID!}",
      "policyName": "${report.policyName!?json_string}",
      "expenses": [
<#list report.transactionList as tx>
        {
          "transactionID": "${tx.transactionID!''}",
          "merchant": "${(tx.modifiedMerchant!(tx.merchant!''))?json_string}",
          "amount": <#if tx.modifiedAmount?? && tx.modifiedAmount?has_content>${tx.modifiedAmount}<#elseif tx.amount?? && tx.amount?has_content>${tx.amount}<#else>0</#if>,
          "convertedAmount": ${tx.convertedAmount!0},
          "currency": "${tx.currency!''}",
          "originalCurrency": "${tx.originalCurrency!''}",
          "category": "${(tx.category!'')?json_string}",
          "tag": "${(tx.tag!'')?json_string}",
          "created": "${tx.modifiedCreated!(tx.created!'')}",
          "comment": "${(tx.comment!'')?json_string}",
          "billable": <#if tx.billable??>${tx.billable?string("true","false")}<#else>false</#if>,
          "reimbursable": <#if tx.reimbursable??>${tx.reimbursable?string("true","false")}<#else>false</#if>,
          "receiptID": "${tx.receiptID!''}",
          "receiptFilename": "${tx.receiptFilename!''}",
          "receiptURL": "${tx.receiptURL!''}",
          "receiptType": "${(tx.receiptObject.type)!''}",
          "receiptSmallThumbnail": "${(tx.receiptObject.smallThumbnail)!''}",
          "receiptLargeThumbnail": "${(tx.receiptObject.largeThumbnail)!''}"
        }<#if tx_has_next>,</#if>
</#list>
      ]
    }<#if report_has_next>,</#if>
</#list>
  ]
}
TEMPLATE

echo "Step 1: Fetching all reports and expenses as JSON..."
FILENAME=$(curl -s -X POST "$API_URL" \
    -d "requestJobDescription={\"type\":\"file\",\"credentials\":{\"partnerUserID\":\"$PARTNER_USER_ID\",\"partnerUserSecret\":\"$PARTNER_USER_SECRET\"},\"onReceive\":{\"immediateResponse\":[\"returnRandomFileName\"]},\"inputSettings\":{\"type\":\"combinedReportData\",\"filters\":{\"reportIDList\":\"$REPORT_IDS\"}},\"outputSettings\":{\"fileExtension\":\"json\"}}" \
    --data-urlencode 'template@export/json_template.ftl')

echo "  Export file: $FILENAME"

if [[ "$FILENAME" != export* ]]; then
    echo "ERROR: Failed to create export. Response: $FILENAME"
    exit 1
fi

echo "Step 2: Downloading export file..."
curl -s -X POST "$API_URL" \
    -d "requestJobDescription={\"type\":\"download\",\"credentials\":{\"partnerUserID\":\"$PARTNER_USER_ID\",\"partnerUserSecret\":\"$PARTNER_USER_SECRET\"},\"fileName\":\"$FILENAME\",\"fileSystem\":\"integrationServer\"}" \
    -o export/expensify_export.json

# Validate JSON
if ! python3 -c "import json; json.load(open('export/expensify_export.json'))" 2>/dev/null; then
    echo "ERROR: Invalid JSON in export file"
    cat export/expensify_export.json
    exit 1
fi

echo "  Saved to export/expensify_export.json"

# Count reports and expenses
REPORT_COUNT=$(python3 -c "import json; d=json.load(open('export/expensify_export.json')); print(len(d['reports']))")
EXPENSE_COUNT=$(python3 -c "import json; d=json.load(open('export/expensify_export.json')); print(sum(len(r['expenses']) for r in d['reports']))")

echo ""
echo "=== Export Summary ==="
echo "  Reports: $REPORT_COUNT"
echo "  Expenses: $EXPENSE_COUNT"
echo ""

# Extract receipt URLs for downloading
echo "Step 3: Extracting receipt URLs..."
python3 << 'PYTHON'
import json

with open('export/expensify_export.json') as f:
    data = json.load(f)

receipts = []
for report in data['reports']:
    for expense in report['expenses']:
        if expense.get('receiptFilename'):
            receipts.append({
                'transactionID': expense['transactionID'],
                'filename': expense['receiptFilename'],
                'url': f"https://www.expensify.com/receipts/{expense['receiptFilename']}"
            })

with open('export/receipt_list.json', 'w') as f:
    json.dump(receipts, f, indent=2)

print(f"  Found {len(receipts)} receipts to download")
PYTHON

echo ""
echo "=== Next Steps ==="
echo "1. Get fresh auth cookie from browser (DevTools > Application > Cookies > authToken)"
echo "2. Run: ./download_receipts.sh <authToken>"
echo ""
