import pytest
from app.services.allocation_approval_contract import (
    AllocationApprovalBlocked,create_review_packet,evaluate_review_actor,
    require_financial_publication_authorization)

H="a"*64
RUN="00000000-0000-0000-0000-000000000012"


def metadata(**kw):
    x={"tenant_id":"company-A","period":"2026-09","scope_hash":H,
       "source_snapshot_hash":H,"mapping_review_hash":H,"rules_hash":H,
       "coverage_hash":H,"result_hash":H,"creator_id":"operator-1","run_id":RUN,
       "calculation_status":"SUCCEEDED","unresolved_issue_count":0,
       "source_coverage_approved":True,"mapping_authority_approved":True,
       "rules_approved":True,"financial_sum_verified":True}
    x.update(kw)
    return x

def packet(**changes):
    return create_review_packet(metadata(**changes), expected_tenant="company-A",
                                expected_period="2026-09")

def principal(**kw):
    return dict({"user_id":"finance-1","tenant_id":"company-A","roles":["finance_approver"]},**kw)

def decision(p):
    return {"run_id":p["run_id"],"request_hash":p["request_hash"],"expected_revision":1}


def test_packet_not_financial_approval_despite_input_signoff_flags():
    p=packet()
    assert not p["financial_approved"] and not p["publication_allowed"]
    assert p["status"]=="PENDING_TRUSTED_REVIEW"


@pytest.mark.parametrize("field,val,error",[
    ("source_coverage_approved",False,"COVERAGE"),
    ("mapping_authority_approved",False,"MAPPING"),
    ("rules_approved",False,"RULES"),
    ("financial_sum_verified",False,"CONSERVATION"),
    ("calculation_status","PARTIAL","CALCULATION"),
    ("unresolved_issue_count",1,"CALCULATION")])
def test_missing_business_evidence_fails(field,val,error):
    with pytest.raises(AllocationApprovalBlocked,match=error):
        packet(**{field:val})


def test_cross_tenant_metadata_blocks():
    with pytest.raises(AllocationApprovalBlocked,match="TENANT"):
        packet(tenant_id="company-B")


def test_cross_tenant_reviewer_blocks():
    p=packet()
    with pytest.raises(AllocationApprovalBlocked,match="TENANT"):
        evaluate_review_actor(p,principal={"user_id":"finance","tenant_id":"other","roles":["finance_approver"]},
                              reviewer_attestation=decision(p),expected_tenant="company-A",expected_revision=1)


def test_creator_cannot_approve_self():
    p=packet()
    with pytest.raises(AllocationApprovalBlocked,match="FOUR_EYES"):
        evaluate_review_actor(p,principal={"user_id":"operator-1","tenant_id":"company-A","roles":["finance_approver"]},
                              reviewer_attestation=decision(p),expected_tenant="company-A",expected_revision=1)


def test_operator_without_approver_permission_blocks():
    p=packet()
    with pytest.raises(AllocationApprovalBlocked,match="ROLE_REQUIRED"):
        evaluate_review_actor(p,principal={"user_id":"member","tenant_id":"company-A","roles":["operator"]},
                              reviewer_attestation=decision(p),expected_tenant="company-A",expected_revision=1)


def test_revision_change_refused():
    p=packet()
    with pytest.raises(AllocationApprovalBlocked,match="REVISION_INVALID"):
        evaluate_review_actor(p,principal=principal(),reviewer_attestation=decision(p),
                              expected_tenant="company-A",expected_revision=2)


def test_tampered_request_refused():
    p=packet();p["run_id"]=RUN.replace("012","013")
    with pytest.raises(AllocationApprovalBlocked,match="TAMPERED"):
        evaluate_review_actor(p,principal=principal(),reviewer_attestation=decision(p),
                              expected_tenant="company-A",expected_revision=1)


def test_without_backend_verifier_never_accepts_bool():
    p=packet()
    with pytest.raises(AllocationApprovalBlocked,match="VERIFIER_UNAVAILABLE"):
        evaluate_review_actor(p,principal=principal(),reviewer_attestation=decision(p),
                              expected_tenant="company-A",expected_revision=1)


def test_backend_verifier_precheck_cannot_publish():
    p=packet()
    result=evaluate_review_actor(p,principal=principal(),reviewer_attestation=decision(p),
                                 expected_tenant="company-A",expected_revision=1,
                                 trusted_verifier=lambda a,b,c:True)
    assert result["status"]=="ATTESTATION_PRECHECK_PASSED_NOT_APPLIED"
    assert result["publication_allowed"] is False and result["signoff_persisted"] is False


def test_false_backend_signature_blocks():
    p=packet()
    with pytest.raises(AllocationApprovalBlocked,match="SIGNATURE_INVALID"):
        evaluate_review_actor(p,principal=principal(),reviewer_attestation=decision(p),
                              expected_tenant="company-A",expected_revision=1,
                              trusted_verifier=lambda a,b,c:False)


def test_even_positive_attestation_never_authorizes_publication():
    with pytest.raises(AllocationApprovalBlocked,match="NOT_CONNECTED"):
        require_financial_publication_authorization()
