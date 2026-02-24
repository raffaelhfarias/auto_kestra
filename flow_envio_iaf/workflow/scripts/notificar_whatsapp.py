import os
import sys
import logging
import requests
from dotenv import load_dotenv

# Reconfigura stdout para UTF-8 (Windows/PowerShell)
sys.stdout.reconfigure(encoding='utf-8')

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("NotificarWhatsApp")

load_dotenv()

# Configurações da Evolution API
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE")
WHATSAPP_ID_EDGAR = os.environ.get("WHATSAPP_ID_EDGAR")
WHATSAPP_ID_PRISCILA = os.environ.get("WHATSAPP_ID_PRISCILA")


def carregar_mensagem(caminho: str = "mensagem_whatsapp.txt") -> str:
    """Carrega o conteúdo da mensagem já formatada pelo formatador_whatsapp.py."""
    if not os.path.exists(caminho):
        logger.error(f"Arquivo de mensagem não encontrado: {caminho}")
        return ""
    
    with open(caminho, "r", encoding="utf-8") as f:
        conteudo = f.read().strip()
    
    logger.info(f"Mensagem carregada ({len(conteudo)} caracteres) de '{caminho}'")
    return conteudo


def enviar_para_whatsapp(mensagem: str, destinatario: str):
    """Envia mensagem de texto via Evolution API."""
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        logger.warning("Credenciais Evolution API não configuradas. Apenas logando mensagem.")
        logger.info(f"\n{mensagem}")
        return False

    if not destinatario:
        logger.error("Destinatário não configurado.")
        return False

    url = f"{EVOLUTION_API_URL}message/sendText/{EVOLUTION_INSTANCE}"

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }

    payload = {
        "number": destinatario,
        "text": mensagem,
        "delay": 2000,
        "linkPreview": False
    }

    try:
        logger.info(f"Enviando mensagem para {destinatario}...")
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Sucesso! Status: {response.status_code}")
        return True
    except requests.exceptions.HTTPError as e:
        logger.error(f"Erro HTTP ao enviar WhatsApp: {e} | Response: {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"Erro ao enviar WhatsApp: {e}")
        return False


if __name__ == "__main__":
    logger.info("--- Iniciando Notificação IAF via WhatsApp ---")

    mensagem = carregar_mensagem()

    if not mensagem:
        logger.error("Mensagem vazia ou arquivo não encontrado. Abortando envio.")
        sys.exit(1)

    logger.info(f"Prévia da mensagem:\n{mensagem}")

    destinatarios = [
        ("Edgar", WHATSAPP_ID_EDGAR),
        ("Priscila", WHATSAPP_ID_PRISCILA)
    ]

    sucessos = 0
    for nome, numero in destinatarios:
        if numero:
            logger.info(f"Iniciando envio para {nome}...")
            if enviar_para_whatsapp(mensagem, numero):
                sucessos += 1
        else:
            logger.warning(f"Número não configurado para {nome}.")

    if sucessos > 0:
        logger.info("--- Notificações enviadas com sucesso! ---")
    else:
        logger.error("--- Falha no envio das notificações ---")
        sys.exit(1)

    logger.info("--- Fim do Processamento ---")
