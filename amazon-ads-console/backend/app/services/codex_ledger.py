"""A dated ledger for this entrance, never a claim of account-wide coverage."""
from datetime import timezone

from app.core.config import settings


def start_time():
    value = settings.codex_ledger_started_at
    if value is None or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc)


def present(rows, start, end, pending):
    fields = ('requests', 'measuredRequests', 'unknownRequests', 'cachedUnknownRequests', 'reasoningUnknownRequests', 'totalTokens',
              'inputTokens', 'outputTokens', 'cachedTokens', 'reasoningTokens')
    sources = [{**dict(row), 'deviceId': str(row['deviceId'])} for row in rows]
    totals = {key: sum(int(row[key] or 0) for row in sources) for key in fields}
    # Null detail counts remain unknown; they are not silently confirmed as zero.
    for key in ('totalTokens', 'inputTokens', 'outputTokens', 'cachedTokens', 'reasoningTokens'):
        totals[key] = sum(int(row[key]) for row in sources if row[key] is not None) if any(
            row[key] is not None for row in sources) else None
    return {'scope': 'unified-entry', 'accountCoverage': 'partial',
            'status': 'active' if start and start <= end else 'not-started',
            'startedAt': start, 'throughAt': end, 'timezone': 'UTC',
            'pendingAccountingEvents': pending,
            'uncoveredSources': ['主管直连', '旧 /v1 入口', '其他官方客户端及历史未采集调用'],
            'totals': totals, 'sources': sources}


async def read_ledger(conn, end, pending, *, recorded_history=False):
    start = await conn.fetchval('SELECT min(finished_at) FROM codex_ops.model_requests WHERE finished_at <= $1', end) if recorded_history else start_time()
    rows = []
    if start is not None and start <= end:
        rows = await conn.fetch('''SELECT d.device_id AS "deviceId",d.user_id AS "userId",
            d.device_name AS "deviceName",coalesce(p.display_name,'未列名人员') AS "displayName",
            coalesce(p.role_code,'unknown') AS "roleCode",d.revoked_at IS NOT NULL AS revoked,
            count(*)::bigint AS requests,
            count(r.total_tokens)::bigint AS "measuredRequests",
            count(*) FILTER (WHERE r.total_tokens IS NULL)::bigint AS "unknownRequests",
            count(*) FILTER (WHERE r.total_tokens IS NOT NULL AND r.cached_tokens IS NULL)::bigint AS "cachedUnknownRequests",
            count(*) FILTER (WHERE r.total_tokens IS NOT NULL AND r.reasoning_tokens IS NULL)::bigint AS "reasoningUnknownRequests",
            sum(r.total_tokens) AS "totalTokens",sum(r.input_tokens) AS "inputTokens",
            sum(r.output_tokens) AS "outputTokens",sum(r.cached_tokens) AS "cachedTokens",
            sum(r.reasoning_tokens) AS "reasoningTokens"
            FROM codex_ops.model_requests r JOIN codex_ops.devices d USING(device_id)
            LEFT JOIN codex_ops.personnel_roster p ON p.user_id=d.user_id
            WHERE r.finished_at >= $1 AND r.finished_at <= $2
            GROUP BY d.device_id,p.display_name,p.role_code ORDER BY d.created_at''', start, end)
    result = present(rows, start, end, pending)
    if recorded_history:
        result.update(scope='recorded-unified-entry', startSource='first-stored-record')
    return result
