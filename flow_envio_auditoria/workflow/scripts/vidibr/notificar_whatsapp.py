import os
import json
import requests
import logging
import sys
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s]: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("NotificarAuditoria")

load_dotenv()
URL = os.environ.get("EVOLUTION_API_URL")
KEY = os.environ.get("EVOLUTION_API_KEY")
INSTANCE = os.environ.get("EVOLUTION_INSTANCE")
GROUP = os.environ.get("WHATSAPP_GROUP_ID")

def enviar(resultado):
    status = resultado.get('status')
    if status not in ['novo_formulario', 'primeiro_registro']:
        logger.info(f"Status '{status}' não requer notificação.")
        return

    if status == 'novo_formulario':
        detalhes = resultado.get('detalhes', {})
        resumo = "\n".join([f"*{k}:* {v}" for k, v in detalhes.items()])
        msg = f"⚠️ *NOVA AUDITORIA DETECTADA!* ⚠️\n\n📄 *{resultado.get('formulario')}*\n\n{resumo}"
    else:
        msg = f"✅ *Monitoramento VIDIBR Iniciado*\n\n🆕 Primeiro: *{resultado.get('formulario')}*\n📋 Total: {resultado.get('total_formularios')}"

    endpoint = f"{URL}/message/sendText/{INSTANCE}"
    headers = {"apikey": KEY, "Content-Type": "application/json"}
    payload = {"number": GROUP, "text": msg}
    
    response = requests.post(endpoint, json=payload, headers=headers)
    response.raise_for_status()
    logger.info("Notificação enviada com sucesso!")

if __name__ == "__main__":
    path = os.environ.get("DADOS_ARQUIVO", "novo_formulario.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            enviar(json.load(f))
    else:
        logger.error(f"Arquivo {path} não encontrado.")
        sys.exit(1)
