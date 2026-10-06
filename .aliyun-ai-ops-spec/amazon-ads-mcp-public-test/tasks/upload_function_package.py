#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import time
from pathlib import Path

from alibabacloud_fc20230330 import models as fc_models
from alibabacloud_fc20230330.client import Client as FCClient
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models


PROFILE_NAME = "codex-cloud-ops-admin"
ACCOUNT_ID = "1196770313768470"
REGION = "cn-hangzhou"
FUNCTION_NAMES = (
    "amazon-ads-ops-test-20260822",
    "amazon-ads-admin-test-20260822",
)
EXPECTED_SHA256 = "be93e6313650bb0e45768fede0db8bda8dc1da12052de2553d76b8f6789819ca"
CRC64_ECMA_REVERSED_POLYNOMIAL = 0xC96C5795D7870F42
CRC64_MASK = 0xFFFFFFFFFFFFFFFF


def load_profile() -> dict[str, object]:
    config_path = Path.home() / ".aliyun" / "config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    profile = next(
        (item for item in payload.get("profiles", []) if item.get("name") == PROFILE_NAME),
        None,
    )
    if profile is None:
        raise RuntimeError(f"Alibaba Cloud profile {PROFILE_NAME!r} was not found")
    required = ("access_key_id", "access_key_secret", "sts_token", "sts_expiration")
    if any(not profile.get(key) for key in required):
        raise RuntimeError("Alibaba Cloud OAuth profile is missing temporary credentials")
    if int(profile["sts_expiration"]) <= int(time.time()) + 120:
        raise RuntimeError("Alibaba Cloud OAuth authorization expires in less than two minutes")
    return profile


def crc64_ecma(data: bytes) -> int:
    table = []
    for value in range(256):
        checksum = value
        for _ in range(8):
            checksum = (
                (checksum >> 1) ^ CRC64_ECMA_REVERSED_POLYNOMIAL
                if checksum & 1
                else checksum >> 1
            )
        table.append(checksum)
    checksum = CRC64_MASK
    for value in data:
        checksum = table[(checksum ^ value) & 0xFF] ^ (checksum >> 8)
    return checksum ^ CRC64_MASK


def load_package(path: Path) -> tuple[bytes, str, str]:
    package = path.read_bytes()
    digest = hashlib.sha256(package).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Package SHA-256 mismatch: {digest}")
    return package, digest, str(crc64_ecma(package))


def create_client(profile: dict[str, object]) -> FCClient:
    config = open_api_models.Config(
        access_key_id=str(profile["access_key_id"]),
        access_key_secret=str(profile["access_key_secret"]),
        security_token=str(profile["sts_token"]),
    )
    config.endpoint = f"{ACCOUNT_ID}.{REGION}.fc.aliyuncs.com"
    return FCClient(config)


def get_function(client: FCClient, function_name: str):
    return client.get_function_with_options(
        function_name,
        fc_models.GetFunctionRequest(),
        {},
        util_models.RuntimeOptions(read_timeout=30_000, connect_timeout=10_000),
    )


def upload(
    client: FCClient,
    function_name: str,
    package: bytes,
    expected_crc64: str,
) -> dict[str, object]:
    before = get_function(client, function_name)
    restriction = getattr(before.body, "invocation_restriction", None)
    if restriction is None or restriction.disable is not True:
        raise RuntimeError(f"Invocation must remain disabled for {function_name}")
    if before.body.internet_access is not False:
        raise RuntimeError(f"Internet access must remain disabled for {function_name}")
    etag = next(
        (value for key, value in (before.headers or {}).items() if key.lower() == "etag"),
        None,
    )
    if not etag:
        raise RuntimeError(f"GetFunction did not return an ETag for {function_name}")
    code = fc_models.InputCodeLocation(
        checksum=expected_crc64,
        zip_file=base64.b64encode(package).decode("ascii")
    )
    request = fc_models.UpdateFunctionRequest(
        body=fc_models.UpdateFunctionInput(code=code)
    )
    response = client.update_function_with_options(
        function_name,
        request,
        {"If-Match": etag},
        util_models.RuntimeOptions(read_timeout=120_000, connect_timeout=10_000),
    )
    body = response.body
    for _ in range(15):
        if body.last_update_status == "Successful":
            break
        time.sleep(2)
        body = get_function(client, function_name).body
    if body.last_update_status != "Successful":
        raise RuntimeError(f"Cloud update did not become successful for {function_name}")
    restriction = getattr(body, "invocation_restriction", None)
    if int(body.code_size or 0) != len(package):
        raise RuntimeError(f"Cloud package size mismatch for {function_name}")
    if str(body.code_checksum) != expected_crc64:
        raise RuntimeError(f"Cloud package CRC-64 mismatch for {function_name}")
    if restriction is None or restriction.disable is not True:
        raise RuntimeError(f"Invocation restriction changed for {function_name}")
    if body.internet_access is not False:
        raise RuntimeError(f"Internet access changed for {function_name}")
    return {
        "function_name": function_name,
        "code_size": body.code_size,
        "code_checksum": body.code_checksum,
        "last_update_status": body.last_update_status,
        "state": body.state,
        "invocation_disabled": restriction.disable,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    package, digest, crc64 = load_package(args.package)
    if args.check_only:
        print(
            json.dumps(
                {"ready": True, "size": len(package), "sha256": digest, "crc64": crc64}
            )
        )
        return

    profile = load_profile()
    client = create_client(profile)
    results = [upload(client, name, package, crc64) for name in FUNCTION_NAMES]
    checksums = {item["code_checksum"] for item in results}
    if len(checksums) != 1:
        raise RuntimeError("The two cloud functions returned different code checksums")
    print(
        json.dumps(
            {"sha256": digest, "crc64": crc64, "functions": results},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
