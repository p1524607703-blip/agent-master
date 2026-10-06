# Terraform Plan Results - amazon-ads-mcp-public-test (Stage 1)

## Timestamp

2026-08-22T08:37:05Z

## Process ID

`iac_58637953-7617-4708-a004-f4503cd4626a`

## Status

SUCCESS — `Plan: 6 to add, 0 to change, 0 to destroy.`

## Provider

- Terraform 1.5.7
- aliyun/alicloud 1.289.0

## Resources to Create

| Resource | Name | Safety boundary |
| --- | --- | --- |
| `alicloud_security_group` | `amazon-ads-mcp-test` | Enterprise/default deny |
| `alicloud_security_group_rule` | `allow_rds_postgresql` | Egress only to `172.24.45.78/32`, TCP 5432 |
| `alicloud_fcv3_function` | `amazon-ads-ops-test-20260822` | Invocation disabled, no trigger, no internet |
| `alicloud_fcv3_function` | `amazon-ads-admin-test-20260822` | Invocation disabled, no trigger, no internet |
| `alicloud_fcv3_concurrency_config` | ops | Reserved concurrency 1 |
| `alicloud_fcv3_concurrency_config` | admin | Reserved concurrency 1 |

## Existing Resources Read Only

- VPC `vpc-bp1lp8evhwpwcdkz49a4j`
- VSwitch `vsw-bp1sthn5indxyktma18m7`

## Destructive or Unexpected Changes

- Modify: 0
- Destroy: 0
- Existing RDS/plugin/tunnel/application changes: 0
