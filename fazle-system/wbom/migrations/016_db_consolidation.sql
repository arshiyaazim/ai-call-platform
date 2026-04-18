-- ============================================================
-- Migration 016: Full Database Consolidation (Zero Data Loss)
-- Merges legacy tables into WBOM tables
-- IDEMPOTENT: safe to re-run multiple times
-- ============================================================

-- =========================================================
-- STEP 1: Extend WBOM tables with social-engine columns
-- =========================================================

-- wbom_contacts: Add social engine fields
ALTER TABLE wbom_contacts ADD COLUMN IF NOT EXISTS platform VARCHAR(20) DEFAULT 'whatsapp';
ALTER TABLE wbom_contacts ADD COLUMN IF NOT EXISTS relation VARCHAR(100) DEFAULT 'unknown';
ALTER TABLE wbom_contacts ADD COLUMN IF NOT EXISTS personality_hint VARCHAR(200) DEFAULT '';
ALTER TABLE wbom_contacts ADD COLUMN IF NOT EXISTS interaction_count INT DEFAULT 0;
ALTER TABLE wbom_contacts ADD COLUMN IF NOT EXISTS interest_level VARCHAR(20) DEFAULT 'unknown';
ALTER TABLE wbom_contacts ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ DEFAULT NOW();

-- Expand column widths to match legacy table sizes
ALTER TABLE wbom_contacts ALTER COLUMN display_name TYPE VARCHAR(200);
ALTER TABLE wbom_contacts ALTER COLUMN display_name SET DEFAULT '';
ALTER TABLE wbom_contacts ALTER COLUMN company_name TYPE VARCHAR(300);
ALTER TABLE wbom_contacts ALTER COLUMN whatsapp_number TYPE VARCHAR(50);

-- Change unique constraint: (whatsapp_number) → (whatsapp_number, platform)
DO $$ BEGIN
    ALTER TABLE wbom_contacts DROP CONSTRAINT IF EXISTS wbom_contacts_whatsapp_number_key;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'wbom_contacts_whatsapp_platform_uniq'
    ) THEN
        ALTER TABLE wbom_contacts ADD CONSTRAINT wbom_contacts_whatsapp_platform_uniq
            UNIQUE (whatsapp_number, platform);
    END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- wbom_whatsapp_messages: Add social engine fields
ALTER TABLE wbom_whatsapp_messages ADD COLUMN IF NOT EXISTS platform VARCHAR(20) DEFAULT 'whatsapp';
ALTER TABLE wbom_whatsapp_messages ADD COLUMN IF NOT EXISTS direction VARCHAR(10);
ALTER TABLE wbom_whatsapp_messages ADD COLUMN IF NOT EXISTS contact_identifier VARCHAR(200);
ALTER TABLE wbom_whatsapp_messages ADD COLUMN IF NOT EXISTS ai_response TEXT DEFAULT '';
ALTER TABLE wbom_whatsapp_messages ADD COLUMN IF NOT EXISTS metadata_json JSONB DEFAULT '{}';
ALTER TABLE wbom_whatsapp_messages ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'sent';

-- Relax constraints for social engine compatibility
ALTER TABLE wbom_whatsapp_messages ALTER COLUMN message_body SET DEFAULT '';
ALTER TABLE wbom_whatsapp_messages ALTER COLUMN sender_number SET DEFAULT '';
ALTER TABLE wbom_whatsapp_messages ALTER COLUMN sender_number TYPE VARCHAR(200);
ALTER TABLE wbom_whatsapp_messages ALTER COLUMN message_type SET DEFAULT 'text';

-- Make NOT NULL columns nullable for social engine inserts
DO $$ BEGIN
    ALTER TABLE wbom_whatsapp_messages ALTER COLUMN message_body DROP NOT NULL;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE wbom_whatsapp_messages ALTER COLUMN sender_number DROP NOT NULL;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE wbom_whatsapp_messages ALTER COLUMN message_type DROP NOT NULL;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- Backfill existing WBOM rows
UPDATE wbom_whatsapp_messages SET direction = message_type WHERE direction IS NULL AND message_type IS NOT NULL;
UPDATE wbom_whatsapp_messages SET contact_identifier = sender_number WHERE contact_identifier IS NULL AND sender_number IS NOT NULL;
UPDATE wbom_whatsapp_messages SET status = CASE WHEN is_processed THEN 'sent' ELSE 'received' END WHERE status IS NULL;

-- Trigger: auto-sync sender_number, message_type, received_at from social engine inserts
CREATE OR REPLACE FUNCTION wbom_msg_autofill() RETURNS trigger AS $fn$
BEGIN
    IF NEW.sender_number IS NULL OR NEW.sender_number = '' THEN
        NEW.sender_number := COALESCE(NEW.contact_identifier, '');
    END IF;
    IF NEW.contact_identifier IS NULL OR NEW.contact_identifier = '' THEN
        NEW.contact_identifier := COALESCE(NEW.sender_number, '');
    END IF;
    IF NEW.message_type IS NULL OR NEW.message_type = '' THEN
        NEW.message_type := COALESCE(NEW.direction, 'text');
    END IF;
    IF NEW.direction IS NULL OR NEW.direction = '' THEN
        NEW.direction := COALESCE(NEW.message_type, 'incoming');
    END IF;
    IF NEW.received_at IS NULL THEN
        NEW.received_at := NOW();
    END IF;
    IF NEW.message_body IS NULL THEN
        NEW.message_body := '';
    END IF;
    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_wbom_msg_autofill ON wbom_whatsapp_messages;
CREATE TRIGGER trg_wbom_msg_autofill
    BEFORE INSERT ON wbom_whatsapp_messages
    FOR EACH ROW EXECUTE FUNCTION wbom_msg_autofill();


-- =========================================================
-- STEP 2: Freeze legacy writes (best effort)
-- =========================================================
DO $$ BEGIN EXECUTE 'REVOKE INSERT, UPDATE, DELETE ON ops_employees FROM PUBLIC'; EXCEPTION WHEN undefined_table THEN NULL; WHEN OTHERS THEN NULL; END $$;
DO $$ BEGIN EXECUTE 'REVOKE INSERT, UPDATE, DELETE ON ops_payments FROM PUBLIC'; EXCEPTION WHEN undefined_table THEN NULL; WHEN OTHERS THEN NULL; END $$;


-- =========================================================
-- STEP 3: Migrate ops_employees → wbom_employees
-- =========================================================
DO $$ BEGIN
    INSERT INTO wbom_employees (employee_mobile, employee_name, designation, status, created_at, updated_at)
    SELECT mobile, COALESCE(name, 'Unknown'), 'Escort', 'Active',
           COALESCE(created_at, NOW()), COALESCE(updated_at, NOW())
    FROM ops_employees
    WHERE mobile IS NOT NULL
    ON CONFLICT (employee_mobile) DO NOTHING;
    RAISE NOTICE 'STEP 3: ops_employees migrated';
EXCEPTION WHEN undefined_table THEN
    RAISE NOTICE 'STEP 3: ops_employees not found — skipping';
END $$;

-- Handle orphan employees from ops_payments
DO $$ BEGIN
    INSERT INTO wbom_employees (employee_mobile, employee_name, designation, status, created_at, updated_at)
    SELECT DISTINCT
        CASE WHEN op.employee_id ~ '^0' THEN op.employee_id ELSE '0' || op.employee_id END,
        COALESCE(op.name, 'Unknown'), 'Escort', 'Active', NOW(), NOW()
    FROM ops_payments op
    WHERE NOT EXISTS (
        SELECT 1 FROM wbom_employees we
        WHERE we.employee_mobile = CASE WHEN op.employee_id ~ '^0' THEN op.employee_id ELSE '0' || op.employee_id END
    )
    ON CONFLICT (employee_mobile) DO NOTHING;
    RAISE NOTICE 'STEP 3b: orphan employees from ops_payments migrated';
EXCEPTION WHEN undefined_table THEN
    RAISE NOTICE 'STEP 3b: ops_payments not found — skipping';
END $$;


-- =========================================================
-- STEP 4: Migrate ops_payments → wbom_cash_transactions
-- =========================================================
DO $$ BEGIN
    INSERT INTO wbom_cash_transactions (
        employee_id, transaction_type, amount, payment_method, payment_mobile,
        transaction_date, transaction_time, status, remarks, created_by
    )
    SELECT
        we.employee_id, 'Other', op.amount,
        CASE op.method WHEN 'B' THEN 'Bkash' WHEN 'N' THEN 'Nagad' ELSE 'Cash' END,
        op.payment_number,
        COALESCE(op.payment_date, CURRENT_DATE),
        COALESCE(op.created_at, NOW()),
        'Completed',
        COALESCE(op.remarks, ''),
        COALESCE(op.paid_by, 'migration_ops')
    FROM ops_payments op
    JOIN wbom_employees we ON we.employee_mobile =
        CASE WHEN op.employee_id ~ '^0' THEN op.employee_id ELSE '0' || op.employee_id END
    WHERE NOT EXISTS (
        SELECT 1 FROM wbom_cash_transactions wct
        WHERE wct.employee_id = we.employee_id
          AND wct.amount = op.amount
          AND wct.transaction_date = COALESCE(op.payment_date, CURRENT_DATE)
          AND wct.transaction_type = 'Other'
          AND wct.payment_method = CASE op.method WHEN 'B' THEN 'Bkash' WHEN 'N' THEN 'Nagad' ELSE 'Cash' END
    );
    RAISE NOTICE 'STEP 4: ops_payments migrated';
EXCEPTION WHEN undefined_table THEN
    RAISE NOTICE 'STEP 4: ops_payments not found — skipping';
END $$;


-- =========================================================
-- STEP 5: Migrate fazle_contacts → wbom_contacts
-- =========================================================
DO $$ BEGIN
    INSERT INTO wbom_contacts (
        whatsapp_number, display_name, company_name, notes, platform,
        relation, personality_hint, interaction_count, interest_level,
        last_seen, is_active, created_at, updated_at
    )
    SELECT
        fc.phone,
        COALESCE(fc.name, ''),
        COALESCE(fc.company, ''),
        COALESCE(fc.notes, ''),
        COALESCE(fc.platform, 'whatsapp'),
        COALESCE(fc.relation, 'unknown'),
        COALESCE(fc.personality_hint, ''),
        COALESCE(fc.interaction_count, 0),
        COALESCE(fc.interest_level, 'unknown'),
        COALESCE(fc.last_seen, NOW()),
        TRUE,
        COALESCE(fc.created_at, NOW()),
        COALESCE(fc.last_updated, NOW())
    FROM fazle_contacts fc
    WHERE NOT EXISTS (
        SELECT 1 FROM wbom_contacts wc
        WHERE wc.whatsapp_number = fc.phone
          AND wc.platform = COALESCE(fc.platform, 'whatsapp')
    )
    ON CONFLICT (whatsapp_number, platform) DO NOTHING;
    RAISE NOTICE 'STEP 5: fazle_contacts migrated';
EXCEPTION WHEN undefined_table THEN
    RAISE NOTICE 'STEP 5: fazle_contacts not found — skipping';
END $$;

-- Also merge fazle_social_contacts into wbom_contacts
DO $$ BEGIN
    INSERT INTO wbom_contacts (
        whatsapp_number, display_name, platform,
        is_active, created_at, updated_at
    )
    SELECT
        fsc.identifier,
        COALESCE(fsc.name, ''),
        fsc.platform,
        TRUE,
        COALESCE(fsc.created_at, NOW()),
        NOW()
    FROM fazle_social_contacts fsc
    WHERE NOT EXISTS (
        SELECT 1 FROM wbom_contacts wc
        WHERE wc.whatsapp_number = fsc.identifier
          AND wc.platform = fsc.platform
    )
    ON CONFLICT (whatsapp_number, platform) DO NOTHING;
    RAISE NOTICE 'STEP 5b: fazle_social_contacts migrated';
EXCEPTION WHEN undefined_table THEN
    RAISE NOTICE 'STEP 5b: fazle_social_contacts not found — skipping';
END $$;


-- =========================================================
-- STEP 6: Migrate fazle_social_messages → wbom_whatsapp_messages
-- =========================================================
DO $$ BEGIN
    INSERT INTO wbom_whatsapp_messages (
        sender_number, message_type, message_body, direction,
        contact_identifier, ai_response, metadata_json, platform,
        content_type, is_processed, received_at, status
    )
    SELECT
        COALESCE(fsm.contact_identifier, ''),
        COALESCE(fsm.direction, 'incoming'),
        COALESCE(fsm.content, fsm.message_text, ''),
        COALESCE(fsm.direction, 'incoming'),
        COALESCE(fsm.contact_identifier, ''),
        COALESCE(fsm.ai_response, ''),
        COALESCE(fsm.metadata, '{}')::jsonb,
        COALESCE(fsm.platform, 'whatsapp'),
        'text',
        CASE WHEN fsm.status IN ('sent', 'delivered', 'read') THEN TRUE ELSE FALSE END,
        COALESCE(fsm.created_at, NOW()),
        COALESCE(fsm.status, 'received')
    FROM fazle_social_messages fsm
    WHERE NOT EXISTS (
        SELECT 1 FROM wbom_whatsapp_messages wm
        WHERE wm.contact_identifier = COALESCE(fsm.contact_identifier, '')
          AND wm.received_at = COALESCE(fsm.created_at, NOW())
          AND wm.direction = COALESCE(fsm.direction, 'incoming')
    );
    RAISE NOTICE 'STEP 6: fazle_social_messages migrated';
EXCEPTION WHEN undefined_table THEN
    RAISE NOTICE 'STEP 6: fazle_social_messages not found — skipping';
END $$;


-- =========================================================
-- STEP 7: Add constraints
-- =========================================================
DO $$ BEGIN
    CREATE UNIQUE INDEX IF NOT EXISTS idx_wbom_tx_dedup_migration
        ON wbom_cash_transactions (employee_id, amount, transaction_date, created_by)
        WHERE created_by = 'migration_ops';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;


-- =========================================================
-- STEP 8: Add indexes
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_wbom_contacts_platform ON wbom_contacts (platform);
CREATE INDEX IF NOT EXISTS idx_wbom_contacts_last_seen ON wbom_contacts (last_seen DESC);
CREATE INDEX IF NOT EXISTS idx_wbom_contacts_phone ON wbom_contacts (whatsapp_number);
CREATE INDEX IF NOT EXISTS idx_wbom_msg_direction ON wbom_whatsapp_messages (direction);
CREATE INDEX IF NOT EXISTS idx_wbom_msg_platform ON wbom_whatsapp_messages (platform);
CREATE INDEX IF NOT EXISTS idx_wbom_msg_contact_identifier ON wbom_whatsapp_messages (contact_identifier);
CREATE INDEX IF NOT EXISTS idx_wbom_msg_received_at ON wbom_whatsapp_messages (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_wbom_msg_platform_direction ON wbom_whatsapp_messages (platform, direction);
CREATE INDEX IF NOT EXISTS idx_wbom_msg_status ON wbom_whatsapp_messages (status);


-- =========================================================
-- STEP 9: Validation counts (logged via NOTICE)
-- =========================================================
DO $$ DECLARE
    v_ops_emp INT := 0;
    v_ops_pay INT := 0;
    v_fc INT := 0;
    v_fsc INT := 0;
    v_fsm INT := 0;
    v_wbom_emp INT;
    v_wbom_tx INT;
    v_wbom_contacts INT;
    v_wbom_msg INT;
BEGIN
    BEGIN SELECT COUNT(*) INTO v_ops_emp FROM ops_employees; EXCEPTION WHEN undefined_table THEN v_ops_emp := 0; END;
    BEGIN SELECT COUNT(*) INTO v_ops_pay FROM ops_payments; EXCEPTION WHEN undefined_table THEN v_ops_pay := 0; END;
    BEGIN SELECT COUNT(*) INTO v_fc FROM fazle_contacts; EXCEPTION WHEN undefined_table THEN v_fc := 0; END;
    BEGIN SELECT COUNT(*) INTO v_fsc FROM fazle_social_contacts; EXCEPTION WHEN undefined_table THEN v_fsc := 0; END;
    BEGIN SELECT COUNT(*) INTO v_fsm FROM fazle_social_messages; EXCEPTION WHEN undefined_table THEN v_fsm := 0; END;

    SELECT COUNT(*) INTO v_wbom_emp FROM wbom_employees;
    SELECT COUNT(*) INTO v_wbom_tx FROM wbom_cash_transactions;
    SELECT COUNT(*) INTO v_wbom_contacts FROM wbom_contacts;
    SELECT COUNT(*) INTO v_wbom_msg FROM wbom_whatsapp_messages;

    RAISE NOTICE '========== MIGRATION VALIDATION ==========';
    RAISE NOTICE 'ops_employees: % → wbom_employees: %', v_ops_emp, v_wbom_emp;
    RAISE NOTICE 'ops_payments: % → wbom_cash_transactions: %', v_ops_pay, v_wbom_tx;
    RAISE NOTICE 'fazle_contacts: % → wbom_contacts: %', v_fc, v_wbom_contacts;
    RAISE NOTICE 'fazle_social_contacts: % → (merged into wbom_contacts): %', v_fsc, v_wbom_contacts;
    RAISE NOTICE 'fazle_social_messages: % → wbom_whatsapp_messages: %', v_fsm, v_wbom_msg;
    RAISE NOTICE '==========================================';
END $$;


-- =========================================================
-- STEP 10: Rename legacy tables as backup (NOT drop)
-- =========================================================
DO $$ BEGIN ALTER TABLE ops_employees RENAME TO _legacy_ops_employees; EXCEPTION WHEN undefined_table THEN NULL; WHEN duplicate_table THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE ops_payments RENAME TO _legacy_ops_payments; EXCEPTION WHEN undefined_table THEN NULL; WHEN duplicate_table THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fazle_contacts RENAME TO _legacy_fazle_contacts; EXCEPTION WHEN undefined_table THEN NULL; WHEN duplicate_table THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fazle_social_messages RENAME TO _legacy_fazle_social_messages; EXCEPTION WHEN undefined_table THEN NULL; WHEN duplicate_table THEN NULL; END $$;
DO $$ BEGIN ALTER TABLE fazle_social_contacts RENAME TO _legacy_fazle_social_contacts; EXCEPTION WHEN undefined_table THEN NULL; WHEN duplicate_table THEN NULL; END $$;


-- end of migration 016
