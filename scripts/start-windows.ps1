# Build the JobFit image and run it on http://localhost:8000.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

docker build -t jobfit .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
# Windows PowerShell 5.1 turns native stderr into a terminating error under "Stop",
# and docker rm writes to stderr when no container exists yet.
$ErrorActionPreference = "Continue"
docker rm -f jobfit 2>$null | Out-Null
$ErrorActionPreference = "Stop"

$envArgs = @()
if (Test-Path ".env") { $envArgs = @("--env-file", ".env") }

docker run -d --name jobfit -p 8000:8000 -v jobfit-data:/data @envArgs jobfit | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "JobFit is running at http://localhost:8000"
