"""KisCredentials — KIS API 인증 정보 관리

secret 원문을 repr/str/log에 노출하지 않는다.
"""
from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class KisCredentials:
    app_key: str
    app_secret: str
    base_url: str
    account_no: str | None = None
    account_product_code: str | None = None
    websocket_url: str | None = None

    def masked_dict(self) -> dict[str, str]:
        """민감값을 마스킹한 dict 반환"""
        return {
            "app_key": _mask(self.app_key),
            "app_secret": _mask(self.app_secret),
            "account_no": _mask(self.account_no) if self.account_no else "",
            "base_url": self.base_url,
            "account_product_code": self.account_product_code or "",
        }

    def __repr__(self) -> str:
        d = self.masked_dict()
        return (f"KisCredentials(app_key={d['app_key']}, "
                f"app_secret={d['app_secret']}, base_url={self.base_url})")

    def validate_required(self) -> bool:
        if not self.app_key or not self.app_secret or not self.base_url:
            raise ValueError("app_key, app_secret, and base_url are required")
        return True

    @classmethod
    def from_env(cls, env_prefix: str = "KIS_") -> "KisCredentials":
        return cls(
            app_key=os.getenv(f"{env_prefix}APP_KEY", ""),
            app_secret=os.getenv(f"{env_prefix}APP_SECRET", ""),
            base_url=os.getenv(f"{env_prefix}BASE_URL",
                               "https://openapi.koreainvestment.com:9443"),
            account_no=os.getenv(f"{env_prefix}ACCOUNT_NO"),
            account_product_code=os.getenv(f"{env_prefix}ACCOUNT_PRODUCT_CODE", "01"),
        )


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return value[:4] + "*" * (len(value) - 4)
