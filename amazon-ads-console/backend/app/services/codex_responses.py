"""Responses request adaptation for the existing session-backed upstream."""
import json

import httpx
from fastapi import HTTPException
from fastapi.responses import JSONResponse, Response


def prepare(value):
    """Preserve request options and output limits; adapt only wire representation."""
    stream = value.get('stream', False)
    if type(stream) is not bool:
        raise HTTPException(400, 'stream must be a boolean')
    if value.get('store', False) is not False:
        raise HTTPException(400, 'This endpoint supports store=false only')
    adapted = dict(value)
    if isinstance(adapted.get('input'), str):
        adapted['input'] = [{'role': 'user', 'content': [
            {'type': 'input_text', 'text': adapted['input']}]}]
    adapted['store'] = False
    adapted['stream'] = True
    return json.dumps(adapted, ensure_ascii=False).encode(), stream


async def collect(status, content_type, stream, observer, headers):
    """Return actual terminal JSON, never an HTTP-200 placeholder for diagnostics."""
    error_body = bytearray()
    received = 0
    try:
        async for chunk in stream:
            received += len(chunk)
            if received > 64*1024*1024:
                raise HTTPException(502, 'Model response exceeds the buffered response limit; use stream=true')
            if status != 200:
                if len(error_body) + len(chunk) > 1024*1024:
                    raise HTTPException(502, 'Model error response is too large')
                error_body.extend(chunk)
    except httpx.HTTPError:
        raise HTTPException(502, 'Model response was interrupted') from None
    finally:
        await stream.aclose()
    if status != 200:
        return Response(bytes(error_body), status_code=status, media_type=content_type.split(';')[0], headers=headers)
    final = observer.response
    if not final or not (observer.completed or final.get('status') == 'incomplete'):
        raise HTTPException(502, 'Upstream did not return a completed model response')
    return JSONResponse(final, headers=headers)
