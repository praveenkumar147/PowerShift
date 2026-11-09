//! Starts, monitors and stops the local Python backend process.
//!
//! Lifecycle:
//! 1. `resolve_launch` decides which program to run (venv Python in development,
//!    the frozen backend executable in a packaged build) and where data lives.
//! 2. `BackendManager::start` spawns it with `--port 0` and a random token, on a
//!    background thread so the window opens immediately.
//! 3. The backend binds a free port and prints `POWERSHIFT_READY port=<n>`.
//!    We parse that line and switch the status to `Ready`.
//! 4. The frontend polls the `backend_status` command until it sees `Ready`.
//! 5. On exit we kill the process. On Windows the process is also placed in a
//!    Job Object, so the OS kills it even if PowerShift itself crashes.

use std::collections::VecDeque;
use std::ffi::OsString;
use std::io::{BufRead, BufReader, Read};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::mpsc::{self, RecvTimeoutError};
use std::sync::{Arc, Mutex, PoisonError};
use std::thread;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Manager, State};

const READY_PREFIX: &str = "POWERSHIFT_READY port=";
const STARTUP_TIMEOUT: Duration = Duration::from_secs(45);
const TOKEN_BYTES: usize = 32;
const STDERR_TAIL_LINES: usize = 15;

/// Sent to the frontend as JSON, e.g. `{"state":"ready","port":51234,"token":"…"}`.
/// Mirrors `BackendStatus` in src/api/connection.ts.
#[derive(Clone, Debug, Serialize)]
#[serde(tag = "state", rename_all = "lowercase")]
pub enum BackendStatus {
    Starting,
    Ready { port: u16, token: String },
    Failed { message: String },
}

/// Everything needed to start the backend process.
pub struct BackendLaunch {
    program: PathBuf,
    args: Vec<OsString>,
    working_dir: PathBuf,
    data_dir: PathBuf,
}

pub struct BackendManager {
    status: Mutex<BackendStatus>,
    child: Mutex<Option<Child>>,
    #[cfg(windows)]
    job: Mutex<Option<win32job::Job>>,
}

impl Default for BackendManager {
    fn default() -> Self {
        Self {
            status: Mutex::new(BackendStatus::Starting),
            child: Mutex::new(None),
            #[cfg(windows)]
            job: Mutex::new(None),
        }
    }
}

/// Mutex poisoning only happens if a thread panicked while holding the lock;
/// the data is still usable, so recover it instead of crashing the app.
fn lock<T>(mutex: &Mutex<T>) -> std::sync::MutexGuard<'_, T> {
    mutex.lock().unwrap_or_else(PoisonError::into_inner)
}

impl BackendManager {
    pub fn status(&self) -> BackendStatus {
        lock(&self.status).clone()
    }

    fn set_status(&self, status: BackendStatus) {
        *lock(&self.status) = status;
    }

    pub fn mark_failed(&self, message: String) {
        log::error!("Backend failed: {message}");
        self.set_status(BackendStatus::Failed { message });
    }

    pub fn start(self: &Arc<Self>, launch: BackendLaunch) {
        let manager = Arc::clone(self);
        thread::spawn(move || {
            if let Err(message) = manager.run_startup(launch) {
                manager.stop();
                manager.mark_failed(message);
            }
        });
    }

    fn run_startup(&self, launch: BackendLaunch) -> Result<(), String> {
        std::fs::create_dir_all(&launch.data_dir)
            .map_err(|e| format!("Could not create data folder {}: {e}", launch.data_dir.display()))?;

        let token = generate_token()?;
        let mut command = Command::new(&launch.program);
        command
            .args(&launch.args)
            .arg("--data-dir")
            .arg(&launch.data_dir)
            .args(["--port", "0", "--token", &token])
            .current_dir(&launch.working_dir)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        hide_console_window(&mut command);

        log::info!("Starting backend: {}", launch.program.display());
        let mut child = command.spawn().map_err(|e| {
            format!("Could not start the backend ({}): {e}", launch.program.display())
        })?;

        self.attach_to_job(&child);
        let stdout = child.stdout.take().ok_or("Backend stdout was not captured")?;
        let stderr_tail = forward_stderr(child.stderr.take());
        *lock(&self.child) = Some(child);

        let port = wait_for_ready_line(stdout).map_err(|reason| {
            let exit = self.exit_description();
            let tail = lock(&stderr_tail).iter().cloned().collect::<Vec<_>>().join("\n");
            format!("{reason}{exit}\n{tail}").trim_end().to_string()
        })?;

        log::info!("Backend ready on 127.0.0.1:{port}");
        self.set_status(BackendStatus::Ready { port, token });
        Ok(())
    }

    /// Describes how the process ended, if it has ended.
    fn exit_description(&self) -> String {
        match lock(&self.child).as_mut().map(Child::try_wait) {
            Some(Ok(Some(status))) => format!(" (backend exited with {status})"),
            _ => String::new(),
        }
    }

    #[cfg(windows)]
    fn attach_to_job(&self, child: &Child) {
        use std::os::windows::io::AsRawHandle;
        let result = (|| -> Result<win32job::Job, win32job::JobError> {
            let job = win32job::Job::create()?;
            let mut info = job.query_extended_limit_info()?;
            info.limit_kill_on_job_close();
            job.set_extended_limit_info(&info)?;
            job.assign_process(child.as_raw_handle() as isize)?;
            Ok(job)
        })();
        match result {
            Ok(job) => *lock(&self.job) = Some(job),
            // Not fatal: we still stop the backend on normal exit.
            Err(e) => log::warn!("Could not attach backend to a Job Object: {e}"),
        }
    }

    #[cfg(not(windows))]
    fn attach_to_job(&self, _child: &Child) {}

    pub fn stop(&self) {
        if let Some(mut child) = lock(&self.child).take() {
            log::info!("Stopping backend");
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

/// Reads backend stdout until the READY line, the process exits, or we time out.
fn wait_for_ready_line(stdout: impl Read + Send + 'static) -> Result<u16, String> {
    let (sender, receiver) = mpsc::channel::<String>();
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            // After startup nobody listens any more; keep draining so the pipe never fills.
            let _ = sender.send(line);
        }
    });

    let deadline = Instant::now() + STARTUP_TIMEOUT;
    loop {
        let remaining = deadline.saturating_duration_since(Instant::now());
        match receiver.recv_timeout(remaining) {
            Ok(line) => {
                if let Some(port) = parse_ready_line(&line) {
                    return Ok(port);
                }
            }
            Err(RecvTimeoutError::Timeout) => {
                return Err(format!(
                    "The backend did not become ready within {} seconds.",
                    STARTUP_TIMEOUT.as_secs()
                ));
            }
            Err(RecvTimeoutError::Disconnected) => {
                return Err("The backend stopped during startup.".to_string());
            }
        }
    }
}

fn parse_ready_line(line: &str) -> Option<u16> {
    line.trim().strip_prefix(READY_PREFIX)?.parse().ok()
}

/// Forwards backend log lines to the app log and keeps the last few for error messages.
fn forward_stderr(stderr: Option<impl Read + Send + 'static>) -> Arc<Mutex<VecDeque<String>>> {
    let tail = Arc::new(Mutex::new(VecDeque::with_capacity(STDERR_TAIL_LINES)));
    if let Some(stderr) = stderr {
        let tail_writer = Arc::clone(&tail);
        thread::spawn(move || {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                log::info!("[backend] {line}");
                let mut buffer = lock(&tail_writer);
                if buffer.len() == STDERR_TAIL_LINES {
                    buffer.pop_front();
                }
                buffer.push_back(line);
            }
        });
    }
    tail
}

fn generate_token() -> Result<String, String> {
    let mut bytes = [0u8; TOKEN_BYTES];
    getrandom::fill(&mut bytes).map_err(|e| format!("Could not generate a security token: {e}"))?;
    Ok(bytes.iter().map(|b| format!("{b:02x}")).collect())
}

#[cfg(windows)]
fn hide_console_window(command: &mut Command) {
    use std::os::windows::process::CommandExt;
    const CREATE_NO_WINDOW: u32 = 0x0800_0000;
    command.creation_flags(CREATE_NO_WINDOW);
}

#[cfg(not(windows))]
fn hide_console_window(_command: &mut Command) {}

/// Development: run the backend source with the project's virtual environment.
/// Production: run the frozen backend shipped as a bundle resource (Stage 9).
pub fn resolve_launch(app: &AppHandle) -> Result<BackendLaunch, String> {
    if cfg!(debug_assertions) {
        let backend_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("backend");
        let python = backend_dir.join(".venv").join("Scripts").join("python.exe");
        if !python.exists() {
            return Err(format!(
                "Python virtual environment not found at {}. Run: py -3.13 -m venv backend\\.venv",
                python.display()
            ));
        }
        Ok(BackendLaunch {
            program: python,
            args: vec!["-m".into(), "powershift".into()],
            data_dir: backend_dir.join(".data"),
            working_dir: backend_dir,
        })
    } else {
        let resource_dir = app.path().resource_dir().map_err(|e| e.to_string())?;
        let backend_dir = resource_dir.join("backend");
        Ok(BackendLaunch {
            program: backend_dir.join("powershift-backend.exe"),
            args: Vec::new(),
            data_dir: app.path().app_data_dir().map_err(|e| e.to_string())?,
            working_dir: backend_dir,
        })
    }
}

#[tauri::command]
pub fn backend_status(manager: State<'_, Arc<BackendManager>>) -> BackendStatus {
    manager.status()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_ready_line() {
        assert_eq!(parse_ready_line("POWERSHIFT_READY port=51234"), Some(51234));
        assert_eq!(parse_ready_line("POWERSHIFT_READY port=51234\r\n"), Some(51234));
    }

    #[test]
    fn ignores_other_lines() {
        assert_eq!(parse_ready_line("INFO starting"), None);
        assert_eq!(parse_ready_line("POWERSHIFT_READY port=notanumber"), None);
        assert_eq!(parse_ready_line("POWERSHIFT_READY port=70000"), None);
    }

    #[test]
    fn token_is_64_hex_characters_and_random() {
        let a = generate_token().unwrap();
        let b = generate_token().unwrap();
        assert_eq!(a.len(), TOKEN_BYTES * 2);
        assert!(a.chars().all(|c| c.is_ascii_hexdigit()));
        assert_ne!(a, b);
    }

    #[test]
    fn ready_line_is_found_after_other_output() {
        let output = b"some log line\nPOWERSHIFT_READY port=4321\n".as_slice();
        assert_eq!(wait_for_ready_line(output), Ok(4321));
    }

    #[test]
    fn process_ending_before_ready_is_reported() {
        let output = b"crashed\n".as_slice();
        assert!(wait_for_ready_line(output).unwrap_err().contains("stopped during startup"));
    }

    #[test]
    fn status_serialises_with_state_tag() {
        let ready = BackendStatus::Ready { port: 1, token: "t".into() };
        assert_eq!(
            serde_json::to_string(&ready).unwrap(),
            r#"{"state":"ready","port":1,"token":"t"}"#
        );
    }
}
