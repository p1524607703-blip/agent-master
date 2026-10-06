# Validation Report - amazon-ads-mcp-public-test (Stage 1)

## Timestamp

2026-08-22T08:43:50Z

## Stage 1: Spec Compliance (Subagent: spec-reviewer)

- Status: PASS
- Issues found: 0
- Coverage: Approved region and existing VPC/VSwitch/RDS values remain fixed; the plan contains exactly one enterprise security group, one `/32:5432` egress rule, two invocation-disabled functions and two concurrency limits. It contains no triggers, versions, aliases, RAM roles, OSS, domains, logs, NAT, EIP, RDS changes, plugin changes or tunnel changes.
- Deferred gate: Stage two cannot start until both cloud functions prove matching CRC64, code size, successful update status and disabled invocation.

## Stage 2: Code Quality (Subagent: code-quality-reviewer)

- Status: PASS
- Critical issues: 0
- Important issues: 0
- Security: 9/10
- Reliability: 9/10
- Maintainability: 8/10
- Performance: 9/10
- Compliance: 9/10
- Verified: `GetFunction → ETag → If-Match UpdateFunction`, server-side CRC64 submission, post-update code checksum/size/status/restriction/internet checks, no credential persistence, no public trigger and fail-closed stage-one network boundaries.
- Follow-up recommendations were applied: `--check-only` no longer requires credentials, and public-network disablement is checked before upload.

## Remote Syntax and Plan

- `iacservice validate-module`: SKIPPED because the MCP CLI endpoint is not published/configured for this account binding.
- Stronger remote check: PASS via Alibaba Cloud RunIaC with Terraform 1.5.7 and aliyun/alicloud 1.289.0.
- Process: `iac_58637953-7617-4708-a004-f4503cd4626a`
- Result: `Plan: 6 to add, 0 to change, 0 to destroy.`
- Data-source reads for the approved VPC and VSwitch succeeded.

## Application Verification

- `uv run pytest -q`: 38 passed.
- Package size: `15,581,274` bytes.
- SHA-256: `be93e6313650bb0e45768fede0db8bda8dc1da12052de2553d76b8f6789819ca`.
- CRC64/ECMA (Go `hash/crc64.ECMA` compatible): `17688003829125096702`.

## Final Result

- Overall: PASS for stage-one apply.
- Both independent review stages PASS.
- Remote plan PASS with no modify or destroy actions.
