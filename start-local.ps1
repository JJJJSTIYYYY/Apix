# Start all APIX backend services locally (non-Docker mode).
# Run this after setup.ps1 has installed dependencies and started Redis/MySQL.

$ROOT = Get-Location

$services = @(
    @{ Name = "TASK";  Path = "TASK/task_flow_module";   Port = 5090 },
    @{ Name = "AGENT"; Path = "AGENT/agent_module";      Port = 5091 },
    @{ Name = "MEMORY"; Path = "MEMORY/memory_module";   Port = 5093 },
    @{ Name = "FILE";  Path = "FILE/file_service";       Port = 5094 }
)

Write-Host "Starting APIX backend services locally..."

foreach ($svc in $services) {
    $jobName = "apix-$($svc.Name.ToLower())"
    Push-Location "$ROOT\$($svc.Path)"
    Write-Host "[$($svc.Name)] Starting uvicorn on port $($svc.Port)..."
    Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run", "main.py" -WorkingDirectory (Get-Location)
    Pop-Location
}

Write-Host "All backend services started."
Write-Host "AGENT : http://127.0.0.1:5091"
Write-Host "TASK  : http://127.0.0.1:5090"
Write-Host "MEMORY: http://127.0.0.1:5093"
Write-Host "FILE  : http://127.0.0.1:5094"
