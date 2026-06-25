import hashlib
import json
import logging
import uuid

import httpx
import redis.asyncio as aioredis

from app.config import settings
from app.services.secrets_service import _fernet

logger = logging.getLogger(__name__)

_STATE_TTL = 600   # 10 minutes for OIDC state/nonce
_EXCHANGE_TTL = 120  # 2 minutes for post-callback token exchange
_DISCOVERY_TTL = 3600  # 1 hour discovery doc cache


def _redis_url() -> str:
    return settings.REDIS_URL


def _discovery_cache_key(discovery_url: str) -> str:
    h = hashlib.sha256(discovery_url.encode()).hexdigest()[:16]
    return f"oidc:discovery:{h}"


async def fetch_discovery_document(discovery_url: str) -> dict:
    cache_key = _discovery_cache_key(discovery_url)
    r = aioredis.from_url(_redis_url(), decode_responses=True)
    try:
        cached = await r.get(cache_key)
        if cached:
            return json.loads(cached)
    finally:
        await r.aclose()

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(discovery_url)
        resp.raise_for_status()
        doc = resp.json()

    r = aioredis.from_url(_redis_url(), decode_responses=True)
    try:
        await r.setex(cache_key, _DISCOVERY_TTL, json.dumps(doc))
    finally:
        await r.aclose()

    return doc


async def invalidate_discovery_cache(discovery_url: str) -> None:
    cache_key = _discovery_cache_key(discovery_url)
    r = aioredis.from_url(_redis_url(), decode_responses=True)
    try:
        await r.delete(cache_key)
    finally:
        await r.aclose()


def encrypt_client_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_client_secret(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()


async def build_authorization_url(
    discovery_url: str,
    client_id: str,
    redirect_uri: str,
    next_url: str,
) -> str:
    import secrets as _secrets
    import base64

    doc = await fetch_discovery_document(discovery_url)
    authorization_endpoint = doc["authorization_endpoint"]

    state = str(uuid.uuid4())
    nonce = str(uuid.uuid4())

    # PKCE
    verifier_bytes = _secrets.token_bytes(32)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode()
    challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode()

    state_data = json.dumps({"nonce": nonce, "next": next_url, "pkce_verifier": code_verifier})
    r = aioredis.from_url(_redis_url(), decode_responses=True)
    try:
        await r.setex(f"sso:state:{state}", _STATE_TTL, state_data)
    finally:
        await r.aclose()

    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{authorization_endpoint}?{urlencode(params)}"


async def exchange_code(
    discovery_url: str,
    client_id: str,
    encrypted_client_secret: str,
    group_claim_key: str,
    code: str,
    state: str,
    redirect_uri: str,
) -> dict:
    """Validate state, exchange code, validate ID token. Returns {sub, email, name, groups}."""
    r = aioredis.from_url(_redis_url(), decode_responses=True)
    try:
        state_raw = await r.getdel(f"sso:state:{state}")
    finally:
        await r.aclose()

    if not state_raw:
        raise ValueError("SSO state expired or not found — possible CSRF attempt")

    state_data = json.loads(state_raw)
    nonce = state_data["nonce"]
    code_verifier = state_data.get("pkce_verifier", "")

    doc = await fetch_discovery_document(discovery_url)
    token_endpoint = doc["token_endpoint"]
    client_secret = decrypt_client_secret(encrypted_client_secret)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        token_response = resp.json()

    id_token = token_response.get("id_token")
    if not id_token:
        raise ValueError("No id_token in token response")

    # Validate the ID token using authlib
    from authlib.jose import jwt as authlib_jwt
    from authlib.jose.errors import JoseError

    jwks_uri = doc.get("jwks_uri")
    if not jwks_uri:
        raise ValueError("OIDC discovery document missing jwks_uri")

    async with httpx.AsyncClient(timeout=10.0) as client:
        jwks_resp = await client.get(jwks_uri)
        jwks_resp.raise_for_status()
        jwks = jwks_resp.json()

    try:
        claims = authlib_jwt.decode(id_token, jwks)
        claims.validate(leeway=30)
    except JoseError as exc:
        raise ValueError(f"ID token validation failed: {exc}") from exc

    # Validate nonce
    if claims.get("nonce") != nonce:
        raise ValueError("ID token nonce mismatch")

    # Validate audience
    aud = claims.get("aud")
    if isinstance(aud, str):
        aud = [aud]
    if client_id not in (aud or []):
        raise ValueError("ID token audience does not include client_id")

    email = (claims.get("email") or "").lower().strip()
    if not email:
        raise ValueError("ID token missing email claim")

    groups = claims.get(group_claim_key) or []
    if not isinstance(groups, list):
        groups = [groups] if groups else []

    name = claims.get("name") or claims.get("preferred_username") or email.split("@")[0]

    return {
        "sub": claims["sub"],
        "email": email,
        "name": name,
        "groups": groups,
        "next": state_data.get("next", "/dashboard"),
    }


async def store_sso_exchange(access_token: str, refresh_token: str) -> str:
    code = str(uuid.uuid4())
    payload = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
    r = aioredis.from_url(_redis_url(), decode_responses=True)
    try:
        await r.setex(f"sso:exchange:{code}", _EXCHANGE_TTL, payload)
    finally:
        await r.aclose()
    return code


async def consume_sso_exchange(code: str) -> dict | None:
    r = aioredis.from_url(_redis_url(), decode_responses=True)
    try:
        raw = await r.getdel(f"sso:exchange:{code}")
    finally:
        await r.aclose()
    if not raw:
        return None
    return json.loads(raw)
