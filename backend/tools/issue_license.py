#!/usr/bin/env python3
"""
tools/issue_license.py
라이선스 발급 도구 — 판매사 내부에서만 사용.

사용법:
  python tools/issue_license.py \\
    --customer "안양 캐피탈" \\
    --edition enterprise \\
    --expires 2027-04-18 \\
    --license-id ENT-2026-0001 \\
    --privkey data/_license_privkey_DEV_ONLY.pem \\
    --output ./license.key

  # 커스텀 기능 플래그
  python tools/issue_license.py ... --features '{"max_concurrent_jobs":20}'

**경고**: 개인키는 판매사 내부에서만 보관. 고객에게 배포 금지.
"""
import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path


def load_private_key(path: Path):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    return load_pem_private_key(path.read_bytes(), password=None)


def sign_payload(private_key, payload: dict) -> str:
    """payload를 canonical JSON으로 직렬화 후 Ed25519 서명"""
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(payload_bytes)
    return base64.b64encode(signature).decode("ascii")


def main():
    ap = argparse.ArgumentParser(description="DataBridge Studio 라이선스 발급")
    ap.add_argument("--customer",   required=True, help="고객사명")
    ap.add_argument("--edition",    required=True, choices=["standard", "enterprise"])
    ap.add_argument("--expires",    required=True, help="만료일 ISO date (예: 2027-04-18)")
    ap.add_argument("--license-id", required=True, help="라이선스 ID (고유)")
    ap.add_argument("--privkey",    required=True, help="판매사 개인키 경로")
    ap.add_argument("--output",     default="./license.key", help="출력 파일")
    ap.add_argument("--features",   default="{}", help="커스텀 feature flags JSON (override)")
    ap.add_argument("--issued-at",  default=None, help="발급일 (기본: 오늘)")
    args = ap.parse_args()

    # 개인키 로드
    priv_path = Path(args.privkey)
    if not priv_path.exists():
        sys.exit(f"개인키 파일 없음: {priv_path}")
    private_key = load_private_key(priv_path)

    # payload 구성
    payload = {
        "customer":    args.customer,
        "edition":     args.edition,
        "issued_at":   args.issued_at or datetime.now().date().isoformat(),
        "expires_at":  args.expires,
        "license_id":  args.license_id,
        "features":    json.loads(args.features),
    }

    # 서명
    signature = sign_payload(private_key, payload)

    # 라이선스 파일 작성
    license_data = {
        "payload":   payload,
        "signature": signature,
        "_readme":   "이 파일을 프로젝트 루트에 'license.key' 로 저장하거나, DATABRIDGE_LICENSE_PATH 환경변수로 경로를 지정하세요.",
    }
    out_path = Path(args.output)
    out_path.write_text(json.dumps(license_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✓ 라이선스 발급 완료: {out_path}")
    print(f"  고객: {payload['customer']}")
    print(f"  Edition: {payload['edition']}")
    print(f"  유효기간: {payload['issued_at']} ~ {payload['expires_at']}")
    print(f"  라이선스 ID: {payload['license_id']}")


if __name__ == "__main__":
    main()
