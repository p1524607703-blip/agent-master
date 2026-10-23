#!/usr/bin/env python3
"""Build a private source worker from a pinned, clean vendor Git archive."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

VENDOR_COMMIT = '9a581df9394b6fb9340beb5453862e202079298b'
PATCH_REVISION = 2


def patch_vendor(root):
    path = root/'crates/codex-plus-core/src/protocol_proxy.rs'
    source = path.read_text()
    original = 'pub fn upstream_stream_header_timeout() -> Duration {\n    UPSTREAM_STREAM_HEADER_TIMEOUT\n}'
    replacement = '''pub fn upstream_stream_header_timeout() -> Duration {
    std::env::var("CPO_SOURCE_HEADER_TIMEOUT_SECONDS").ok()
        .and_then(|value| value.parse::<u64>().ok())
        .filter(|seconds| (60..=900).contains(seconds))
        .map(Duration::from_secs)
        .unwrap_or(UPSTREAM_STREAM_HEADER_TIMEOUT)
}'''
    if source.count(original) != 1:
        raise RuntimeError('Pinned vendor timeout function changed')
    source = source.replace(original,replacement)
    original = '''fn response_header_timeout(is_stream: bool) -> Duration {
    if is_stream {
        UPSTREAM_STREAM_HEADER_TIMEOUT
    } else {
        UPSTREAM_HEADER_TIMEOUT
    }
}'''
    if source.count(original) != 1:
        raise RuntimeError('Pinned vendor response timeout selection changed')
    source = source.replace(original,original.replace('        UPSTREAM_STREAM_HEADER_TIMEOUT','        upstream_stream_header_timeout()'))
    original = '''    tokio::time::timeout(timeout, request.send())
        .await
        .with_context(|| format!("上游请求超过 {} 秒未返回响应头", timeout.as_secs()))?
        .context("上游请求失败")'''
    replacement = '''    let retry = request.try_clone();
    let first = tokio::time::timeout(timeout, request.send())
        .await
        .with_context(|| format!("上游请求超过 {} 秒未返回响应头", timeout.as_secs()))?;
    match first {
        Ok(response) => Ok(response),
        Err(error) if error.is_connect() && retry.is_some() => {
            // No HTTP request reached upstream. Never replay HTTP/read failures.
            tokio::time::sleep(Duration::from_millis(150)).await;
            tokio::time::timeout(timeout, retry.unwrap().send()).await
                .with_context(|| format!("上游请求超过 {} 秒未返回响应头", timeout.as_secs()))?
                .context("上游连接重试失败")
        },
        Err(error) => Err(error).context("上游请求失败"),
    }'''
    if source.count(original) != 1:
        raise RuntimeError('Pinned vendor connect retry function changed')
    source = source.replace(original,replacement)
    path.write_text(source)
    return hashlib.sha256(source.encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vendor-source',required=True)
    parser.add_argument('--build-dir',required=True)
    parser.add_argument('--cargo',required=True)
    args=parser.parse_args()
    vendor_source=Path(args.vendor_source).resolve()
    head=subprocess.check_output(['git','-C',str(vendor_source),'rev-parse','HEAD'],text=True).strip()
    if head!=VENDOR_COMMIT:
        raise RuntimeError('Unexpected vendor Git version')
    build=Path(args.build_dir).resolve();build.mkdir(mode=0o700,parents=True,exist_ok=True)
    vendor=build/'vendor';worker=build/'worker'
    stamp=build/'vendor-patch.json'
    if vendor.exists() and (not stamp.exists() or json.loads(stamp.read_text()).get('patchRevision')!=PATCH_REVISION):
        shutil.rmtree(vendor)
    if not vendor.exists():
        archive=build/'vendor.tar'
        with archive.open('wb') as stream:
            subprocess.run(['git','-C',str(vendor_source),'archive',VENDOR_COMMIT],stdout=stream,check=True)
        vendor.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(vendor,filter='data')
        archive.unlink()
        patched_sha=patch_vendor(vendor)
        stamp.write_text(json.dumps({'commit':head,'patchRevision':PATCH_REVISION,'protocolProxySha256':patched_sha}))
    template=Path(__file__).resolve().parents[1]/'deploy/codex-source-worker'
    shutil.copytree(template,worker,dirs_exist_ok=True)
    if not (worker/'Cargo.lock').exists():
        shutil.copy2(vendor/'Cargo.lock',worker/'Cargo.lock')
    command=[str(Path(args.cargo).absolute()),'build','--manifest-path',str(worker/'Cargo.toml'),
             '--profile','cpo','--jobs','1']
    if (template/'Cargo.lock').exists():
        command.append('--locked')
    subprocess.run(command,check=True)
    binary=worker/'target/cpo/cpo-codex-source-worker'
    results=[]
    for value,expected in [(None,120),('600',600),('1',120),('invalid',120),('901',120)]:
        env=os.environ.copy();env.pop('CPO_SOURCE_HEADER_TIMEOUT_SECONDS',None)
        if value is not None:env['CPO_SOURCE_HEADER_TIMEOUT_SECONDS']=value
        result=json.loads(subprocess.check_output([str(binary),'--self-check'],env=env,text=True))
        if result['headerTimeoutSeconds']!=expected:
            raise RuntimeError('Source timeout self-check failed')
        results.append({'value':value,'seconds':expected})
    env=os.environ.copy();env['CPO_SOURCE_HEADER_TIMEOUT_SECONDS']='600'
    env['NO_PROXY']='127.0.0.1,localhost';env['no_proxy']='127.0.0.1,localhost'
    long_wait=json.loads(subprocess.check_output([str(binary),'--test-header-wait'],env=env,text=True,timeout=150))
    if long_wait['httpStatus']!=200 or long_wait['elapsedSeconds']<125:
        raise RuntimeError('Long upstream header wait was cut short')
    receipt={'vendorCommit':head,'binary':str(binary),'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
             'timeoutChecks':results,'longWaitCheck':long_wait,'modelsInvoked':False,'accountAuthenticationModified':False}
    (build/'build-receipt.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))


if __name__=='__main__':main()
