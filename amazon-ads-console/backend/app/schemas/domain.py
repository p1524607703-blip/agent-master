from enum import Enum
from pydantic import BaseModel

class AllocationMethod(str, Enum):
    campaign_code = "campaign_code"
    advertised_product = "advertised_product"
    mixed_split = "mixed_split"
    fixed_equal_split = "fixed_equal_split"
    manual_confirmed = "manual_confirmed"

class AdTypeL1(str, Enum):
    SP="SP"; SB="SB"; SD="SD"; STV="STV"

class AdTypeL2(str, Enum):
    SP_MANUAL="SP_MANUAL"; SP_AUTO="SP_AUTO"; SB_HEADLINE="SB_HEADLINE"; SB_VIDEO="SB_VIDEO"; SD_DISPLAY="SD_DISPLAY"; STV_STREAMING="STV_STREAMING"

ISSUE_CODES = {"operator_unresolved","UNCLASSIFIED","ad_units_field_missing","campaign_allocation_not_conserved","ad_type_rollup_not_conserved"}
CLASSIFICATION_PRIORITY = ["confirmed_campaign_mapping","platform_metadata","dedicated_report_source","name_fallback","unresolved"]
ANALYTIC_GRAINS = {
    "product_daily_summary": ["product","date"],
    "product_daily_ad_type_l1": ["product","date","ad_type_l1"],
    "product_daily_ad_type_l2": ["product","date","ad_type_l1","ad_type_l2"],
}

class HealthResponse(BaseModel):
    status: str
    database_mode: str
