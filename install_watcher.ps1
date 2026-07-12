# script de instalación para Windows (SES Watcher)
# Ejecuta este script para configurar el Watcher en el inicio automático de Windows.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TrayAppPath = "$ScriptDir\ses\watcher\tray_app.py"

# Buscar pythonw.exe (versión sin consola de python)
$PythonwExe = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source

if (-not $PythonwExe) {
    Write-Host "❌ No se encontró pythonw.exe en tu sistema."
    Write-Host "Asegúrate de tener Python instalado y agregado a tu variable de entorno PATH."
    Pause
    exit 1
}

Write-Host "⚙️ Configurando SES Enterprise Watcher..."

# Crear carpeta de documentos por defecto si no existe
$DefaultDocs = "$env:USERPROFILE\Documents\SES_Ingest"
if (-not (Test-Path $DefaultDocs)) {
    New-Item -ItemType Directory -Force -Path $DefaultDocs | Out-Null
    Write-Host "📂 Carpeta de sincronización creada en: $DefaultDocs"
}

# Crear acceso directo en la carpeta de Inicio de Windows
$WshShell = New-Object -comObject WScript.Shell
$StartupPath = [Environment]::GetFolderPath("Startup")
$ShortcutPath = "$StartupPath\SES_Enterprise_Watcher.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonwExe
$Shortcut.Arguments = """$TrayAppPath"""
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Description = "Sincronización automática de documentos para SES Enterprise"
$Shortcut.IconLocation = "$PythonwExe, 0"
$Shortcut.Save()

Write-Host "✅ ¡Instalación exitosa!"
Write-Host "El Watcher se ejecutará silenciosamente en la bandeja del sistema (junto al reloj) cada vez que inicies Windows."
Write-Host ""
Write-Host "Iniciando la aplicación ahora mismo para ti..."

# Iniciar la aplicación ahora
Start-Process -FilePath $PythonwExe -ArgumentList """$TrayAppPath""" -WorkingDirectory $ScriptDir

Write-Host "Completado. Puedes cerrar esta ventana."
Pause
