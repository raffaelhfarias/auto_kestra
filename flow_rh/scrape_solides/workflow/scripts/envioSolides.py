import os
import sys
import base64
import requests
import json
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

# Configuração de logging simples para este script de envio
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_file(filename):
    """Busca um arquivo no diretório atual ou subdiretórios"""
    if os.path.exists(filename):
        return filename
    
    # Busca recursiva
    for path in Path(".").rglob(filename):
        if path.is_file():
            return str(path)
    return None

def enviar_whatsapp():
    parser = argparse.ArgumentParser(description="Script de envio de relatórios Solides via WhatsApp")
    parser.add_argument("--remoteJid", required=True, help="JID do destinatário")
    parser.add_argument("--filial", required=True, help="Nome da filial")
    parser.add_argument("--txt_path", default="resumo_banco_horas.txt", help="Caminho do arquivo de texto")
    parser.add_argument("--csv_path", default="resumo_banco_horas.csv", help="Caminho do arquivo CSV")
    
    args = parser.parse_args()

    # Log de depuração dos arquivos presentes
    logger.info(f"Arquivos no diretório atual: {os.listdir('.')}")

    # Carrega variáveis de ambiente
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
    load_dotenv(PROJECT_ROOT / ".env")

    api_url = os.environ.get("EVOLUTION_API_URL")
    api_key = os.environ.get("EVOLUTION_API_KEY")
    instance = os.environ.get("EVOLUTION_INSTANCE")

    if not all([api_url, api_key, instance]):
        logger.error("Configurações da Evolution API não encontradas no .env")
        sys.exit(1)

    headers = {
        "apikey": api_key,
        "Content-Type": "application/json"
    }

    # 1. Enviar Resumo em Texto
    target_txt = find_file(args.txt_path)
    if target_txt:
        logger.info(f"Lendo resumo de: {target_txt}")
        with open(target_txt, "r", encoding="utf-8") as f:
            texto_resumo = f.read()
        
        payload_text = {
            "number": args.remoteJid,
            "text": f"✅ *Relatório Gerado com Sucesso*\n\n{texto_resumo}"
        }
        
        try:
            res = requests.post(f"{api_url}/message/sendText/{instance}", headers=headers, json=payload_text)
            if res.status_code == 201 or res.status_code == 200:
                logger.info("Resumo em texto enviado com sucesso.")
            else:
                logger.error(f"Erro ao enviar texto: {res.text}")
        except Exception as e:
            logger.error(f"Falha na requisição de texto: {e}")
    else:
        logger.warning(f"Arquivo de resumo não encontrado: {args.txt_path}")

    # 2. Enviar Arquivo CSV
    target_csv = find_file(args.csv_path)
    if target_csv:
        logger.info(f"Lendo CSV de: {target_csv}")
        with open(target_csv, "rb") as f:
            base64_data = base64.b64encode(f.read()).decode("utf-8")
        
        # Gera um nome de arquivo amigável
        filename = f"banco_horas_{args.filial.replace(' ', '_').lower()}.csv"
        
        payload_media = {
            "number": args.remoteJid,
            "media": f"data:text/csv;base64,{base64_data}",
            "fileName": filename,
            "caption": "📄 Arquivo CSV para análise detalhada.",
            "mediatype": "document"
        }
        
        try:
            res = requests.post(f"{api_url}/message/sendMedia/{instance}", headers=headers, json=payload_media)
            if res.status_code == 201 or res.status_code == 200:
                logger.info("Arquivo CSV enviado com sucesso.")
            else:
                logger.error(f"Erro ao enviar CSV: {res.text}")
        except Exception as e:
            logger.error(f"Falha na requisição de mídia: {e}")
    else:
        logger.warning(f"Arquivo CSV não encontrado: {args.csv_path}")

if __name__ == "__main__":
    enviar_whatsapp()
