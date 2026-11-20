# Apaga la API (puerto 8000) y la pagina web (puerto 3000) de Zeno Investments.
# La base de datos (PostgreSQL) sigue funcionando: es un servicio de Windows.

$host.UI.RawUI.WindowTitle = "Zeno Investments"
Write-Host "Apagando Zeno Investments..." -ForegroundColor Cyan

# Las ventanas que abrio "Iniciar Zeno.bat" (se cierra cada una con todo lo que lanzo)
$ventanas = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*Zeno - *(no cerrar)*" }
foreach ($v in $ventanas) { & taskkill.exe /PID $v.ProcessId /T /F *> $null }

# Por si la API o la pagina se habian levantado de otra forma
foreach ($item in @(@{ Puerto = 8000; Nombre = "API" }, @{ Puerto = 3000; Nombre = "Pagina web" })) {
    $ids = Get-NetTCPConnection -LocalPort $item.Puerto -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($id in $ids) { & taskkill.exe /PID $id /T /F *> $null }
    Start-Sleep -Milliseconds 300
    if (Get-NetTCPConnection -LocalPort $item.Puerto -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "  $($item.Nombre): no se pudo apagar." -ForegroundColor Yellow
    } else {
        Write-Host "  $($item.Nombre): apagada."
    }
}

Write-Host ""
Write-Host "Listo." -ForegroundColor Green
Start-Sleep -Seconds 3
