#!/bin/bash
cd "$(dirname "$0")"

PARTNER_USER_ID="aa_geoff_dgbi_ca"
PARTNER_USER_SECRET="632b5433aeadf54ca721fc9bd3a446ad27ac995c"
API_URL="https://integrations.expensify.com/Integration-Server/ExpensifyIntegrations"

# All report IDs from UI (32 found + BACKUP_UNREPORTED internal ID)
# Mix of R-prefixed and numeric formats
REPORT_IDS="R009FSdHreTs,R00SQ6YNDY2j,R00D5BOPBFvO,R00KVv1wdh6Z,R007D1Kpw4wz,R00RT06m8yOR,R008fCRtW7Si,R005s7rTO96j,R00AXrIm93mh,R00AU7OzKLWM,R00IYcqLFja6,42633717,42724205,43359662,45970863,54478608,58650619,R00000065tuN,R00000065tvb,R00000065tvl,90064686,59219428,56553250,55659724,52025296,51767590,51766389,42631416,44594824,43868288,42631424,42633661,R00NZhoCoBJH"

cat > report_list_template.ftl << 'EOF'
<#if addHeader == true>
ReportID,ReportName,ReportTotal,ReportCurrency,ReportStatus,PolicyID,PolicyName,ExpenseCount
</#if>
<#list reports as report>
"${report.reportID!}","${report.reportName!}",${report.total!0},"${report.currency!}","${report.status!}","${report.policyID!}","${report.policyName!}",${report.transactionList?size}
</#list>
EOF

echo "=== Fetching ALL reports by ID ==="
FILENAME=$(curl -s -X POST "$API_URL" \
    -d "requestJobDescription={\"type\":\"file\",\"credentials\":{\"partnerUserID\":\"$PARTNER_USER_ID\",\"partnerUserSecret\":\"$PARTNER_USER_SECRET\"},\"onReceive\":{\"immediateResponse\":[\"returnRandomFileName\"]},\"inputSettings\":{\"type\":\"combinedReportData\",\"filters\":{\"reportIDList\":\"$REPORT_IDS\"}},\"outputSettings\":{\"fileExtension\":\"csv\"}}" \
    --data-urlencode 'template@report_list_template.ftl')

echo "Result: $FILENAME"
if [[ "$FILENAME" == export* ]]; then
    curl -s -X POST "$API_URL" \
        -d "requestJobDescription={\"type\":\"download\",\"credentials\":{\"partnerUserID\":\"$PARTNER_USER_ID\",\"partnerUserSecret\":\"$PARTNER_USER_SECRET\"},\"fileName\":\"$FILENAME\",\"fileSystem\":\"integrationServer\"}" | tee all_reports.csv
    echo ""
    echo "=== Summary ==="
    echo "Total reports: $(wc -l < all_reports.csv)"
    echo "Total expenses: $(awk -F',' '{sum += $NF} END {print sum}' all_reports.csv)"
fi
