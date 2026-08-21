import argparse
import subprocess
from pathlib import Path

from job_application_automation.signature import SignatureProfile, build_signature_html
from job_application_automation.outlook_com_mailer import _to_windows_path, _ps_quote


def main():
    parser = argparse.ArgumentParser(description="Cria rascunho ou envia uma resposta (Reply) automática com assinatura perfeita pelo Outlook.")
    parser.add_argument("--search", default="Colab", help="Termo para buscar no assunto, remetente ou destinatário (ex: Colab, pyuloko7)")
    parser.add_argument("--body", default="", help="Texto direto da resposta.")
    parser.add_argument("--body-file", type=Path, default=None, help="Caminho para arquivo .txt ou .md com o texto da resposta.")
    parser.add_argument("--recipient", default="", help="Destinatário forçado caso necessário")
    parser.add_argument("--send", action="store_true", help="Se definido, envia diretamente. Por padrão, salva como RASCUNHO.")
    parser.add_argument("--display", action="store_true", default=True, help="Abre a janela do rascunho na tela do Outlook quando não envia.")
    args = parser.parse_args()

    default_body = (
        "Olá Pedro, tudo bem?\n\n"
        "Confirmo o recebimento e interesse em seguir no processo seletivo.\n\n"
        "Já realizei o agendamento da nossa entrevista pelo link informado. Fico à disposição e aguardo nosso bate-papo!\n\n"
        "Até mais tarde."
    )

    if args.body_file and args.body_file.exists():
        body_text = args.body_file.read_text(encoding="utf-8").strip()
    elif args.body.strip():
        body_text = args.body.strip()
    else:
        body_text = default_body

    paragraphs = "".join(
        f"<p style='font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111111;line-height:1.5;margin:0 0 12px 0;'>{part.replace(chr(10), '<br>')}</p>"
        for part in body_text.split("\n\n")
        if part.strip()
    )

    profile = SignatureProfile(
        name="Nilvan Lopes",
        role="Desenvolvedor FullStack",
        phone="(63) 99223-0471",
        email="nilvanlopes@outlook.com",
        website="https://nilvanlopes.com",
        linkedin="https://www.linkedin.com/in/nilvanlopes",
        github="https://github.com/nilvanlopes",
        whatsapp="https://wa.me/5563992230471",
    )
    sig_html = build_signature_html(profile)

    combined_html = f"{paragraphs}\n{sig_html}\n<br><br>"

    temp_html_file = Path("output/temp_reply_body.html").resolve()
    temp_html_file.parent.mkdir(parents=True, exist_ok=True)
    temp_html_file.write_text(combined_html, encoding="utf-8")

    windows_html_path = _to_windows_path(temp_html_file)
    sender_email = _ps_quote("nilvanlopes@outlook.com")
    action_send = "$true" if args.send else "$false"
    action_display = "$true" if args.display and not args.send else "$false"
    forced_recipient = _ps_quote(args.recipient.strip()) if args.recipient.strip() else "$null"

    ps_code = f"""
$ErrorActionPreference = "Stop";
$outlook = New-Object -ComObject Outlook.Application;
$session = $outlook.Session;

$account = $session.Accounts | Where-Object {{ $_.SmtpAddress -eq {sender_email} }} | Select-Object -First 1;
if (-not $account) {{
    $account = $session.Accounts.Item(1);
}}

$mail = $null;

# 1. Tentar pegar o e-mail selecionado na tela
try {{
    $selection = $outlook.ActiveExplorer.Selection;
    if ($selection.Count -gt 0) {{
        $mail = $selection.Item(1);
        Write-Host "SELECTED_MAIL Subject=$($mail.Subject) From=$($mail.SenderEmailAddress)";
    }}
}} catch {{}}

# 2. Buscar na Caixa de Entrada
if (-not $mail) {{
    try {{
        $inbox = $session.GetDefaultFolder(6);
        $items = $inbox.Items;
        $items.Sort("[ReceivedTime]", $true);
        foreach ($item in $items) {{
            if ($item.Subject -like "*{args.search}*" -or $item.SenderEmailAddress -like "*{args.search}*" -or $item.To -like "*{args.search}*") {{
                $mail = $item;
                Write-Host "FOUND_INBOX_MAIL Subject=$($mail.Subject) From=$($mail.SenderEmailAddress)";
                break;
            }}
        }}
    }} catch {{}}
}}

if (-not $mail) {{
    Write-Error "Nenhum e-mail correspondente a '{args.search}' foi encontrado na Caixa de Entrada.";
    exit 1;
}}

$newBodyHtml = Get-Content '{windows_html_path}' -Raw -Encoding UTF8;

# Criar o objeto Reply nativo do Outlook
$reply = $mail.Reply();
$reply.SendUsingAccount = $account;

# Garantir que o destinatario seja preenchido explicitamente
$targetTo = if ({forced_recipient}) {{ {forced_recipient} }} elseif ($mail.SenderEmailAddress) {{ $mail.SenderEmailAddress }} else {{ $reply.To }};
$reply.To = $targetTo;
$reply.Recipients.ResolveAll();

$replySubject = if ($reply.Subject) {{ $reply.Subject }} else {{ "RE: " + $mail.Subject }};
$reply.Subject = $replySubject;

$reply.HTMLBody = $newBodyHtml + $reply.HTMLBody;

if ({action_send}) {{
    $reply.Send();
    Write-Host "SENT_REPLY_SUBMITTED To=$targetTo Subject=$replySubject";
    
    # Forcar sincronizacao para mover da Caixa de Saida para Itens Enviados
    Write-Host "Sincronizando envio com o servidor de e-mail...";
    try {{
        for($i = 1; $i -le $session.SyncObjects.Count; $i++) {{
            try {{
                $s = $session.SyncObjects.Item($i);
                $s.Start();
            }} catch {{}}
        }}
        Start-Sleep -Seconds 8;
    }} catch {{}}

    # Verificar se ja entrou em Itens Enviados
    $sentFolder = $session.GetDefaultFolder(5);
    $sentItems = $sentFolder.Items;
    $sentItems.Sort("[SentOn]", $true);
    $foundSent = $false;
    foreach ($sItem in $sentItems) {{
        if ($sItem.To -like "*$targetTo*" -or $sItem.Subject -like "*$replySubject*") {{
            Write-Host "CONFIRMED_IN_SENT_ITEMS SentOn=$($sItem.SentOn) To=$($sItem.To) Subject=$($sItem.Subject)";
            $foundSent = $true;
            break;
        }}
    }}

    if (-not $foundSent) {{
        $outbox = $session.GetDefaultFolder(4);
        Write-Host "INFO: A mensagem esta na Caixa de Saida ($($outbox.Items.Count) item) e sera despachada pelo Outlook na proxima sincronizacao.";
    }}
}} else {{
    $reply.Save();
    Write-Host "SAVED_DRAFT_SUCCESS To=$targetTo Subject=$replySubject";
    if ({action_display}) {{
        try {{
            $reply.Display();
            Write-Host "DRAFT_DISPLAYED_ON_SCREEN";
        }} catch {{}}
    }}
}}
"""

    cmd = ["powershell.exe", "-NoProfile", "-Command", ps_code]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:")
    print(result.stdout)
    if result.stderr:
        print("STDERR:")
        print(result.stderr)


if __name__ == "__main__":
    main()
