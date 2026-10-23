"""Bounded, authenticated frontend diagnostics; no arbitrary messages or request bodies."""
from __future__ import annotations
import json
import re
import time
import uuid
from collections import OrderedDict, deque
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from fastapi import HTTPException
from app.core.observability import emit_diagnostic, request_context, release_metadata

Kind = Literal['vue_error','javascript_error','unhandled_rejection','resource_error','router_error','navigation_timeout']
MESSAGES = {
 'CACHE_LIFECYCLE_ERROR':'页面缓存切换异常', 'NULL_DOM_NODE':'页面节点渲染异常',
 'CHUNK_LOAD_FAILED':'页面资源加载失败', 'RESOURCE_LOAD_FAILED':'静态资源加载失败',
 'JAVASCRIPT_ERROR':'浏览器脚本异常', 'UNHANDLED_REJECTION':'未处理的异步异常',
 'ROUTER_ERROR':'页面导航异常', 'NAVIGATION_TIMEOUT':'页面导航超过 30 秒未完成',
}
PATHS = {'/','/login','/my-cpo','/operator-cpo','/ad-allocation','/data-changes','/product-mappings','/data-maintenance','/reports','/cpo-jobs','/diagnostics','/codex-devices'}
def safe_page(value: str) -> str:
 path=urlsplit(value).path
 return path if path in PATHS else '/operators/:operator' if path.startswith('/operators/') else '/unknown'

class Frame(BaseModel):
 model_config=ConfigDict(extra='forbid')
 file: str=Field(max_length=240)
 line: int=Field(ge=0,le=10_000_000)
 column: int=Field(default=0,ge=0,le=10_000_000)
 @field_validator('file')
 @classmethod
 def safe_file(cls,value):
  path=urlsplit(value).path
  if not re.fullmatch(r'/(?:assets|src)/[A-Za-z0-9_./-]+\.(?:js|ts|vue|css)',path) or '..' in path:raise ValueError('Invalid asset path')
  return path

class FrontendError(BaseModel):
 model_config=ConfigDict(extra='forbid')
 event_id: uuid.UUID
 kind: Kind
 error_code: Literal['CACHE_LIFECYCLE_ERROR','NULL_DOM_NODE','CHUNK_LOAD_FAILED','RESOURCE_LOAD_FAILED','JAVASCRIPT_ERROR','UNHANDLED_REJECTION','ROUTER_ERROR','NAVIGATION_TIMEOUT']
 exception_type: Literal['Error','TypeError','ReferenceError','SyntaxError','RangeError','URIError','EvalError','ResourceError','NavigationTimeout']= 'Error'
 page_path: str=Field(max_length=300)
 target_path: str=Field(default='',max_length=300)
 client_commit: str=Field(pattern=r'^(?:[a-f0-9]{40}|development)$')
 duration_ms: int=Field(default=0,ge=0,le=86_400_000)
 occurrences: int=Field(default=1,ge=1,le=100)
 stack: list[Frame]=Field(default_factory=list,max_length=12)
 @field_validator('page_path','target_path')
 @classmethod
 def page(cls,value):return safe_page(value) if value else ''

# Per-worker bounds prevent a failing tab from filling logs or retaining unbounded identities.
_buckets: OrderedDict[str,deque] = OrderedDict()
_seen: OrderedDict[tuple[str,str],float] = OrderedDict()
def record_frontend_error(data: dict, user: dict) -> dict:
 try:event=FrontendError.model_validate(data)
 except ValidationError:raise HTTPException(400,'Invalid frontend diagnostic') from None
 uid=str(user['userId']);now=time.monotonic();key=(uid,str(event.event_id))
 if key in _seen and now-_seen[key]<300:return {'accepted':True,'duplicate':True,'event_id':str(event.event_id)}
 bucket=_buckets.setdefault(uid,deque());_buckets.move_to_end(uid)
 while bucket and now-bucket[0]>=60:bucket.popleft()
 if len(bucket)>=60:raise HTTPException(429,'Frontend diagnostics rate limit',headers={'Retry-After':'60'})
 bucket.append(now)
 while len(_buckets)>2048:_buckets.popitem(last=False)
 context=request_context.get() or {}
 payload=event.model_dump(mode='json')
 record={**payload,'event':'frontend_error','schema_version':1,'timestamp':datetime.now(timezone.utc).isoformat(),
         'user_id':uid,'username':user.get('username'),'role':user.get('roleCode'),
         'operator_group':str(user.get('operatorCode') or '').upper()[:2] or None,
         'request_id':context.get('request_id') or uuid.uuid4().hex,
         'message':MESSAGES[event.error_code],**release_metadata()}
 if not emit_diagnostic(record):raise HTTPException(503,'Frontend diagnostic storage unavailable')
 _seen[key]=now
 while len(_seen)>4096:_seen.popitem(last=False)
 return {'accepted':True,'event_id':str(event.event_id),'request_id':record['request_id']}
