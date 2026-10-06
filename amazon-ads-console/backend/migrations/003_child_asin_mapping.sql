BEGIN;

CREATE TABLE IF NOT EXISTS app.child_asin_mapping (
    account_scope TEXT NOT NULL,
    child_asin TEXT NOT NULL,
    product_code TEXT NOT NULL,
    parent_asin TEXT,
    brand TEXT,
    operator_group TEXT NOT NULL,
    mapping_status TEXT NOT NULL DEFAULT 'parent_inherited',
    source TEXT NOT NULL DEFAULT 'business_child_parent_inheritance',
    confidence TEXT NOT NULL DEFAULT 'inherited',
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    effective_date DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_scope, child_asin),
    CONSTRAINT child_asin_format_ck CHECK (child_asin ~ '^B[0-9A-Z]{9}$'),
    CONSTRAINT child_mapping_status_ck CHECK (mapping_status IN ('parent_inherited','explicit','blocked_conflict'))
);

CREATE INDEX IF NOT EXISTS idx_child_mapping_parent ON app.child_asin_mapping(parent_asin);
CREATE INDEX IF NOT EXISTS idx_child_mapping_product ON app.child_asin_mapping(product_code);
CREATE INDEX IF NOT EXISTS idx_child_mapping_group ON app.child_asin_mapping(operator_group);

COMMENT ON TABLE app.child_asin_mapping IS
'账户级 Child ASIN -> 产品/运营映射。parent_inherited 仅是由当前唯一 Parent 映射继承，可被 explicit 覆盖；不按产品号合并。';

COMMIT;
