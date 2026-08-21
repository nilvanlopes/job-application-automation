import subprocess
import time

ps_test = """
Write-Host "STEP 1: Starting Outlook COM"
try {
    $outlook = New-Object -ComObject Outlook.Application
    Write-Host "STEP 1 OK: Outlook COM object created"
} catch {
    Write-Host "STEP 1 FAILED: $_"
    exit 1
}

Write-Host "STEP 2: Getting Session and Accounts"
try {
    $session = $outlook.Session
    $accounts = $session.Accounts
    Write-Host "STEP 2 OK: Found $($accounts.Count) accounts"
    foreach ($acc in $accounts) {
        Write-Host "  - Account: $($acc.DisplayName) ($($acc.SmtpAddress))"
    }
} catch {
    Write-Host "STEP 2 FAILED: $_"
    exit 1
}

Write-Host "STEP 3: Testing Path Access"
$path1 = "\\\\wsl.localhost\\Ubuntu\\home\\pyu\\docker\\job-application-automation\\output\\test_email_signature.html"
$path2 = "\\\\wsl$\\Ubuntu\\home\\pyu\\docker\\job-application-automation\\output\\test_email_signature.html"

if (Test-Path $path1) {
    Write-Host "STEP 3 OK: path1 accessible"
} else {
    Write-Host "STEP 3 WARNING: path1 NOT accessible"
}

if (Test-Path $path2) {
    Write-Host "STEP 3 OK: path2 accessible"
} else {
    Write-Host "STEP 3 WARNING: path2 NOT accessible"
}

Write-Host "ALL DIAGNOSTICS COMPLETED"
"""

print("Running diagnostics...")
cmd = ["powershell.exe", "-NoProfile", "-Command", ps_test]
try:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = p.communicate(timeout=15)
    print("STDOUT:")
    print(stdout)
    if stderr:
        print("STDERR:")
        print(stderr)
except subprocess.TimeoutExpired:
    p.kill()
    print("TIMEOUT: PowerShell hung during diagnostics!")
except Exception as e:
    print("ERROR:", e)
