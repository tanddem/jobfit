# Stop and remove the JobFit container. The jobfit-data volume is kept.
if (docker ps -aq --filter "name=^jobfit$") {
    docker rm -f jobfit | Out-Null
    Write-Host "JobFit stopped."
} else {
    Write-Host "JobFit was not running."
}
