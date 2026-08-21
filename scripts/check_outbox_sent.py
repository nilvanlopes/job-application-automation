import subprocess

ps_code = """
$outlook = New-Object -ComObject Outlook.Application
$session = $outlook.Session

$outbox = $session.GetDefaultFolder(4) # olFolderOutbox
$sent = $session.GetDefaultFolder(5)   # olFolderSentMail

Write-Host "=== CAIXA DE SAÍDA (OUTBOX) ==="
$outboxItems = $outbox.Items
Write-Host "Total na Caixa de Saída: $($outboxItems.Count)"
foreach ($item in $outboxItems) {
    Write-Host "  - Para: $($item.To) | Assunto: $($item.Subject)"
}

Write-Host "`n=== ÚLTIMOS 5 ITENS ENVIADOS ==="
$sentItems = $sent.Items
$sentItems.Sort("[SentOn]", $true)
$count = 0
foreach ($item in $sentItems) {
    if ($count -ge 5) { break }
    Write-Host "  - Enviado em: $($item.SentOn) | Para: $($item.To) | Assunto: $($item.Subject)"
    $count++
}
"""

cmd = ["powershell.exe", "-NoProfile", "-Command", ps_code]
result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
