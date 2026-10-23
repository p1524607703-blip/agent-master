"""Formal finance approval *preflight* contract, not an approval endpoint.

A UI boolean or a valid hash is never a verified reviewer signature. The
production identity/approval server is intentionally not connected.
"""
from datetime import datetime, timezone
from uuid import UUID
from .allocation_store import digest


class AllocationApprovalBlocked(ValueError):
    pass


FIELDS=("tenant_id","period","scope_hash","source_snapshot_hash","mapping_review_hash",
        "rules_hash","coverage_hash","result_hash","creator_id","run_id")


def _nonempty_str(x):
    return type(x) is str and bool(x.strip()) and len(x)<=256 and "\x00" not in x


def create_review_packet(metadata, *, expected_tenant, expected_period):
    """Prepare immutable reviewer queue payload; no claim that data is signed."""
    if not isinstance(metadata,dict):
        raise AllocationApprovalBlocked("REVIEW_METADATA_REQUIRED")
    if not all(_nonempty_str(metadata.get(f)) for f in FIELDS):
        raise AllocationApprovalBlocked("APPROVAL_EVIDENCE_INCOMPLETE")
    if metadata["tenant_id"] != expected_tenant or metadata["period"] != expected_period:
        raise AllocationApprovalBlocked("TENANT_OR_PERIOD_SCOPE_MISMATCH")
    try:
        UUID(metadata["run_id"])
    except (ValueError,TypeError) as ex:
        raise AllocationApprovalBlocked("RUN_ID_INVALID") from ex
    for f in ("scope_hash","source_snapshot_hash","mapping_review_hash",
              "rules_hash","coverage_hash","result_hash"):
        v=metadata[f]
        if len(v)!=64 or any(c not in "0123456789abcdef" for c in v):
            raise AllocationApprovalBlocked("SHA256_EVIDENCE_INVALID:"+f)
    if metadata.get("calculation_status")!="SUCCEEDED" or metadata.get("unresolved_issue_count")!=0:
        raise AllocationApprovalBlocked("FINANCIAL_CALCULATION_NOT_COMPLETE")
    if metadata.get("source_coverage_approved") is not True:
        raise AllocationApprovalBlocked("COVERAGE_SIGNOFF_REQUIRED")
    if metadata.get("mapping_authority_approved") is not True:
        raise AllocationApprovalBlocked("MAPPING_SIGNOFF_REQUIRED")
    if metadata.get("rules_approved") is not True:
        raise AllocationApprovalBlocked("RULES_SIGNOFF_REQUIRED")
    if metadata.get("financial_sum_verified") is not True:
        raise AllocationApprovalBlocked("CAMPAIGN_CONSERVATION_SIGNOFF_REQUIRED")
    # Flags describe what a hypothetical upstream system claims; no trusted IAM check is connected.
    result={f:metadata[f] for f in FIELDS}
    result.update({"schema_version":"allocation-review-preflight-v1",
                   "unverified_source_declarations":{f:metadata[f] for f in
                      ("source_coverage_approved","mapping_authority_approved",
                       "rules_approved","financial_sum_verified")},
                   "status":"PENDING_TRUSTED_REVIEW",
                   "financial_approved":False,"publication_allowed":False,
                   "signature_verification_connected":False})
    result["request_hash"]=digest(result)
    return result


def evaluate_review_actor(packet, *, principal, reviewer_attestation, trusted_verifier=None,
                          expected_tenant, expected_revision):
    """Check scope & four-eyes separation but never grant publication.

    trusted_verifier must be a backend-owned callable injected by the future IAM
    adapter, not user request data; its callback result alone cannot publish.
    """
    if not isinstance(packet,dict) or packet.get("request_hash")!=digest(
            {k:v for k,v in packet.items() if k!="request_hash"}):
        raise AllocationApprovalBlocked("REVIEW_PACKET_TAMPERED")
    if packet.get("tenant_id")!=expected_tenant:
        raise AllocationApprovalBlocked("REVIEW_CROSS_TENANT")
    if not isinstance(principal,dict) or not _nonempty_str(principal.get("user_id")):
        raise AllocationApprovalBlocked("AUTHENTICATED_PRINCIPAL_REQUIRED")
    if principal["user_id"]==packet["creator_id"]:
        raise AllocationApprovalBlocked("FOUR_EYES_SEPARATION_REQUIRED")
    if principal.get("tenant_id")!=expected_tenant:
        raise AllocationApprovalBlocked("REVIEWER_TENANT_SCOPE_INVALID")
    if "finance_approver" not in principal.get("roles",[]):
        raise AllocationApprovalBlocked("FINANCE_APPROVER_ROLE_REQUIRED")
    if not isinstance(reviewer_attestation,dict) or reviewer_attestation.get("run_id")!=packet["run_id"]:
        raise AllocationApprovalBlocked("REVIEW_RUN_MISMATCH")
    if reviewer_attestation.get("request_hash")!=packet["request_hash"]:
        raise AllocationApprovalBlocked("REVIEW_VERSION_MISMATCH")
    if type(expected_revision) is not int or expected_revision<1 or reviewer_attestation.get("expected_revision")!=expected_revision:
        raise AllocationApprovalBlocked("REVIEW_CAS_REVISION_INVALID")
    if not callable(trusted_verifier):
        raise AllocationApprovalBlocked("TRUSTED_ATTESTATION_VERIFIER_UNAVAILABLE")
    authenticated=trusted_verifier(principal,reviewer_attestation,packet)
    if authenticated is not True:
        raise AllocationApprovalBlocked("REVIEW_SIGNATURE_INVALID")
    return {"run_id":packet["run_id"],"tenant_id":expected_tenant,
            "request_hash":packet["request_hash"],"reviewer_id":principal["user_id"],
            "expected_revision":expected_revision,
            "status":"ATTESTATION_PRECHECK_PASSED_NOT_APPLIED",
            "financial_approved":False,"publication_allowed":False,
            "signoff_persisted":False}


def require_financial_publication_authorization(*args,**kwargs):
    raise AllocationApprovalBlocked("PRODUCTION_REVIEW_AND_PUBLICATION_API_NOT_CONNECTED")
