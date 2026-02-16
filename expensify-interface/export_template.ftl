<#if addHeader == true>
ReportID,ReportName,ReportTotal,ReportCurrency,ReportStatus,ReportCreated,ReportSubmitted,TransactionID,Merchant,Amount,ConvertedAmount,Currency,Category,Created,Comment,Billable,Reimbursable,ReceiptID,ReceiptFilename,ReceiptURL,ReceiptSmall,ReceiptLarge,ReceiptType
</#if>
<#list reports as report>
<#list report.transactionList as expense>
"${report.reportID!}","${report.reportName!}",${report.total!0},"${report.currency!}","${report.status!}","${report.created!}","${report.submitted!}","${expense.transactionID!}","${expense.modifiedMerchant!expense.merchant!}",${expense.modifiedAmount!expense.amount!0},${expense.convertedAmount!0},"${expense.currency!}","${expense.category!}","${expense.modifiedCreated!expense.created!}","${expense.comment!}",${expense.billable?string("true","false")},${expense.reimbursable?string("true","false")},"${expense.receiptID!}","${expense.receiptFilename!}","${expense.receiptURL!}","${expense.receiptObject.smallThumbnail!}","${expense.receiptObject.largeThumbnail!}","${expense.receiptObject.type!}"
</#list>
</#list>
