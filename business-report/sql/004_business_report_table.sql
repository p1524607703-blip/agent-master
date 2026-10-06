-- 004_business_report_table.sql
-- 业务报告「按父商品」（详情页面销售和流量）期间事实表。
-- 由 business-report/br_to_rds.py --init-ddl 执行；可重复运行。
--
-- 期间语义：单日存 (D, D)；周快照存 (周一, 周日)。靠 report_start_date/report_end_date 区分，互不覆盖。
-- 幂等两层：① core.import_batches.file_hash 唯一（文件级）② 本表主键 ON CONFLICT DO UPDATE（行级，
--           Amazon 会回溯修正历史数据，所以要更新而不是丢弃）。
--
-- 命名：沿用「一份报告一张表」家族 report_*。同时保留旧名兼容视图，
--       让任何引用 core.business_report_parent_asin_period 的旧代码仍能解析。

BEGIN;

CREATE TABLE IF NOT EXISTS core.report_business_parent_asin_period (
    account_id                          TEXT      NOT NULL,
    account_name                        TEXT      NOT NULL,
    report_start_date                   DATE      NOT NULL,
    report_end_date                     DATE      NOT NULL,
    parent_asin                         TEXT      NOT NULL,
    title                               TEXT      NOT NULL,

    sessions_total                      BIGINT,
    sessions_b2b                        BIGINT,
    mobile_app_conversion_rate_b2b_pct  NUMERIC(12,6),
    mobile_app_session_pct              NUMERIC(12,6),
    browser_session_pct                 NUMERIC(12,6),
    browser_session_b2b_pct             NUMERIC(12,6),
    ordered_product_units               BIGINT,
    ordered_product_units_b2b           BIGINT,
    unit_session_pct                    NUMERIC(12,6),
    unit_session_b2b_pct                NUMERIC(12,6),
    ordered_product_sales               NUMERIC(18,6),
    ordered_product_sales_b2b           NUMERIC(18,6),
    total_order_items                   BIGINT,
    total_order_items_b2b               BIGINT,

    currency_code                       TEXT      NOT NULL DEFAULT 'USD',
    source_batch_id                     BIGINT,
    created_at                          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT report_business_period_ck CHECK (report_end_date >= report_start_date),
    PRIMARY KEY (account_id, report_start_date, report_end_date, parent_asin)
);

-- 外键：批次不存在时不阻塞导入（历史批次可能被清理），故用 NOT VALID 语义以外的方式 —— 直接不加 FK，
-- 只用索引保证关联查询走得上。若需要强约束，可在批次稳定后单独 ALTER ADD CONSTRAINT。
CREATE INDEX IF NOT EXISTS idx_brp_account_period
    ON core.report_business_parent_asin_period (account_id, report_start_date, report_end_date);
CREATE INDEX IF NOT EXISTS idx_brp_asin
    ON core.report_business_parent_asin_period (parent_asin);
CREATE INDEX IF NOT EXISTS idx_brp_period
    ON core.report_business_parent_asin_period (report_start_date, report_end_date);
CREATE INDEX IF NOT EXISTS idx_brp_batch
    ON core.report_business_parent_asin_period (source_batch_id);

COMMENT ON TABLE core.report_business_parent_asin_period IS
    '业务报告「按父商品」期间事实表。单日 (D,D) / 周快照 (周一,周日)。'
    '日界为太平洋时间；来自 Seller Central 详情页面销售和流量（按父商品）。';

-- 旧名兼容视图：老工具/老代码引用 core.business_report_parent_asin_period 时仍可解析
CREATE OR REPLACE VIEW core.business_report_parent_asin_period AS
SELECT * FROM core.report_business_parent_asin_period;

COMMENT ON VIEW core.business_report_parent_asin_period IS
    '兼容视图 → core.report_business_parent_asin_period。新代码请直接引用 report_ 表。';

COMMIT;
