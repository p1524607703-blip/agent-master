"""Administrator model availability, shared by every worker and preserved across releases."""
import json
import os
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from app.services import codex_control


def read(root):
    path = root / 'models.json'
    if not path.exists():
        return {'revision':0,'enabledModels':None,'updatedAt':None,'updatedBy':None}
    try:
        if path.stat().st_mode & 0o077 or path.stat().st_size > 65536:
            raise ValueError()
        value = json.loads(path.read_text())
        if not (type(value['revision']) is int and value['revision'] >= 0
                and isinstance(value['enabledModels'],list) and len(value['enabledModels']) <= 64
                and all(isinstance(x,str) and 0 < len(x) <= 256 for x in value['enabledModels'])):
            raise ValueError()
        return value
    except (OSError,ValueError,KeyError,TypeError):
        raise HTTPException(503,{'code':'model_policy_unavailable','message':'Model availability settings are unavailable','source':'relay'}) from None


def snapshot():
    with codex_control.locked() as root:
        return read(root)


def filter_catalog(catalog):
    enabled = snapshot()['enabledModels']
    if enabled is None:
        return catalog  # Preserve the verified upstream catalog until the first explicit setting.
    return {**catalog,'data':[item for item in catalog.get('data',[]) if isinstance(item,dict) and item.get('id') in enabled]}


def require_model(body):
    enabled = snapshot()['enabledModels']
    if enabled is None:
        return
    try:
        model = json.loads(body).get('model')
    except (ValueError,AttributeError):
        model = None
    if model not in enabled:
        raise HTTPException(403,{'code':'model_not_enabled','message':'This model is not enabled by the administrator','source':'access'})


def update(*, revision, enabled_models, available_models, actor):
    if (len(enabled_models)>64 or any(not isinstance(x,str) or not 0<len(x)<=256 for x in enabled_models)
            or len(set(enabled_models)) != len(enabled_models) or not set(enabled_models).issubset(available_models)):
        raise HTTPException(400,'Select only verified models currently available from the model source')
    with codex_control.locked() as root:
        old = read(root)
        if old['revision'] != revision:
            raise HTTPException(409,'Model settings changed; refresh before saving')
        value = {'revision':revision+1,'enabledModels':sorted(enabled_models),
                 'updatedAt':datetime.now(timezone.utc).isoformat(),'updatedBy':actor}
        temporary = root / ('models.'+uuid.uuid4().hex+'.tmp')
        with os.fdopen(os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as stream:
            json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,root/'models.json')
        return value
