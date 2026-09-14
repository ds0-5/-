# app/security.py
# 用途：签发和验证「通行证」（token）
# 原理：把用户信息 + 过期时间打包，用服务器密钥签名。改一个字，签名就对不上。

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Header, HTTPException

# 服务器密钥：优先从环境变量读，没有就用默认值（生产环境必须配环境变量）
SECRET = os.environ.get("YINKU_SECRET", "yinku-dev-secret-change-me")

# 通行证有效期（秒）：7 天
TOKEN_TTL = 7 * 24 * 3600


def _b64encode(data: bytes) -> str:
    """把二进制转成 URL 安全的字符串（去掉末尾的 =）"""
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(s: str) -> bytes:
    """补回被去掉的 =，再转回二进制"""
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def _sign(payload_b64: str) -> str:
    """用密钥给内容签名"""
    mac = hmac.new(SECRET.encode(), payload_b64.encode(), hashlib.sha256)
    return _b64encode(mac.digest())


def make_token(user_id: str) -> str:
    """签发通行证：内容 + 签名"""
    payload = {"user_id": user_id, "exp": int(time.time()) + TOKEN_TTL}
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    return payload_b64 + "." + _sign(payload_b64)


def read_token(token: str):
    """验证通行证。有效 → 返回 user_id；无效或过期 → 返回 None"""
    if not token or "." not in token:
        return None
    payload_b64, sig = token.split(".", 1)

    # 1) 先验签名：签名不对，说明内容被改过，直接拒
    if not hmac.compare_digest(_sign(payload_b64), sig):
        return None

    # 2) 再验过期
    try:
        payload = json.loads(_b64decode(payload_b64))
    except Exception:
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None

    return payload.get("user_id")

# ===== FastAPI 依赖：从请求头取通行证，验证后给出 user_id =====
def current_user(authorization: str = Header(default="")) -> str:
    """从请求头 Authorization: Bearer <token> 里取出并验证通行证。

    验证通过 → 返回 user_id；失败 → 报 401。
    """
    token = authorization[7:] if authorization.startswith("Bearer ") else ""
    user_id = read_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    return user_id
