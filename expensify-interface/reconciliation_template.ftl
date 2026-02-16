<#if addHeader>
CardOwner,CardName,Bank,ReportID,TransactionID,Merchant,Amount,Posted,Category,Tag
</#if>
<#list cards as card, reports>
<#list reports as report>
<#list report.transactionList as expense>
"${card.owner!}","${card.cardName!}","${card.bank!}","${report.reportID!}","${expense.transactionID!}","${expense.merchant!}",${expense.amount!0},"${expense.posted!}","${expense.category!}","${expense.tag!}"
</#list>
</#list>
</#list>
