# Levanta Zeno Investments en esta compu: base de datos, API (puerto 8000) y front (puerto 3000).
# Se ejecuta con doble clic en "Iniciar Zeno.bat", en la carpeta del proyecto.

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$back = Join-Path $raiz "backend"
$front = Join-Path $raiz "frontend"
$env:Path = "C:\Program Files\nodejs;" + $env:Path
$host.UI.RawUI.WindowTitle = "Zeno Investments"

function Escuchando([int]$puerto) {
    [bool](Get-NetTCPConnection -LocalPort $puerto -State Listen -ErrorAction SilentlyContinue)
}

function Esperar([int]$puerto, [int]$segundos) {
    for ($i = 0; $i -lt $segundos; $i++) {
        if (Escuchando $puerto) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Paso([string]$texto) { Write-Host ""; Write-Host "> $texto" -ForegroundColor Cyan }

try {
    Write-Host "Zeno Investments" -ForegroundColor Green

    # 1. Base de datos: el servicio de PostgreSQL arranca solo con Windows; si estaba parado, se intenta prender
    Paso "Base de datos"
    $pg = Get-Service "postgresql-x64-19" -ErrorAction SilentlyContinue
    if (-not $pg) {
        Write-Host "  No encontre el servicio de PostgreSQL 19." -ForegroundColor Yellow
    } elseif ($pg.Status -eq "Running") {
        Write-Host "  PostgreSQL 19 funcionando."
    } else {
        try {
            Start-Service $pg.Name
            Write-Host "  PostgreSQL 19 iniciado."
        } catch {
            Write-Host "  PostgreSQL 19 esta detenido y no se pudo iniciar sin permisos de administrador." -ForegroundColor Yellow
            Write-Host "  Abri 'Servicios' de Windows e inicia 'postgresql-x64-19'."
        }
    }

    # 2. API (FastAPI) en su propia ventana
    Paso "API (puerto 8000)"
    if (Escuchando 8000) {
        Write-Host "  Ya estaba corriendo."
    } else {
        $python = Join-Path $back ".venv\Scripts\python.exe"
        if (-not (Test-Path $python)) { throw "No encuentro el entorno de Python en $python" }
        $cmd = "`$host.UI.RawUI.WindowTitle = 'Zeno - API (no cerrar)'; Set-Location '$back'; & '$python' -m uvicorn src.app:app --host 0.0.0.0 --port 8000"
        Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-Command", $cmd -WindowStyle Minimized
        if (Esperar 8000 40) { Write-Host "  Lista." } else { Write-Host "  Tarda en arrancar: mira la ventana 'Zeno - API'." -ForegroundColor Yellow }
    }

    # 3. Front (Next.js en modo produccion). Se compila solo si cambio algo desde la ultima vez
    Paso "Pagina web (puerto 3000)"
    if (Escuchando 3000) {
        Write-Host "  Ya estaba corriendo."
    } else {
        Set-Location $front
        if (-not (Test-Path (Join-Path $front "node_modules"))) {
            Write-Host "  Instalando dependencias (solo la primera vez)..."
            & npm.cmd install
            if ($LASTEXITCODE -ne 0) { throw "Fallo 'npm install'." }
        }
        $build = Join-Path $front ".next\BUILD_ID"
        $fuentes = @("app", "components", "context", "lib", "public", "next.config.ts", "package.json") |
            ForEach-Object { Join-Path $front $_ } | Where-Object { Test-Path $_ }
        $ultimo = Get-ChildItem $fuentes -Recurse -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not (Test-Path $build) -or $ultimo.LastWriteTime -gt (Get-Item $build).LastWriteTime) {
            Write-Host "  Hay cambios: compilando la pagina (tarda menos de un minuto)..."
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) { throw "La compilacion fallo: revisa los errores de arriba." }
        } else {
            Write-Host "  Sin cambios desde la ultima compilacion."
        }
        $cmd = "`$host.UI.RawUI.WindowTitle = 'Zeno - Pagina web (no cerrar)'; `$env:Path = 'C:\Program Files\nodejs;' + `$env:Path; Set-Location '$front'; npm.cmd run start -- -p 3000"
        Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-Command", $cmd -WindowStyle Minimized
        if (Esperar 3000 40) { Write-Host "  Lista." } else { Write-Host "  Tarda en arrancar: mira la ventana 'Zeno - Pagina web'." -ForegroundColor Yellow }
    }

    # 4. Abrir el navegador y mostrar la direccion para el celular (misma red Wi-Fi)
    Start-Process "http://localhost:3000"
    $ip = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.PrefixOrigin -ne "WellKnown" } |
        Select-Object -First 1 -ExpandProperty IPAddress
    Write-Host ""
    Write-Host "Listo. Zeno Investments esta funcionando:" -ForegroundColor Green
    Write-Host "  En esta compu:  http://localhost:3000"
    if ($ip) { Write-Host "  En el celular:  http://${ip}:3000  (conectado al mismo Wi-Fi)" }
    Write-Host ""
    Write-Host "La API y la pagina quedan en dos ventanas minimizadas. Para apagar todo: 'Detener Zeno.bat'."
    Write-Host "Esta ventana se cierra sola en 15 segundos."
    Start-Sleep -Seconds 15
} catch {
    Write-Host ""
    Write-Host "No se pudo iniciar: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Apreta Enter para cerrar"
    exit 1
}
