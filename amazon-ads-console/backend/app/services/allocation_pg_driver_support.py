"""Only allow local ephemeral test Unix-socket connections, never production."""
import os


def isolated_connection():
    import asyncpg
    socket=os.environ.get("CPO_TEST_PG_SOCKET", "")
    port=os.environ.get("CPO_TEST_PG_PORT")
    user=os.environ.get("CPO_TEST_PG_USER")
    if not socket.startswith("/tmp/cpo-") or "/socket" not in socket:
        raise RuntimeError("EPHEMERAL_LOCAL_SOCKET_REQUIRED")
    if not port or not user:
        raise RuntimeError("ISOLATED_PG_CONFIG_REQUIRED")
    async def connect():
        return await asyncpg.connect(host=socket,port=int(port),user=user,database="postgres")
    return connect
