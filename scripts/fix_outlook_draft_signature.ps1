$ErrorActionPreference = "Stop"

try {
    $outlook = [System.Runtime.InteropServices.Marshal]::GetActiveObject("Outlook.Application")
} catch {
    $outlook = New-Object -ComObject Outlook.Application
}

$item = $null
try {
    $inspector = $outlook.ActiveInspector
    if ($inspector -and $inspector.CurrentItem) {
        $item = $inspector.CurrentItem
    }
} catch {}

if (-not $item) {
    Write-Error "Janela de mensagem aberta não encontrada."
    exit 1
}

$body = $item.HTMLBody

# Extrair a parte do email original de Pedro (a partir de 'De: Pedro Burity' ou 'From: Pedro Burity' ou <hr>)
$originalEmail = ""
if ($body -match '(?i)(<div style=.border:none;border-top:solid #E1E1E1 1.0pt.*?|<b>De:</b> Pedro Burity.*|De: Pedro Burity.*|<hr\b.*)') {
    $originalEmail = $Matches[1]
} elseif ($body -match '(?i)(<hr.*)') {
    $originalEmail = $Matches[1]
}

# Assinatura limpa compatível com o Word do Outlook
$sig = @'
<div style="font-family:Arial,Helvetica,sans-serif; margin-top:16px; margin-bottom:24px;">
  <table cellpadding="0" cellspacing="0" border="0" width="560" bgcolor="#0d0d0d" style="width:560px; background:#0d0d0d; border-collapse:collapse; border-bottom:4px solid #d4af37;">
    <tr>
      <td bgcolor="#0d0d0d" style="padding:16px 20px; background-color:#0d0d0d;">
        <table cellpadding="0" cellspacing="0" border="0" width="100%" bgcolor="#0d0d0d" style="width:100%; border-collapse:collapse; background-color:#0d0d0d;">
          <tr>
            <td valign="middle" bgcolor="#0d0d0d" style="background-color:#0d0d0d; padding-right:15px;">
              <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/nilvan-lopes.png" width="210" height="56" alt="Nilvan Lopes" style="display:block; width:210px; height:auto; border:0;">
              <div style="font-size:12px; font-weight:bold; color:#e6c76a; font-family:Arial,sans-serif; margin-top:2px; margin-left:12px; letter-spacing:0.5px;">Desenvolvedor FullStack</div>
              <div style="margin-top:8px; font-size:12px; line-height:16px; color:#ffffff; font-family:Arial,sans-serif;">
                <span style="color:#d4af37; font-weight:bold;">T:</span> <a href="tel:+5563992230471" style="color:#ffffff; text-decoration:none;">+55 (63) 99223-0471</a><br>
                <span style="color:#d4af37; font-weight:bold;">E:</span> <a href="mailto:nilvanlopes@outlook.com" style="color:#ffffff; text-decoration:none;">nilvanlopes@outlook.com</a>
              </div>
            </td>
            <td valign="middle" width="180" align="right" bgcolor="#0d0d0d" style="width:180px; text-align:right; background-color:#0d0d0d;">
              <div style="margin-bottom:8px;">
                <img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/eu.png" width="76" height="76" alt="Nilvan Lopes" style="display:inline-block; width:76px; height:76px; border:2px solid #d4af37; border-radius:50%;">
              </div>
              <div style="margin-top:6px;">
                <a href="https://www.linkedin.com/in/nilvanlopes" target="_blank" style="text-decoration:none; margin-left:8px;"><img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/linkedin.png" width="18" height="18" alt="LinkedIn" style="border:0; display:inline-block;"></a>
                <a href="https://github.com/nilvanlopes" target="_blank" style="text-decoration:none; margin-left:8px;"><img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/github.png" width="18" height="18" alt="GitHub" style="border:0; display:inline-block;"></a>
                <a href="https://wa.me/5563992230471" target="_blank" style="text-decoration:none; margin-left:8px;"><img src="https://raw.githubusercontent.com/nilvanlopes/mail-signature/main/assets/whatsapp.png" width="18" height="18" alt="WhatsApp" style="border:0; display:inline-block;"></a>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</div>
'@

# Mensagem de resposta estruturada
$replyText = @'
<p style="font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#ffffff; line-height:1.5;">Olá Pedro, tudo bem?</p>
<p style="font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#ffffff; line-height:1.5;">Confirmo o recebimento e o total interesse em seguir no processo seletivo para a vaga em Paraíso do Tocantins.</p>
<p style="font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#ffffff; line-height:1.5;">Já realizei o agendamento da nossa entrevista pelo link informado. Fico à disposição!</p>
<p style="font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#ffffff; line-height:1.5; margin-bottom:16px;">Atenciosamente,</p>
'@

# Montar o HTML completo com a resposta no topo, a assinatura no meio e o histórico de Pedro abaixo
if ($originalEmail) {
    $newHtml = "<html><body style='font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#ffffff;'>" + $replyText + $sig + "<hr style='border:none; border-top:1px solid #444; margin-top:20px; margin-bottom:20px;'>" + $originalEmail + "</body></html>"
} else {
    $newHtml = "<html><body style='font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#ffffff;'>" + $replyText + $sig + "<hr style='border:none; border-top:1px solid #444; margin-top:20px; margin-bottom:20px;'>" + $body + "</body></html>"
}

$item.HTMLBody = $newHtml
Write-Host "SUCCESS: Resposta e assinatura formatadas com sucesso!"
