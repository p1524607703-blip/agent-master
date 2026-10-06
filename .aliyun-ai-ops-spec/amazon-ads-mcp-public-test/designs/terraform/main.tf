terraform {
  required_version = ">= 1.5"

  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.284"
    }
  }
}

provider "alicloud" {
  region               = var.region
  configuration_source = "AlibabaCloud-Agent-Toolkit/alibabacloud-spec-ops"
}

variable "region" {
  type        = string
  description = "Alibaba Cloud region for the isolated test resources."
  default     = "cn-hangzhou"

  validation {
    condition     = var.region == "cn-hangzhou"
    error_message = "This test is approved only for cn-hangzhou."
  }
}

variable "existing_vpc_id" {
  type        = string
  description = "Existing VPC ID that contains the approved RDS instance."
  default     = "vpc-bp1lp8evhwpwcdkz49a4j"

  validation {
    condition     = can(regex("^vpc-[0-9a-z]+$", var.existing_vpc_id))
    error_message = "existing_vpc_id must be an Alibaba Cloud VPC ID."
  }
}

variable "existing_vswitch_id" {
  type        = string
  description = "Existing VSwitch ID used by the two isolated functions."
  default     = "vsw-bp1sthn5indxyktma18m7"

  validation {
    condition     = can(regex("^vsw-[0-9a-z]+$", var.existing_vswitch_id))
    error_message = "existing_vswitch_id must be an Alibaba Cloud VSwitch ID."
  }
}

variable "database_host" {
  type        = string
  description = "TLS hostname of the existing RDS PostgreSQL private endpoint."
  default     = "pgm-bp18chyrycgz5q42.pg.rds.aliyuncs.com"

  validation {
    condition     = can(regex("^[a-z0-9-]+\\.pg\\.rds\\.aliyuncs\\.com$", var.database_host))
    error_message = "database_host must be an RDS PostgreSQL hostname."
  }
}

variable "database_hostaddr" {
  type        = string
  description = "Verified private IPv4 address of the existing RDS endpoint."
  default     = "172.24.45.78"

  validation {
    condition     = can(cidrhost("${var.database_hostaddr}/32", 0))
    error_message = "database_hostaddr must be a valid IPv4 address."
  }
}

variable "database_name" {
  type        = string
  description = "Existing PostgreSQL database name."
  default     = "amazon_ads"

  validation {
    condition     = can(regex("^[a-z_][a-z0-9_]*$", var.database_name))
    error_message = "database_name must be a valid unquoted PostgreSQL identifier."
  }
}

variable "ops_test_verification_key" {
  type        = string
  description = "Public Ed25519 verification key for the short-lived ops test envelope."
  default     = "osFuJ3YppcJ1NjuogSAhNrhbaBd0tP3ueuBttnsG3qU"

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{43}$", var.ops_test_verification_key))
    error_message = "ops_test_verification_key must be a 32-byte base64url Ed25519 public key."
  }
}

variable "admin_test_verification_key" {
  type        = string
  description = "Public Ed25519 verification key for the short-lived admin test envelope."
  default     = "gZfFdYhTk4zv_HmGiSqPyDKhy2akvjnHhx-xGPfUDtA"

  validation {
    condition     = can(regex("^[A-Za-z0-9_-]{43}$", var.admin_test_verification_key))
    error_message = "admin_test_verification_key must be a 32-byte base64url Ed25519 public key."
  }
}

variable "project_name" {
  type        = string
  description = "Tag value used to identify only this isolated test deployment."
  default     = "amazon-ads-mcp-public-test"

  validation {
    condition     = var.project_name == "amazon-ads-mcp-public-test"
    error_message = "This state is reserved for amazon-ads-mcp-public-test."
  }
}

locals {
  placeholder_zip_b64 = "UEsDBBQAAAAIAFgiFl1IpdVAcwAAAHwAAAAJABwAYm9vdHN0cmFwVVQJAANoW4lqaFuJanV4CwABBPUBAAAEFAAAAB2MMQ7CMAwA977ChKETSiXEkpUnlG6VkNsaMAqOlZhKFerfoQy33d1+5wcWXx6VZha7Qd0a2rsEODVHaCnPPBJ0gjNyxCFSn3s5JzESO1wWpQCoGnlE4yT+WZJsxsbHlf/KBTeRxrS8fs1VSSaWu1vr6gtQSwECHgMUAAAACABYIhZdSKXVQHMAAAB8AAAACQAYAAAAAAABAAAA7YEAAAAAYm9vdHN0cmFwVVQFAANoW4lqdXgLAAEE9QEAAAQUAAAAUEsFBgAAAAABAAEATwAAALYAAAAAAA=="

  common_environment = {
    ADS_DB_HOST       = var.database_host
    ADS_DB_HOSTADDR   = var.database_hostaddr
    ADS_DB_PORT       = "5432"
    ADS_DB_NAME       = var.database_name
    ADS_DB_SSLMODE    = "verify-full"
    ADS_DB_SSLROOTCERT = "/code/ApsaraDB-CA-Chain.pem"
    ADS_DB_TIMEZONE   = "America/New_York"
    ADS_RUNTIME_ROOT  = "/tmp/amazon-ads-data"
  }

  common_tags = {
    ManagedBy   = "Terraform"
    Project     = var.project_name
    Environment = "test"
    CreatedBy   = "Codex"
  }
}

data "alicloud_vpcs" "existing" {
  ids    = [var.existing_vpc_id]
  status = "Available"
}

data "alicloud_vswitches" "existing" {
  ids     = [var.existing_vswitch_id]
  vpc_id  = one(data.alicloud_vpcs.existing.ids)
  status  = "Available"
}

resource "alicloud_security_group" "mcp_test" {
  security_group_name = "amazon-ads-mcp-test"
  description         = "Isolated security group for Amazon Ads MCP test functions."
  vpc_id              = one(data.alicloud_vpcs.existing.ids)
  security_group_type = "enterprise"
  tags                = local.common_tags
}

resource "alicloud_security_group_rule" "allow_rds_postgresql" {
  security_group_id = alicloud_security_group.mcp_test.id
  type              = "egress"
  ip_protocol       = "tcp"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "5432/5432"
  priority          = 1
  cidr_ip           = "${var.database_hostaddr}/32"
  description       = "Allow only the existing RDS PostgreSQL private endpoint."
}

resource "alicloud_fcv3_function" "ops_test" {
  function_name       = "amazon-ads-ops-test-20260822"
  description         = "Isolated 10-tool read-only Amazon Ads MCP test function."
  runtime             = "custom.debian11"
  handler             = "bootstrap"
  cpu                 = 0.25
  memory_size         = 512
  disk_size           = 512
  timeout             = 30
  instance_concurrency = 1
  internet_access     = false

  code {
    zip_file = local.placeholder_zip_b64
  }

  invocation_restriction {
    disable = true
    reason  = "Deployment package verification is not complete."
  }

  custom_runtime_config {
    port = 9000

    health_check_config {
      http_get_url         = "/healthz"
      initial_delay_seconds = 3
      period_seconds       = 10
      success_threshold    = 1
      timeout_seconds      = 2
      failure_threshold    = 3
    }
  }

  environment_variables = merge(local.common_environment, {
    ADS_MCP_MODE       = "readonly"
    ADS_DB_ROLE        = "amazon_ads_ops_reader"
    ADS_MCP_QUERY_ROLE = "amazon_ads_ops_reader"
    ADS_MCP_TEST_VERIFY_KEY_B64 = var.ops_test_verification_key
  })

  vpc_config {
    vpc_id           = one(data.alicloud_vpcs.existing.ids)
    vswitch_ids      = [one(data.alicloud_vswitches.existing.ids)]
    security_group_id = alicloud_security_group.mcp_test.id
  }

  tags       = local.common_tags
  depends_on = [alicloud_security_group_rule.allow_rds_postgresql]

  lifecycle {
    # Stage two owns code through UpdateFunction; cloud CRC-64 verification is mandatory.
    ignore_changes = [code]
  }
}

resource "alicloud_fcv3_function" "admin_test" {
  function_name       = "amazon-ads-admin-test-20260822"
  description         = "Isolated 25-tool administrator Amazon Ads MCP test function."
  runtime             = "custom.debian11"
  handler             = "bootstrap"
  cpu                 = 0.25
  memory_size         = 512
  disk_size           = 512
  timeout             = 30
  instance_concurrency = 1
  internet_access     = false

  code {
    zip_file = local.placeholder_zip_b64
  }

  invocation_restriction {
    disable = true
    reason  = "Deployment package verification is not complete."
  }

  custom_runtime_config {
    port = 9000

    health_check_config {
      http_get_url         = "/healthz"
      initial_delay_seconds = 3
      period_seconds       = 10
      success_threshold    = 1
      timeout_seconds      = 2
      failure_threshold    = 3
    }
  }

  environment_variables = merge(local.common_environment, {
    ADS_MCP_MODE             = "admin"
    ADS_DB_ROLE              = "codex_reader"
    ADS_MCP_QUERY_ROLE       = "codex_reader"
    ADS_MCP_ADMIN_AUDIT_FILE = "/tmp/amazon-ads-mcp-admin-audit.jsonl"
    ADS_MCP_ADMIN_MAX_TIMEOUT_SECONDS = "20"
    ADS_MCP_TEST_VERIFY_KEY_B64 = var.admin_test_verification_key
  })

  vpc_config {
    vpc_id           = one(data.alicloud_vpcs.existing.ids)
    vswitch_ids      = [one(data.alicloud_vswitches.existing.ids)]
    security_group_id = alicloud_security_group.mcp_test.id
  }

  tags       = local.common_tags
  depends_on = [alicloud_security_group_rule.allow_rds_postgresql]

  lifecycle {
    # Stage two owns code through UpdateFunction; cloud CRC-64 verification is mandatory.
    ignore_changes = [code]
  }
}

resource "alicloud_fcv3_concurrency_config" "ops_test" {
  function_name        = alicloud_fcv3_function.ops_test.function_name
  reserved_concurrency = 1
}

resource "alicloud_fcv3_concurrency_config" "admin_test" {
  function_name        = alicloud_fcv3_function.admin_test.function_name
  reserved_concurrency = 1
}

output "created_function_names" {
  description = "Names of the two isolated, invocation-disabled stage-one functions."
  value = [
    alicloud_fcv3_function.ops_test.function_name,
    alicloud_fcv3_function.admin_test.function_name
  ]
}
