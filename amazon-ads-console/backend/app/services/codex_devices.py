"""Read-only member overview. Device telemetry is opt-in after explicit activation."""
from app.services.auth import _connect
from app.core.config import settings
from app.services.codex_quota import snapshot as quota_snapshot
from app.services.codex_telemetry import flush_events,spool_dir
from app.services.codex_ledger import read_ledger, present


async def overview():
    pending = 0
    if settings.codex_telemetry_enabled:
        try:
            await flush_events()
        except Exception:
            pass  # Keep the last committed ledger readable, with its pending count.
        pending = len(list(spool_dir().glob('*.json')))
    conn = await _connect()
    try:
        async with conn.transaction(isolation='repeatable_read', readonly=True):
            now = await conn.fetchval('SELECT now()')
            roster = await conn.fetch('''SELECT user_id, display_name, username, group_code,
                group_name, person_code, role_code FROM codex_ops.personnel_roster
                WHERE status = 'active' ORDER BY group_code DESC, user_id''')
            devices = []
            ledger = present([], None, now, pending)
            if settings.codex_telemetry_enabled:
                ledger = await read_ledger(conn, now, pending)
                devices = await conn.fetch('''SELECT d.*,
                    max(r.finished_at) AS last_request_at,count(r.request_id) AS requests,
                    count(r.request_id) FILTER (WHERE r.total_tokens IS NULL) AS unknown_requests,
                    sum(r.total_tokens) AS total_tokens,
                    sum(r.total_tokens) FILTER (WHERE (r.finished_at AT TIME ZONE 'Asia/Shanghai')::date
                        = (now() AT TIME ZONE 'Asia/Shanghai')::date) AS today_tokens,
                    sum(r.input_tokens) AS input_tokens,sum(r.output_tokens) AS output_tokens,
                    sum(r.cached_tokens) AS cached_tokens,sum(r.reasoning_tokens) AS reasoning_tokens
                    FROM codex_ops.devices d LEFT JOIN codex_ops.model_requests r USING(device_id)
                    GROUP BY d.device_id ORDER BY d.created_at''')
        grouped = {}
        for d in devices:
            alive = bool(d['last_heartbeat_at'] and (now-d['last_heartbeat_at']).total_seconds() <= 120 and not d['revoked_at'])
            grouped.setdefault(d['user_id'],[]).append({
                'deviceId':str(d['device_id']),'deviceName':d['device_name'],'platform':d['platform'],
                'online':alive and d['codex_running'],'agentOnline':alive,'codexRunning':d['codex_running'],
                'revoked':bool(d['revoked_at']),'lastHeartbeatAt':d['last_heartbeat_at'],
                'lastRequestAt':d['last_request_at'],'totalTokens':d['total_tokens'],'todayTokens':d['today_tokens'],
                'inputTokens':d['input_tokens'],'outputTokens':d['output_tokens'],
                'cachedTokens':d['cached_tokens'],'reasoningTokens':d['reasoning_tokens'],
                'requests':d['requests'],'unknownRequests':d['unknown_requests']})
        return {
            'members': [{
                'userId': r['user_id'], 'displayName': r['display_name'], 'username': r['username'],
                'groupCode': r['group_code'], 'groupName': r['group_name'],
                'personCode': r['person_code'], 'roleCode': r['role_code'], 'devices': grouped.get(r['user_id'],[]),
            } for r in roster],
            'serverTime': now, 'onlineTimeoutSeconds': 120, 'timezone': 'Asia/Shanghai',
            'accountQuota': quota_snapshot(),
            'ledger': ledger,
            'integrationStage': 'pilot' if settings.codex_telemetry_enabled else 'preparing',
            'statisticsAvailable': settings.codex_telemetry_enabled,'pendingAccountingEvents':pending,
            'deploymentTarget': settings.codex_deployment_target if settings.codex_telemetry_enabled else '日本代理服务器',
        }
    finally:
        await conn.close()
