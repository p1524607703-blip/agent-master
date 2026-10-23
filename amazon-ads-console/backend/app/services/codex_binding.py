"""One approved public key per device credential; bounded, replay-protected proofs.

Hardware storage is enforced by the supplied client, not remotely attested here.
The server never accepts a client-supplied device ID as authentication.
"""
import base64
import hashlib
import json
import re
import time
import uuid
from asyncpg import UniqueViolationError

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils
from fastapi import HTTPException

from app.services.auth import _connect

MAX_BODY = 16 * 1024 * 1024
PROVIDERS = {'windows-tpm-p256', 'macos-secure-enclave-p256'}


def canonical(key, method, target, timestamp, nonce, body):
    return ('cpo-device-v1\n' + hashlib.sha256(key.encode()).hexdigest() + '\n' + method.upper()
            + '\n' + target + '\n' + timestamp + '\n' + nonce + '\n' + hashlib.sha256(body).hexdigest()).encode()


def public_key(value):
    try:
        raw = base64.b64decode(value, validate=True)
        if len(raw) != 65 or raw[0] != 4:
            raise ValueError()
        key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
        return key, hashlib.sha256(raw).hexdigest()
    except (ValueError, TypeError):
        raise HTTPException(400, 'Invalid device public key')


def verify(key, method, target, headers, body, encoded_public_key, now=None):
    timestamp = headers.get('x-cpo-time', '')
    nonce = headers.get('x-cpo-nonce', '')
    try:
        if not re.fullmatch(r'[0-9]{10,11}', timestamp) or abs((time.time() if now is None else now) - int(timestamp)) > 90:
            raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,64}', nonce):
            raise ValueError()
        signature = base64.b64decode(headers.get('x-cpo-proof', ''), validate=True)
        if len(signature) != 64:
            raise ValueError()
        public, _ = public_key(encoded_public_key)
        public.verify(utils.encode_dss_signature(int.from_bytes(signature[:32], 'big'),
                      int.from_bytes(signature[32:], 'big')),
                      canonical(key, method, target, timestamp, nonce, body), ec.ECDSA(hashes.SHA256()))
    except (ValueError, TypeError, InvalidSignature):
        raise HTTPException(403, 'Device proof missing, expired or invalid')
    return nonce


async def request_body(request):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY:
            raise HTTPException(413, 'Device request too large')
    # Starlette's body cache allows the actual model handler to read these same bytes.
    request._body = bytes(body)
    return request._body


def target(request):
    # Reject ambiguous encodings. These machine endpoints have ASCII paths and no query.
    if request.scope.get('query_string') or request.scope.get('raw_path', request.url.path.encode()) != request.url.path.encode():
        raise HTTPException(400, 'Device endpoints do not accept encoded paths or queries')
    return request.url.path


async def use_nonce(conn, device_id, nonce):
    # Server time governs expiry. Unique constraint spans all processes and restarts.
    await conn.execute('DELETE FROM codex_ops.device_proof_nonces WHERE expires_at < now()')
    value = await conn.fetchval('''INSERT INTO codex_ops.device_proof_nonces(device_id,nonce,expires_at)
        VALUES($1,$2,now()+interval '4 minutes') ON CONFLICT DO NOTHING RETURNING nonce''', device_id, nonce)
    if value is None:
        raise HTTPException(403, 'Device proof has already been used')


async def require_proof(device, key, request):
    body = await request_body(request)
    path = target(request)
    conn = await _connect()
    try:
        async with conn.transaction():
            row = await conn.fetchrow('SELECT * FROM codex_ops.device_bindings WHERE device_id=$1 FOR SHARE', device['device_id'])
            if row is None or not row['approved_at'] or not row['public_key']:
                raise HTTPException(403, 'Device enrollment and administrator approval required')
            nonce = verify(key, request.method, path, request.headers, body, row['public_key'])
            await use_nonce(conn, device['device_id'], nonce)
    finally:
        await conn.close()


async def claim(device, key, request):
    body = await request_body(request)
    path = target(request)
    if len(body) > 4096:
        raise HTTPException(413, 'Enrollment request too large')
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict) or set(payload) != {'publicKey', 'provider'} or payload['provider'] not in PROVIDERS:
            raise ValueError()
        _, fingerprint = public_key(payload['publicKey'])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, 'Expected a supported hardware-key enrollment')
    nonce = verify(key, request.method, path, request.headers, body, payload['publicKey'])
    conn = await _connect()
    try:
        async with conn.transaction():
            await conn.execute('INSERT INTO codex_ops.device_bindings(device_id) VALUES($1) ON CONFLICT DO NOTHING', device['device_id'])
            row = await conn.fetchrow('SELECT * FROM codex_ops.device_bindings WHERE device_id=$1 FOR UPDATE', device['device_id'])
            await use_nonce(conn, device['device_id'], nonce)
            if row['approved_at']:
                if row['fingerprint'] != fingerprint:
                    raise HTTPException(403, 'This Key is already bound to another device')
                return {'state': 'approved', 'fingerprint': fingerprint}
            count = await conn.fetchval('SELECT count(*) FROM codex_ops.device_binding_claims WHERE device_id=$1 AND generation=$2', device['device_id'], row['generation'])
            exists = await conn.fetchval('SELECT claim_id FROM codex_ops.device_binding_claims WHERE device_id=$1 AND generation=$2 AND fingerprint=$3', device['device_id'], row['generation'], fingerprint)
            if count >= 5 and not exists:
                raise HTTPException(429, 'Enrollment candidates full; contact administrator')
            claim_id = exists or uuid.uuid4()
            await conn.execute('''INSERT INTO codex_ops.device_binding_claims(claim_id,device_id,public_key,fingerprint,provider,generation)
                VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT DO NOTHING''', claim_id, device['device_id'], payload['publicKey'], fingerprint, payload['provider'], row['generation'])
            return {'state': 'pending', 'claimId': str(claim_id), 'fingerprint': fingerprint}
    finally:
        await conn.close()


async def listing():
    conn = await _connect()
    try:
        rows = await conn.fetch('''SELECT d.device_id,d.device_name,b.fingerprint,b.approved_at,b.generation,
            c.claim_id,c.fingerprint AS candidate_fingerprint,c.provider,c.created_at
            FROM codex_ops.devices d LEFT JOIN codex_ops.device_bindings b USING(device_id)
            LEFT JOIN codex_ops.device_binding_claims c ON c.device_id=d.device_id AND c.generation=b.generation
            AND b.approved_at IS NULL WHERE d.revoked_at IS NULL ORDER BY d.created_at,c.created_at''')
        return {'items': [dict(r, device_id=str(r['device_id']), claim_id=str(r['claim_id']) if r['claim_id'] else None) for r in rows]}
    finally:
        await conn.close()


async def approve(claim_id, expected_fingerprint, actor):
    conn = await _connect()
    try:
        async with conn.transaction():
            candidate = await conn.fetchrow('SELECT * FROM codex_ops.device_binding_claims WHERE claim_id=$1', claim_id)
            if not candidate or candidate['fingerprint'] != expected_fingerprint:
                raise HTTPException(409, 'Enrollment fingerprint changed; refresh and verify')
            # Device row first prevents approval racing with revocation.
            device = await conn.fetchrow('SELECT revoked_at FROM codex_ops.devices WHERE device_id=$1 FOR UPDATE', candidate['device_id'])
            row = await conn.fetchrow('SELECT * FROM codex_ops.device_bindings WHERE device_id=$1 FOR UPDATE', candidate['device_id'])
            if device['revoked_at'] or row['generation'] != candidate['generation'] or row['approved_at']:
                raise HTTPException(409, 'Enrollment is no longer pending')
            duplicate = await conn.fetchval('SELECT device_id FROM codex_ops.device_bindings WHERE public_key=$1', candidate['public_key'])
            if duplicate:
                raise HTTPException(409, 'Device public key already assigned')
            await conn.execute('''UPDATE codex_ops.device_bindings SET public_key=$2,fingerprint=$3,provider=$4,
                approved_at=now(),approved_by=$5 WHERE device_id=$1''', candidate['device_id'], candidate['public_key'], expected_fingerprint, candidate['provider'], actor)
            await conn.execute("INSERT INTO codex_ops.device_binding_audit(device_id,action,fingerprint,actor) VALUES($1,'approve',$2,$3)", candidate['device_id'], expected_fingerprint, actor)
            return {'approved': True, 'deviceId': str(candidate['device_id'])}
    except UniqueViolationError:
        raise HTTPException(409, 'Device public key already assigned')
    finally:
        await conn.close()
