#!/bin/bash

curl -X POST 'https://integrations.expensify.com/Integration-Server/ExpensifyIntegrations' \
    -d 'requestJobDescription={
        "type":"file",
        "credentials":{
            "partnerUserID":"aa_geoff_dgbi_ca",
            "partnerUserSecret":"632b5433aeadf54ca721fc9bd3a446ad27ac995c"
        },
        "onReceive":{
            "immediateResponse":["returnRandomFileName"]
        },
        "inputSettings":{
            "type":"combinedReportData",
            "reportState":"OPEN,SUBMITTED,APPROVED,REIMBURSED,ARCHIVED"
        },
        "outputSettings":{
            "fileExtension":"csv"
        }
    }' \
    --data-urlencode 'template@export_template.ftl'
