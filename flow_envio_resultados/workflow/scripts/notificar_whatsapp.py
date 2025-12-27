import os
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
WHATSAPP_GROUP_LOJA = os.environ.get("WHATSAPP_GROUP_LOJA")
LOJA_META = float(os.environ.get("LOJA_META", 0.0)) # 0.0 indica que não há meta definida

def formatar_valor(valor):
    """Formata valor para o padrão brasileiro: R$ 1.234,56"""
    # Formata com separador de milhar e decimal
    v = f"{valor:,.2f}"
    # Troca , por X, . por , e X por .
    return f"R$ {v.replace(',', 'X').replace('.', ',').replace('X', '.')}"

def formatar_mensagem(dados):
    """Cria uma mensagem elegante seguindo o template do usuário."""
    msg = ["➡️ *Parcial Receita LOJA*", ""]
    
    realizado = 0
    for item in dados:
        loja = item.get("loja", "N/A")
        gmv = item.get("gmv", 0)
        realizado += gmv
        msg.append(f" {loja}: {formatar_valor(gmv)}")
    
    msg.append("")
    
    if LOJA_META > 0:
        msg.append(f"🎯 *Meta*: {formatar_valor(LOJA_META)}")
        msg.append(f"💰 *Realizado*: {formatar_valor(realizado)}")
        
        diferenca = realizado - LOJA_META
        
        if diferenca < 0:
            # Quando o meta ainda não foi batido (negativo)
            msg.append(f"🔴 *Faltante*: {formatar_valor(diferenca)}")
        else:
            # Quando o meta foi ultrapassado
            msg.append(f"🎉 *Ultrapassou*: {formatar_valor(diferenca)}")
    else:
        # Caso não exista meta, exibe apenas o realizado
        msg.append(f"💰 *Realizado*: {formatar_valor(realizado)}")
    
    return "\n".join(msg)

def enviar_whatsapp(dados_loja):
    if not EVOLUTION_URL or not EVOLUTION_API_KEY:
        logger.error("Credenciais da Evolution API não encontradas!")
        return

    texto_formatado = formatar_mensagem(dados_loja)
    
    # Endpoint da Evolution API para envio de texto
    url = f"{EVOLUTION_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    payload = {
        "number": WHATSAPP_DESTINO,
        "text": texto_formatado,
        "delay": 1200,
        "linkPreview": False
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info("Mensagem enviada com sucesso para o WhatsApp!")
        return response.json()
    except Exception as e:
        logger.error(f"Erro ao enviar para Evolution API: {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Resposta da API: {e.response.text}")
        raise e

if __name__ == "__main__":
    # O Kestra passará o JSON via argumento ou variável de ambiente
    # Vamos pegar da variável de ambiente que passaremos no YAML
    dados_raw = os.environ.get("DADOS_LOJA")
    
    if dados_raw:
        try:
            # O Kestra às vezes passa strings JSON com escape
            dados = json.loads(dados_raw)
            enviar_whatsapp(dados)
        except Exception as e:
            logger.error(f"Erro ao processar dados para envio: {e}")
    else:
        logger.error("Nenhum dado de loja encontrado na variável DADOS_LOJA")
