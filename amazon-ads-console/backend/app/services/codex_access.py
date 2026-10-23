"""Administrator approval is independent of optional hardware proof."""
from fastapi import HTTPException
from app.services.auth import _connect
from app.services import codex_binding


async def require_access(device, key, request):
    conn = await _connect()
    try:
        row = await conn.fetchrow('SELECT auth_mode,approved_at,revision FROM codex_ops.device_access WHERE device_id=$1', device['device_id'])
    finally:
        await conn.close()
    if not row or not row['approved_at']:
        raise HTTPException(403, {'code':'access_approval_required','message':'This API key is awaiting administrator approval','source':'access'})
    if row['auth_mode'] == 'hardware':
        await codex_binding.require_proof(device, key, request)
    elif row['auth_mode'] != 'api_key':
        raise HTTPException(503, {'code':'access_policy_unavailable','message':'Device access policy is unavailable','source':'access'})
    device['_access_revision'] = row['revision']


async def recheck_queued(device):
    if '_access_revision' not in device:
        return  # Internal service callers have their own explicit authorization.
    conn = await _connect()
    try:
        row = await conn.fetchrow('''SELECT a.approved_at,a.revision,d.revoked_at,r.status
            FROM codex_ops.devices d JOIN codex_ops.personnel_roster r USING(user_id)
            JOIN codex_ops.device_access a USING(device_id) WHERE d.device_id=$1''', device['device_id'])
    finally:
        await conn.close()
    if not row or row['revoked_at'] or row['status'] != 'active':
        raise HTTPException(401, {'code':'invalid_api_key','message':'This API key is no longer active','source':'access'})
    if not row['approved_at'] or row['revision'] != device['_access_revision']:
        raise HTTPException(403, {'code':'access_policy_changed','message':'Access approval changed while queued; check the control panel before retrying','source':'access'})


async def update(device_id, *, revision, auth_mode, approved, actor):
    conn = await _connect()
    try:
        async with conn.transaction():
            device = await conn.fetchrow('SELECT revoked_at FROM codex_ops.devices WHERE device_id=$1 FOR UPDATE', device_id)
            if not device or device['revoked_at']:
                raise HTTPException(404, 'Active API key not found')
            row = await conn.fetchrow('SELECT * FROM codex_ops.device_access WHERE device_id=$1 FOR UPDATE', device_id)
            if not row or row['revision'] != revision:
                raise HTTPException(409, 'Access settings changed; refresh before saving')
            row = await conn.fetchrow('''UPDATE codex_ops.device_access SET auth_mode=$2,
                approved_at=CASE WHEN $3 THEN coalesce(approved_at,now()) ELSE NULL END,
                approved_by=CASE WHEN $3 THEN coalesce(approved_by,$4) ELSE NULL END,
                revision=revision+1,updated_at=now() WHERE device_id=$1
                RETURNING auth_mode,approved_at,revision''', device_id, auth_mode, approved, actor)
            await conn.execute('''INSERT INTO codex_ops.device_access_audit(device_id,action,auth_mode,actor)
                VALUES($1,$2,$3,$4)''', device_id, 'approve' if approved else 'hold', auth_mode, actor)
            return dict(row, device_id=str(device_id))
    finally:
        await conn.close()
