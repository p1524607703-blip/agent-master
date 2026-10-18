"""Read-only distribution roster for the console preparation phase.

No account, device provisioning, heartbeat, model request or usage ingestion runs
in this phase. The final source will be the unified Japan proxy deployment.
"""
from app.services.auth import _connect


async def overview():
    conn = await _connect()
    try:
        async with conn.transaction(isolation='repeatable_read', readonly=True):
            now = await conn.fetchval('SELECT now()')
            roster = await conn.fetch('''SELECT user_id, display_name, username, group_code,
                group_name, person_code, role_code FROM codex_ops.personnel_roster
                WHERE status = 'active' ORDER BY group_code DESC, user_id''')
        return {
            'members': [{
                'userId': r['user_id'], 'displayName': r['display_name'], 'username': r['username'],
                'groupCode': r['group_code'], 'groupName': r['group_name'],
                'personCode': r['person_code'], 'roleCode': r['role_code'], 'devices': [],
            } for r in roster],
            'serverTime': now, 'onlineTimeoutSeconds': 120, 'timezone': 'Asia/Shanghai',
            'integrationStage': 'preparing', 'statisticsAvailable': False,
            'deploymentTarget': '日本代理服务器',
        }
    finally:
        await conn.close()
