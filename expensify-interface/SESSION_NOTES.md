# Expensify Backup Project - Session Notes

**Created:** 2026-01-17
**Last modified:** 2026-01-18

## Project Goal
One-time full backup of all Expensify data to Cloudflare D1 + R2 before decommissioning Expensify.

## Current Status
**Backup complete and audited. Ready to decommission Expensify.**

### Backup Summary
| Location | Reports | Expenses | Receipts |
|----------|---------|----------|----------|
| D1 database | 33 | 1068 | - |
| R2 bucket | - | - | 1063 |

- Database size: ~1.2 MB
- Receipt images: 112 MB
- 5 expenses have no receipt images (expected)

### Schema Update (2026-01-18)
Added human-readable dollar amounts alongside penny values:
- `amount` (REAL) + `amount_in_pennies` (INTEGER)
- `converted_amount` (REAL) + `converted_amount_in_pennies` (INTEGER)
- `total` (REAL) + `total_in_pennies` (INTEGER)

### Audit Results (2026-01-18)
All audits passed:
- Aggregate validation: 33/33 report totals match
- Receipt existence: 30/30 random receipts valid in R2
- Expense spot-check: 15+ verified against Expensify UI
- Receipt alignment: 5/5 R2 images match expense data

### Cloudflare Resources
- **D1 Database:** `expensify-backup` (ID: `d6602972-cfc9-4620-8547-0947a2030da5`)
- **R2 Bucket:** `expensify-receipts`

### Key Files
- `PLAN.md` - Full implementation plan with schema, audit results
- `export.sh` - Fetches all reports/expenses as JSON via API
- `download_receipts.sh` - Downloads receipt images using auth cookie
- `upload_to_d1.sh` - Uploads data to D1
- `export/expensify_export.json` - Local JSON backup
- `export/receipts/` - Local copy of receipt images

## Commands

Query D1:
```bash
wrangler d1 execute expensify-backup --remote --command="SELECT merchant, amount, created_date FROM expenses LIMIT 5;"
```

List R2 receipts:
```bash
rclone ls r2:expensify-receipts/receipts/ | wc -l
```

## Next Steps (Optional)
1. Remove expenses from BACKUP_UNREPORTED report in Expensify (if desired before closing account)
2. Delete local export files if no longer needed
3. Decommission Expensify account

## API Quirks (Reference)
1. `reportState` filter unreliable - use explicit `reportIDList`
2. Two report ID formats: `R00xxxxx` (new) and numeric (old)
3. Receipt images need browser cookie (API creds get 403)
4. Use `modifiedAmount`/`modifiedMerchant` in Freemarker templates
