param(
    [ValidateRange(0, 3600)]
    [int]$DelaySeconds = 60
)

$ErrorActionPreference = 'Stop'
$message = 'Candidatura concluida pela skill candidate-a-essa-vaga'
& "$env:WINDIR\System32\shutdown.exe" /s /t $DelaySeconds /d p:4:1 /c $message
if ($LASTEXITCODE -ne 0) {
    throw "Windows shutdown request failed with exit code $LASTEXITCODE"
}
Write-Output "WINDOWS_SHUTDOWN_REQUESTED delay=$DelaySeconds"
