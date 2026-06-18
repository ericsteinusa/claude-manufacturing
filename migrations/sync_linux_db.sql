-- =============================================================
-- Migration: Sync Linux 'company_db' → match Windows 'company'
-- Generated: 2026-06-17
-- Apply on:  192.168.0.239, database company_db
--   sudo -u postgres psql -d company_db -f sync_linux_db.sql
-- =============================================================

BEGIN;

-- -------------------------------------------------------
-- 1. Drop legacy tables removed from Windows in commit #186
-- -------------------------------------------------------
DROP TABLE IF EXISTS expense_report;
DROP TABLE IF EXISTS vendors CASCADE;  -- CASCADE removes the stale ap_invoice_vendor_id_fkey FK

-- Uncomment if you want to drop these too (review first):
-- DROP TABLE IF EXISTS calls;       -- Windows uses calls2; keep if Linux still references it
-- DROP TABLE IF EXISTS department;  -- Windows uses dept/dept_sub; keep if Linux still references it

-- -------------------------------------------------------
-- 2. Fix column type mismatches
-- -------------------------------------------------------

ALTER TABLE inventory_transaction
    ALTER COLUMN quantity TYPE real USING quantity::real;

ALTER TABLE tax
    ALTER COLUMN percent TYPE integer USING percent::integer;

ALTER TABLE wo_material
    ALTER COLUMN qty_required TYPE real USING qty_required::real,
    ALTER COLUMN qty_issued   TYPE real USING qty_issued::real;

-- -------------------------------------------------------
-- 3. payroll_run: restructure to match Windows
--    Linux columns:   pay_period_start, pay_period_end, run_number, notes
--    Windows columns: period_start, period_end, pay_frequency, federal_tax_rate, state_tax_rate
-- -------------------------------------------------------

-- Add Windows-only columns with temporary defaults so NOT NULL is satisfied
ALTER TABLE payroll_run
    ADD COLUMN IF NOT EXISTS period_start     text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS period_end       text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS pay_frequency    text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS federal_tax_rate real NOT NULL DEFAULT 0.0,
    ADD COLUMN IF NOT EXISTS state_tax_rate   real NOT NULL DEFAULT 0.0;

-- Preserve data: copy Linux column values into the new Windows-named columns
UPDATE payroll_run
    SET period_start = pay_period_start
    WHERE pay_period_start IS NOT NULL AND period_start = '';

UPDATE payroll_run
    SET period_end = pay_period_end
    WHERE pay_period_end IS NOT NULL AND period_end = '';

-- Drop Linux-only columns
ALTER TABLE payroll_run
    DROP COLUMN IF EXISTS pay_period_start,
    DROP COLUMN IF EXISTS pay_period_end,
    DROP COLUMN IF EXISTS run_number,
    DROP COLUMN IF EXISTS notes;

-- Remove temporary defaults (Windows columns have no default; app sets them)
ALTER TABLE payroll_run
    ALTER COLUMN period_start     DROP DEFAULT,
    ALTER COLUMN period_end       DROP DEFAULT,
    ALTER COLUMN pay_frequency    DROP DEFAULT;

-- Match Windows default on status
ALTER TABLE payroll_run
    ALTER COLUMN status SET DEFAULT 'processed';

-- -------------------------------------------------------
-- 4. payroll_entry: drop Linux-only columns
-- -------------------------------------------------------
ALTER TABLE payroll_entry
    DROP COLUMN IF EXISTS hourly_rate,
    DROP COLUMN IF EXISTS hours_worked,
    DROP COLUMN IF EXISTS notes;

-- -------------------------------------------------------
-- 5. payroll_entry_deduction: drop Linux-only column
-- -------------------------------------------------------
ALTER TABLE payroll_entry_deduction
    DROP COLUMN IF EXISTS deduction_type_id;

-- -------------------------------------------------------
-- 6. payroll_deduction_type: drop Linux-only column
-- -------------------------------------------------------
ALTER TABLE payroll_deduction_type
    DROP COLUMN IF EXISTS description;

-- -------------------------------------------------------
-- 7. bom: drop Linux-only column
-- -------------------------------------------------------
ALTER TABLE bom
    DROP COLUMN IF EXISTS scrap_pct;

-- -------------------------------------------------------
-- 8. product: drop Linux-only columns
-- -------------------------------------------------------
ALTER TABLE product
    DROP COLUMN IF EXISTS item_type,
    DROP COLUMN IF EXISTS lead_time_days,
    DROP COLUMN IF EXISTS uom;

COMMIT;
