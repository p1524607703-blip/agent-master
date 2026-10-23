// Reuse the vendor launcher and credential handling; never copy OAuth material.
use anyhow::{Context, Result, ensure};
use serde::Deserialize;
use std::{path::PathBuf, time::Duration};

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Options {
    app_path: String,
    debug_port: u16,
    helper_port: u16,
    state_dir: String,
}

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("--test-header-wait") {
        use std::io::{Read, Write};
        let listener = std::net::TcpListener::bind(("127.0.0.1",0))?;
        let address = listener.local_addr()?;
        let server = std::thread::spawn(move || -> std::io::Result<()> {
            let (mut stream,_) = listener.accept()?;
            stream.set_read_timeout(Some(Duration::from_secs(10)))?;
            let mut request = [0u8;4096];
            let count = stream.read(&mut request)?;
            assert!(!String::from_utf8_lossy(&request[..count]).to_ascii_lowercase().contains("authorization:"));
            std::thread::sleep(Duration::from_secs(125));
            stream.write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}")
        });
        let start = std::time::Instant::now();
        let runtime = tokio::runtime::Builder::new_current_thread().enable_all().build()?;
        let status = runtime.block_on(async {
            let client = codex_plus_core::protocol_proxy::upstream_http_client()?;
            let response = codex_plus_core::protocol_proxy::send_upstream_request_for_responses(
                client.post(format!("http://{address}/controlled-test")).body("{}"),true).await?;
            Ok::<u16,anyhow::Error>(response.status().as_u16())
        })?;
        server.join().map_err(|_| anyhow::anyhow!("Controlled test server failed"))??;
        ensure!(status==200 && start.elapsed().as_secs()>=125,"Long header wait check failed");
        println!("{}",serde_json::json!({"mode":"controlled-loopback-header-test","httpStatus":status,
            "elapsedSeconds":start.elapsed().as_secs_f64(),"modelsInvoked":false,"credentialsSent":false}));
        return Ok(());
    }
    if args.get(1).map(String::as_str) == Some("--self-check") {
        println!("{}", serde_json::json!({
            "mode":"diagnostic-no-launch",
            "vendorCommit":"9a581df9394b6fb9340beb5453862e202079298b",
            "headerTimeoutSeconds":codex_plus_core::protocol_proxy::upstream_stream_header_timeout().as_secs()
        }));
        return Ok(());
    }
    ensure!(args.get(1).map(String::as_str) == Some("--codex-plus-multi-worker") && args.len() == 3,
            "Expected isolated source worker options");
    let options_path = PathBuf::from(&args[2]).canonicalize()?;
    let instance = options_path.parent().context("Missing isolated instance directory")?;
    let options: Options = serde_json::from_slice(&std::fs::read(&options_path)?)?;
    ensure!(std::env::var("CODEX_PLUS_MULTI_INSTANCE").ok().as_deref() == Some("1"),
            "Isolated worker environment is required");
    for (variable, suffix) in [("CODEX_HOME","codex-home"),("CODEX_SQLITE_HOME","sqlite-home")] {
        let actual = PathBuf::from(std::env::var_os(variable).context("Missing isolated source directory")?).canonicalize()?;
        ensure!(actual == instance.join(suffix).canonicalize()?, "Source isolation mismatch");
    }
    let state = PathBuf::from(&options.state_dir).canonicalize()?;
    ensure!(state == instance.join("worker-home/.codex-session-delete").canonicalize()?,
            "Source state directory mismatch");
    if let Ok(raw) = std::env::var("CPO_SOURCE_HEADER_TIMEOUT_SECONDS") {
        ensure!(raw.parse::<u64>().ok().filter(|v| (60..=900).contains(v)).is_some(),
                "Invalid source header timeout");
    }
    codex_plus_launcher::start(codex_plus_launcher::LaunchOptions {
        app_dir: Some(PathBuf::from(options.app_path)),
        debug_port: options.debug_port,
        helper_port: options.helper_port,
        status_store: codex_plus_core::status::StatusStore::new(state.join("latest-status.json")),
        state_dir: Some(state),
        codex_home: std::env::var_os("CODEX_HOME").map(PathBuf::from),
        sqlite_home: std::env::var_os("CODEX_SQLITE_HOME").map(PathBuf::from),
    })?;
    // The supervised helper owns its lifetime. A transient failed CDP probe must
    // not shut down a healthy API source and repeatedly reopen the desktop.
    loop { std::thread::sleep(Duration::from_secs(5)); }
}
