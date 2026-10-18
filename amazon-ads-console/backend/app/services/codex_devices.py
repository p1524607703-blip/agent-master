"""Member/device telemetry; heartbeats and trusted proxy usage are separate signals."""
import hashlib
import secrets
import uuid

from app.services.auth import _connect

ONLINE_SECONDS = 120


def heartbeat_online(last_heartbeat, revoked_at, now):
    return (revoked_at is None and last_heartbeat is not None
            and 0 <= (now - last_heartbeat).total_seconds() <= ONLINE_SECONDS)


async def overview():
    conn = await _connect()
    try:
        async with conn.transaction(isolation='repeatable_read', readonly=True):
            now = await conn.fetchval('SELECT now()')
            roster = await conn.fetch('''SELECT user_id, display_name, username, group_code,
                group_name, person_code, role_code FROM codex_ops.personnel_roster
                WHERE status = 'active' ORDER BY group_code DESC, user_id''')
            devices = await conn.fetch('''SELECT d.device_id, d.user_id, d.device_name, d.platform,
                d.last_heartbeat_at, d.revoked_at, d.agent_version,
                COUNT(e.response_id)::bigint AS requests,
                COUNT(e.response_id) FILTER (WHERE e.input_tokens IS NULL OR e.output_tokens IS NULL)::bigint AS unknown_requests,
                SUM(e.input_tokens + e.output_tokens)::bigint AS total_tokens,
                SUM(e.input_tokens)::bigint AS input_tokens,
                SUM(e.output_tokens)::bigint AS output_tokens,
                SUM(e.input_tokens + e.output_tokens) FILTER (
                    WHERE (e.occurred_at AT TIME ZONE 'Asia/Shanghai')::date =
                          (now() AT TIME ZONE 'Asia/Shanghai')::date)::bigint AS today_tokens,
                MAX(e.occurred_at) AS last_request_at
                FROM codex_ops.devices d
                JOIN codex_ops.personnel_roster r ON r.user_id=d.user_id AND r.status='active'
                LEFT JOIN codex_ops.usage_events e ON e.device_id=d.device_id
                GROUP BY d.device_id ORDER BY d.created_at''')
        members = {r['user_id']: {
            'userId': r['user_id'], 'displayName': r['display_name'], 'username': r['username'],
            'groupCode': r['group_code'], 'groupName': r['group_name'],
            'personCode': r['person_code'], 'roleCode': r['role_code'], 'devices': [],
        } for r in roster}
        for d in devices:
            members[d['user_id']]['devices'].append({
                'deviceId': str(d['device_id']), 'deviceName': d['device_name'], 'platform': d['platform'],
                'online': heartbeat_online(d['last_heartbeat_at'], d['revoked_at'], now),
                'revoked': d['revoked_at'] is not None, 'lastHeartbeatAt': d['last_heartbeat_at'],
                'lastRequestAt': d['last_request_at'], 'agentVersion': d['agent_version'],
                'requests': d['requests'], 'unknownRequests': d['unknown_requests'],
                'totalTokens': d['total_tokens'], 'todayTokens': d['today_tokens'],
                'inputTokens': d['input_tokens'], 'outputTokens': d['output_tokens'],
            })
        return {'members': list(members.values()), 'serverTime': now,
                'onlineTimeoutSeconds': ONLINE_SECONDS, 'timezone': 'Asia/Shanghai'}
    finally:
        await conn.close()


async def create_device(user_id, device_name, platform):
    conn = await _connect()
    try:
        key = secrets.token_urlsafe(48)
        device_id = uuid.uuid4()
        row = await conn.fetchrow('''INSERT INTO codex_ops.devices
            (device_id, user_id, device_name, platform, heartbeat_key_hash)
            SELECT $1, user_id, $3, $4, $5 FROM codex_ops.personnel_roster
            WHERE user_id=$2 AND status='active' RETURNING device_id''',
            device_id, user_id, device_name, platform, hashlib.sha256(key.encode()).hexdigest())
        return {'deviceId': str(device_id), 'heartbeatKey': key} if row else None
    finally:
        await conn.close()


async def heartbeat(key, agent_version):
    conn = await _connect()
    try:
        result = await conn.fetchrow('''UPDATE codex_ops.devices d
            SET last_heartbeat_at=now(), agent_version=$2
            FROM codex_ops.personnel_roster r
            WHERE d.heartbeat_key_hash=$1 AND d.revoked_at IS NULL
                AND r.user_id=d.user_id AND r.status='active'
            RETURNING d.device_id''', hashlib.sha256(key.encode()).hexdigest(), agent_version)
        return result is not None
    finally:
        await conn.close()


async def revoke_device(device_id):
    conn = await _connect()
    try:
        return await conn.fetchval('''UPDATE codex_ops.devices SET revoked_at=COALESCE(revoked_at,now())
            WHERE device_id=$1 RETURNING device_id''', device_id) is not None
    finally:
        await conn.close()


async def record_usage(payload):
    conn = await _connect()
    try:
        # First receipt wins: retries never add usage twice. Trust only the proxy's final usage.
        result = await conn.fetchval('''INSERT INTO codex_ops.usage_events
            (device_id,response_id,model,outcome,occurred_at,input_tokens,cached_input_tokens,output_tokens,reasoning_tokens)
            SELECT d.device_id,$2,$3,$4,$5,$6,$7,$8,$9 FROM codex_ops.devices d
            JOIN codex_ops.personnel_roster r ON r.user_id=d.user_id
            WHERE d.device_id=$1 AND d.revoked_at IS NULL AND r.status='active'
            ON CONFLICT(device_id,response_id) DO NOTHING RETURNING response_id''',
            payload.device_id, payload.response_id, payload.model, payload.outcome, payload.occurred_at,
            payload.input_tokens, payload.cached_input_tokens, payload.output_tokens, payload.reasoning_tokens)
        return result is not None
    finally:
        await conn.close()
