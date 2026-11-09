//! PowerShift desktop shell.
//!
//! The Rust side has one job beyond opening the window: start the local Python
//! backend, tell the frontend where it is, and make sure it stops with the app.

mod backend;

use std::sync::Arc;

use backend::BackendManager;
use tauri::RunEvent;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let manager = Arc::new(BackendManager::default());
    let setup_manager = Arc::clone(&manager);

    let app = tauri::Builder::default()
        .plugin(
            tauri_plugin_log::Builder::default()
                .level(log::LevelFilter::Info)
                .build(),
        )
        .manage(Arc::clone(&manager))
        .invoke_handler(tauri::generate_handler![backend::backend_status])
        .setup(move |app| {
            match backend::resolve_launch(app.handle()) {
                Ok(launch) => setup_manager.start(launch),
                Err(message) => setup_manager.mark_failed(message),
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the PowerShift application");

    app.run(move |_, event| {
        if let RunEvent::Exit = event {
            manager.stop();
        }
    });
}
