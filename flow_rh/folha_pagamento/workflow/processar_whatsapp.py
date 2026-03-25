import os
import sys
import base64
import subprocess
import requests

def download_and_extract():
    # 1. Obter variáveis do ambiente
    api_url = os.environ.get("EVOLUTION_API_URL")
    instance = os.environ.get("EVOLUTION_INSTANCE")
    api_key = os.environ.get("EVOLUTION_API_KEY")
    remote_jid = os.environ.get("REMOTE_JID")
    message_key_id = os.environ.get("MESSAGE_KEY_ID")

    if not all([api_url, instance, api_key, remote_jid, message_key_id]):
        print("❌ Faltando variáveis de ambiente (EVOLUTION_...).", file=sys.stderr)
        sys.exit(1)

    # 2. Download do PDF via Evolution API
    print(f"📥 Baixando PDF da mensagem {message_key_id}...")
    resp = requests.post(
        f"{api_url}/chat/getBase64FromMediaMessage/{instance}",
        json={
            "message": {
                "key": {
                    "remoteJid": remote_jid,
                    "fromMe": False,
                    "id": message_key_id
                }
            },
            "convertToMp4": False
        },
        headers={"apikey": api_key},
        timeout=60
    )

    if resp.status_code >= 300:
        print(f"❌ Erro ao baixar mídia: HTTP {resp.status_code}", file=sys.stderr)
        print(f"   Response: {resp.text}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    b64_content = data.get("base64", "")
    if not b64_content:
        print("❌ Resposta sem conteúdo base64!", file=sys.stderr)
        sys.exit(1)

    # Remove data URI prefix if present
    if "base64," in b64_content:
        b64_content = b64_content.split("base64,")[1]

    pdf_bytes = base64.b64decode(b64_content)
    pdf_input = "folha_input.pdf"
    output_csv = "folha_resultado.csv"

    with open(pdf_input, "wb") as f:
        f.write(pdf_bytes)
    print(f"✅ PDF salvo ({len(pdf_bytes)} bytes)")

    # 3. Executar o script de extração (que já está no repo)
    print("💎 Iniciando extração dos dados...")
    result = subprocess.run(
        [
            "python", 
            "flow_rh/folha_pagamento/workflow/extrair_folha.py",
            "--pdf", pdf_input, 
            "--output", output_csv
        ],
        capture_output=True, 
        text=True
    )

    # Proxy o output do extrator
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"❌ Falha no script de extração (Exit Code: {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    
    print(f"✅ Processamento concluído: {output_csv}")

if __name__ == "__main__":
    download_and_extract()
