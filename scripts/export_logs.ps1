$ErrorActionPreference = "Stop"

$target = "exported_logs"
New-Item -ItemType Directory -Force -Path $target | Out-Null

Write-Host "Copying logs from app container..."
docker compose cp app:/app/logs $target

Write-Host "Done. Logs copied to ./$target"
