import base64
import hashlib
import hmac
import json
import time

JWT_SECRET = "trading-api-2024"
JWT_TTL_SECONDS = 3600


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def jwt_encode(payload: dict, secret: str = JWT_SECRET, alg: str = "HS256") -> str:
    header = {"alg": alg, "typ": "JWT"}
    body = dict(payload)
    body.setdefault("iat", int(time.time()))
    body.setdefault("exp", int(time.time()) + JWT_TTL_SECONDS)

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(body, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    if alg == "none":
        signature = b""
    else:
        signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()

    sig_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


class JWTError(Exception):
    pass


def jwt_decode(token: str, secret: str = JWT_SECRET) -> dict:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:
        raise JWTError("malformed token") from exc

    alg = header.get("alg", "HS256")
    if alg == "none":
        pass
    else:
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            raise JWTError("bad signature")

    if payload.get("exp") and payload["exp"] < time.time():
        raise JWTError("token expired")

    return payload
