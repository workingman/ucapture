# Expensify Backup to Cloudflare - Plan

## Goal
One-time full backup of all Expensify data (expenses, reports, receipt images) to Cloudflare D1 + R2 before decommissioning Expensify.

## Data Inventory (Final - 2026-01-18)
- **33 reports** across 2 workspaces (DGBI + Geoffrey's Expenses)
- **1,068 expenses** total
- **1,063 receipt images** (112 MB)
- **5 expenses** without receipts
- Note: UI shows 1,092 expenses total (includes 23 deleted + 1 empty report)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   Local Scripts (Bash/Python)                   │
├─────────────────────────────────────────────────────────────────┤
│  1. Export all reports/expenses via Expensify API               │
│  2. Download receipt images via auth cookie                     │
│  3. Push data to D1 via Wrangler CLI                            │
│  4. Upload images to R2 via rclone                              │
└─────────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
┌─────────────────────┐      ┌─────────────────────┐
│        D1           │      │         R2          │
│  (SQLite database)  │      │   (Object storage)  │
├─────────────────────┤      ├─────────────────────┤
│  expenses           │      │  receipts/          │
│  reports            │      │    {txn_id}.ext     │
│  report_expenses    │      │                     │
│  sync_log           │      │                     │
└─────────────────────┘      └─────────────────────┘
```

## D1 Schema

```sql
-- Expenses (the core data)
CREATE TABLE expenses (
    transaction_id TEXT PRIMARY KEY,
    merchant TEXT,
    amount REAL,                 -- dollars (human-readable)
    amount_in_pennies INTEGER,   -- cents (precision)
    converted_amount REAL,       -- dollars, in report currency
    converted_amount_in_pennies INTEGER,  -- cents, in report currency
    currency TEXT,
    category TEXT,
    tag TEXT,
    created_date TEXT,
    comment TEXT,
    billable BOOLEAN,
    reimbursable BOOLEAN,
    receipt_id TEXT,
    receipt_filename TEXT,
    receipt_type TEXT,           -- pdf, jpg, etc
    r2_receipt_key TEXT,         -- R2 path after upload
    raw_json TEXT,               -- full original expense data
    synced_at TEXT
);

-- Reports (parent records)
CREATE TABLE reports (
    report_id TEXT PRIMARY KEY,
    report_name TEXT,
    total REAL,                  -- dollars (human-readable)
    total_in_pennies INTEGER,    -- cents (precision)
    currency TEXT,
    status TEXT,
    created_date TEXT,
    submitted_date TEXT,
    approved_date TEXT,
    reimbursed_date TEXT,
    raw_json TEXT,               -- report metadata (without expenses)
    synced_at TEXT
);

-- Join table (which expenses are on which reports)
CREATE TABLE report_expenses (
    report_id TEXT,
    transaction_id TEXT,
    PRIMARY KEY (report_id, transaction_id),
    FOREIGN KEY (report_id) REFERENCES reports(report_id),
    FOREIGN KEY (transaction_id) REFERENCES expenses(transaction_id)
);

-- Sync tracking
CREATE TABLE sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT,
    completed_at TEXT,
    status TEXT,
    expenses_synced INTEGER,
    receipts_synced INTEGER,
    errors TEXT
);
```

## Implementation Steps

### Phase 1: Manual Data Preparation ✅ DONE
1. ~~In Expensify UI, select all unreported expenses~~
2. ~~Add to a new report called "BACKUP_UNREPORTED"~~
3. ~~This makes them visible to the API~~
   - Created with 288 expenses, $21,738.79 CAD

### Phase 2: Cloudflare Setup ✅ DONE
1. ~~Create D1 database via Wrangler CLI~~
2. ~~Run schema migration~~
3. ~~Create R2 bucket for receipts~~
4. ~~Configure wrangler.toml~~

### Phase 3: Local Export Script ✅ DONE
1. ~~Fetch all reports via Expensify API using reportIDList filter~~
2. ~~Parse response into expenses + reports (JSON format)~~
3. ~~Download receipt images using auth cookie~~
4. ~~Save locally for verification~~

### Phase 4: Upload to Cloudflare ✅ DONE
1. ~~Insert expenses/reports into D1 via Wrangler~~
2. ~~Upload receipt images to R2 via rclone~~
3. ~~R2 keys stored in D1 as `receipts/{transaction_id}.{ext}`~~

### Phase 5: Verification ✅ DONE
1. ~~Verify counts match (33 reports, 1068 expenses, 1063 receipts)~~

### Phase 6: Audit & Validation ✅ DONE (2026-01-18)

#### Schema Mapping Analysis
- Reviewed all Expensify API fields vs D1 schema
- Key fields mapped correctly: merchant, amount, currency, category, dates
- `policyID`/`policyName` not in dedicated columns but preserved in `raw_json`
- `convertedAmount` correctly captures currency conversions (computed at expense creation time)
- Receipt thumbnails preserved in `raw_json` (not needed separately)

#### Schema Update Applied
- Renamed `amount` → `amount_in_pennies` (preserves precision)
- Added `amount` as REAL for human-readable dollars
- Same pattern for `converted_amount` and report `total`

#### Audit Results

| Audit | Result | Details |
|-------|--------|---------|
| Aggregate validation | ✅ PASS | All 33 report totals match sum of expenses |
| Receipt existence (n=30) | ✅ PASS | 30/30 random receipts exist in R2, files valid |
| Expense spot-check (n=15+) | ✅ PASS | Verified against Expensify UI across 2017-2025 |
| Receipt alignment (n=5) | ✅ PASS | R2 images match expense data exactly |

**Receipt alignment verified:**
1. PETRO-CANADA $4.12 (2019-11-24) - JPG ✅
2. Google $52.78 (2025-11-30) - PDF ✅
3. GitHub $7.00 (2019-02-22) - PDF ✅
4. PayByPhone $1.93 (2019-08-08) - PDF ✅
5. Hangtag $3.50 (2019-09-06) - PDF ✅

#### Optional cleanup (not done)
- Remove expenses from BACKUP_UNREPORTED report in Expensify
- Delete local export files if no longer needed

## Cloudflare Resources

- **D1 Database:** `expensify-backup`
  - ID: `d6602972-cfc9-4620-8547-0947a2030da5`
  - Size: 1.16 MB

- **R2 Bucket:** `expensify-receipts`
  - Size: 112 MB
  - Files: 1,063

## Credentials

```
EXPENSIFY_PARTNER_USER_ID=aa_geoff_dgbi_ca
EXPENSIFY_PARTNER_USER_SECRET=632b5433aeadf54ca721fc9bd3a446ad27ac995c
EXPENSIFY_AUTH_TOKEN=<browser cookie - refresh as needed>
```

## Report IDs (all 33 with data)

```
R009FSdHreTs,R00SQ6YNDY2j,R00D5BOPBFvO,R00KVv1wdh6Z,R007D1Kpw4wz,R00RT06m8yOR,
R008fCRtW7Si,R005s7rTO96j,R00AXrIm93mh,R00AU7OzKLWM,R00IYcqLFja6,42633717,
42724205,43359662,45970863,54478608,58650619,R00000065tuN,R00000065tvb,
R00000065tvl,90064686,59219428,56553250,55659724,52025296,51767590,51766389,
42631416,44594824,43868288,42631424,42633661,R00NZhoCoBJH
```

## Key Findings

1. **API doesn't return "Draft" reports by default** - Must specify report IDs explicitly
2. **Two report ID formats exist**: `R00xxxxx` (new) and numeric `12345678` (old)
3. **Both formats work** in the `reportIDList` filter
4. **Receipt images require browser auth cookie** - API creds alone get 403
5. **Receipt URL pattern**: `https://www.expensify.com/receipts/{filename}`
6. **Two workspaces**: DGBI (main) and Geoffrey's Expenses (personal)
7. **rclone is much faster than wrangler** for R2 bulk uploads (1.5 min vs 18+ min)
8. **Freemarker null handling** - Use `?has_content` for numeric fields that may be empty
