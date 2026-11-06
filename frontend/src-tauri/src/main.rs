#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use rand::RngCore;
use serde::Serialize;
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

#[derive(Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct ApiConnection {
    origin: String,
    token: String,
}

struct DesktopState {
    connection: ApiConnection,
    sidecar: Mutex<Option<CommandChild>>,
}

#[tauri::command]
fn desktop_connection(state: tauri::State<'_, DesktopState>) -> ApiConnection {
    state.connection.clone()
}

// A portable archive ships portable.flag beside the Windows executable.
// Linux AppImage provides APPIMAGE as the path of its outer executable.
// In portable mode persistent data must remain beside the application;
// a read-only destination is an error, never a silent profile fallback.
fn portable_directory(executable: &Path, appimage: Option<&Path>) -> Option<PathBuf> {
    if let Some(image) = appimage {
        if image.is_file() {
            return image.parent().map(Path::to_path_buf);
        }
    }
    let parent = executable.parent()?;
    parent.join("portable.flag").is_file().then(|| parent.to_path_buf())
}

fn portable_data_root() -> Option<PathBuf> {
    let executable = std::env::current_exe().ok()?;
    #[cfg(target_os = "linux")]
    let appimage = std::env::var_os("APPIMAGE").map(PathBuf::from);
    #[cfg(not(target_os = "linux"))]
    let appimage: Option<PathBuf> = None;
    portable_directory(&executable, appimage.as_deref()).map(|dir| dir.join("LumaCarveData"))
}

fn start_sidecar(app: &tauri::App) -> Result<DesktopState, Box<dyn std::error::Error>> {
    let data_root = match portable_data_root() {
        Some(root) => root,
        None => app.path().app_data_dir()?,
    };
    let data_dir = data_root.join("workspace");
    std::fs::create_dir_all(&data_dir)?;
    std::fs::create_dir_all(data_root.join("logs"))?;

    let listener = TcpListener::bind(("127.0.0.1", 0))?;
    let port = listener.local_addr()?.port();
    drop(listener);

    let mut secret = [0u8; 32];
    rand::rngs::OsRng.fill_bytes(&mut secret);
    let token: String = secret.iter().map(|byte| format!("{byte:02x}")).collect();
    let origin = format!("http://127.0.0.1:{port}");
    let command = app.shell().sidecar("lumacarve-api")?
        .env("LUMACARVE_DATA_DIR", data_dir.to_string_lossy().to_string())
        .env("LUMACARVE_PORT", port.to_string())
        .env("LUMACARVE_HOST", "127.0.0.1")
        .env("LUMACARVE_DESKTOP_TOKEN", token.clone())
        .env("LUMACARVE_ALLOWED_ORIGINS", "http://tauri.localhost,tauri://localhost")
        .env("LUMACARVE_INFERENCE_BACKEND", "disabled");
    let (mut receiver, child) = command.spawn()?;
    tauri::async_runtime::spawn(async move {
        while receiver.recv().await.is_some() {}
    });
    Ok(DesktopState { connection: ApiConnection { origin, token }, sidecar: Mutex::new(Some(child)) })
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![desktop_connection])
        .setup(|app| {
            let state = start_sidecar(app)?;
            app.manage(state);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Could not initialize LumaCarve Tauri 2");

    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = app_handle.try_state::<DesktopState>() {
                if let Ok(mut child) = state.sidecar.lock() {
                    if let Some(child) = child.take() {
                        let _ = child.kill();
                    }
                }
            }
        }
    });
}

#[cfg(test)]
mod portable_tests {
    use super::portable_directory;
    use std::fs;
    use std::path::Path;

    #[test]
    fn portable_marker_keeps_data_next_to_executable() {
        let root = std::env::temp_dir().join(format!(
            "lumacarve-portable-test-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        fs::create_dir_all(&root).unwrap();
        let executable = root.join("LumaCarve.exe");
        assert_eq!(portable_directory(&executable, None), None);
        fs::write(root.join("portable.flag"), b"").unwrap();
        assert_eq!(portable_directory(&executable, None), Some(root.clone()));
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn appimage_uses_its_original_location() {
        let root = std::env::temp_dir().join(format!(
            "lumacarve-appimage-test-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        fs::create_dir_all(&root).unwrap();
        let image = root.join("LumaCarve.AppImage");
        fs::write(&image, b"appimage").unwrap();
        assert_eq!(
            portable_directory(Path::new("/tmp/appimage-mount/lumacarve-desktop"), Some(&image)),
            Some(root.clone())
        );
        fs::remove_dir_all(root).unwrap();
    }
}
