-- Expenses (the core data)
CREATE TABLE expenses (
    transaction_id TEXT PRIMARY KEY,
    merchant TEXT,
    amount INTEGER,              -- cents
    converted_amount INTEGER,    -- cents, in report currency
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
    raw_json TEXT,               -- full original data for future use
    synced_at TEXT
);

-- Reports (parent records)
CREATE TABLE reports (
    report_id TEXT PRIMARY KEY,
    report_name TEXT,
    total INTEGER,               -- cents
    currency TEXT,
    status TEXT,
    created_date TEXT,
    submitted_date TEXT,
    approved_date TEXT,
    reimbursed_date TEXT,
    raw_json TEXT,
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

-- Indexes for common queries
CREATE INDEX idx_expenses_created ON expenses(created_date);
CREATE INDEX idx_expenses_merchant ON expenses(merchant);
CREATE INDEX idx_reports_status ON reports(status);
CREATE INDEX idx_reports_created ON reports(created_date);
