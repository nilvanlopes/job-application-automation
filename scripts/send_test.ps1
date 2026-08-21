$ErrorActionPreference = "Stop"

Write-Host "Iniciando envio pelo Outlook COM..." -ForegroundColor Cyan

try {
    $outlook = [System.Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application")
} catch {
    $outlook = New-Object -ComObject Outlook.Application
}

$session = $outlook.Session

$account = $session.Accounts | Where-Object { $_.SmtpAddress -eq 'nilvanlopes@outlook.com' } | Select-Object -First 1
if (-not $account) {
    $account = $session.Accounts.Item(1)
}

$htmlPath = "\\wsl.localhost\Ubuntu\home\pyu\docker\job-application-automation\output\fast_test_email.html"
if (-not (Test-Path $htmlPath)) {
    $htmlPath = "\\wsl$\Ubuntu\home\pyu\docker\job-application-automation\output\fast_test_email.html"
}

$html = Get-Content $htmlPath -Raw -Encoding UTF8

$mail = $outlook.CreateItem(0)
$mail.SendUsingAccount = $account
$mail.To = "pyuloko7@gmail.com"
$mail.Subject = "Teste de Assinatura Automática - Nilvan Lopes"
$mail.HTMLBody = $html
$mail.Send()

Write-Host "✅ E-MAIL ENVIADO COM SUCESSO PARA pyuloko7@gmail.com!" -ForegroundColor Green

# Sincronizar saída
try {
    for($i = 1; $i -le $session.SyncObjects.Count; $i++) {
        try {
            $s = $session.SyncObjects.Item($i)
            $s.Start()
        } catch {}
    }
} catch {}
