import os
import sys
import json
import requests
import logging
from dotenv import load_dotenv

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("NotificarWhatsApp")

load_dotenv()

# Configurações da Evolution API vindas do env (Kestra KV Store)
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE")
WHATSAPP_GROUP_VD = os.environ.get("WHATSAPP_GROUP_VD")
VD_META = float(os.environ.get("VD_META", 0.0)) # 0.0 indica que não há meta definida

def formatar_valor(valor):
    """Formata valor para o padrão brasileiro: R$ 1.234,56"""
    # Formata com separador de milhar e decimal
    v = f"{valor:,.2f}"
    # Troca , por X, . por , e X por .
    return f"R$ {v.replace(',', 'X').replace('.', ',').replace('X', '.')}"

def formatar_mensagem(dados):
    """Cria uma mensagem elegante seguindo o template do usuário."""
    logger.info(f"Iniciando formatação da mensagem para {len(dados)} registros...")
    msg = ["➡️ *Parcial Receita VD*", ""]
    
    realizado = 0
    for item in dados:
        loja = item.get("loja", "N/A")
        gmv = item.get("gmv", 0)
        realizado += gmv
        msg.append(f" {loja}: {formatar_valor(gmv)}")
    
    msg.append("")
    
    if VD_META > 0:
        logger.info(f"Meta detectada: R$ {VD_META:,.2f}. Calculando indicadores...")
        msg.append(f"🎯 *Meta*: {formatar_valor(VD_META)}")
        msg.append(f"💰 *Realizado*: {formatar_valor(realizado)}")
        
        diferenca = realizado - VD_META
        
        if diferenca < 0:
            msg.append(f"🔴 *Faltante*: {formatar_valor(diferenca)}")
            logger.info(f"Status: Faltante de R$ {abs(diferenca):,.2f}")
        else:
            msg.append(f"🎉 *Ultrapassou*: {formatar_valor(diferenca)}")
            logger.info("Status: Meta batida/ultrapassada!")
    else:
        logger.info("Nenhuma meta definida (VD_META=0). Exibindo apenas realizado.")
        msg.append(f"💰 *Realizado*: {formatar_valor(realizado)}")
    
    return "\n".join(msg)

def enviar_whatsapp(dados_loja):
    logger.info(f"Preparando envio para Evolution API (Instância: {EVOLUTION_INSTANCE})...")
    
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        logger.error("ERRO: Credenciais da Evolution API (URL ou API_KEY) ausentes no ambiente.")
        return

    texto_formatado = formatar_mensagem(dados_loja)
    
    # Endpoint da Evolution API para envio de texto
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    logger.info(f"Destino da mensagem: {WHATSAPP_GROUP_VD}")
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    payload = {
        "number": WHATSAPP_GROUP_VD,
        "text": texto_formatado,
        "delay": 1200,
        "linkPreview": False
    }

    try:
        logger.info("Enviando requisição POST para Evolution API...")
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"NOTIFICAÇÃO ENVIADA! Status Code: {response.status_code}")
        return response.json()
    except Exception as e:
        logger.error(f"FALHA NO ENVIO: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Resposta bruta da API: {e.response.text}")
        raise e

if __name__ == "__main__":
    logger.info("--- Iniciando Script de Notificação WhatsApp (VD) ---")
    path_arquivo = os.environ.get("DADOS_ARQUIVO")
    
    if path_arquivo and os.path.exists(path_arquivo):
        try:
            logger.info(f"Lendo dados do arquivo: {path_arquivo}")
            with open(path_arquivo, "r", encoding="utf-8") as f:
                dados = json.load(f)
            enviar_whatsapp(dados)
        except Exception as e:
            logger.error(f"Erro ao processar arquivo JSON: {e}", exc_info=True)
            sys.exit(1)
    else:
        logger.error(f"Arquivo de entrada não encontrado ou vazio: {path_arquivo}")
        sys.exit(1)
    
    logger.info("--- Notificação Finalizada ---")
