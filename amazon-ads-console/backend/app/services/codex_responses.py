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


def prepare_compact(value):
    """Bridge the legacy JSON endpoint to the source's native v2 control item."""
    body, stream = prepare(value)
    if stream:
        raise HTTPException(400, 'The compact endpoint returns JSON; omit stream or set it to false')
    adapted = json.loads(body)
    items = adapted.get('input')
    if not isinstance(items, list):
        raise HTTPException(400, 'Compaction input must be a string or list')
    if not any(isinstance(item, dict) and item.get('type') == 'compaction_trigger' for item in items):
        items.append({'type':'compaction_trigger'})
    return json.dumps(adapted, ensure_ascii=False).encode(), False


async def collect(status, content_type, stream, observer, headers, *, compact=False):
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
    if compact:
        # Retain the complete canonical output window, including any retained
        # messages. Never turn plain summary text into encrypted state.
        output = [observer.output_items[index] for index in sorted(observer.output_items)] if observer.output_items else final.get('output')
        native = [item for item in output if isinstance(item, dict) and item.get('type') == 'compaction'] if isinstance(output, list) else []
        content = native[0].get('encrypted_content') if len(native) == 1 else None
        if not observer.completed or not isinstance(content, str) or not content or content.startswith('codexplusplus:summary:v1:'):
            raise HTTPException(502, {'code':'native_compaction_missing','message':'Model source did not return a completed native compaction','source':'upstream'})
        final = {key:final[key] for key in ('id','created_at','usage') if key in final}
        final.update(object='response.compaction', output=output)
    return JSONResponse(final, headers=headers)
