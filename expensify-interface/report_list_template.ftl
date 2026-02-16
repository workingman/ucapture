<#if addHeader == true>
ReportID,ReportName,ReportTotal,ReportCurrency,ReportStatus,PolicyID,PolicyName,ExpenseCount
</#if>
<#list reports as report>
"${report.reportID!}","${report.reportName!}",${report.total!0},"${report.currency!}","${report.status!}","${report.policyID!}","${report.policyName!}",${report.transactionList?size}
</#list>
