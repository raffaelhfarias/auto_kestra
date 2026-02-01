import os
import sys
import json
import csv
import glob
import logging
import requests
from dotenv import load_dotenv

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("NotificarWhatsApp")

load_dotenv()

# Configurações da Evolution API
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE")
WHATSAPP_GROUP_VD = os.environ.get("WHATSAPP_GROUP_VD")

# Metas Específicas por Ciclo (JSON)
# Exemplo env: VD_METAS_JSON='{"VD_202602": 150000, "EUD_202602": 50000}'
VD_METAS_JSON_STR = os.environ.get("VD_METAS_JSON", "{}")
try:
    VD_METAS_DICT = json.loads(VD_METAS_JSON_STR)
except Exception as e:
    logger.warning(f"Erro ao fazer parse de VD_METAS_JSON: {e}. Nenhuma meta será aplicada.")
    VD_METAS_DICT = {}

def get_meta(tipo, ciclo):
    """Retorna a meta específica buscando pela chave 'TIPO_CICLO' (ex: VD_202602)."""
    chave = f"{tipo}_{ciclo}"
    
    # Busca exata: VD_202602
    meta = VD_METAS_DICT.get(chave)
    
    if meta is not None:
        logger.info(f"Meta encontrada para {chave}: {meta}")
        return float(meta)
    
    logger.info(f"Nenhuma meta definida para {chave}.")
    return 0.0

def listar_arquivos_extracao():
    """Encontra todos os CSVs de extração no diretório 'extracoes/' ou raiz."""
    # Tenta padrão na pasta extracoes ou raiz
    padroes = ["extracoes/resultado_filtros_*.csv", "resultado_filtros_*.csv"]
    arquivos = []
    for p in padroes:
        arquivos.extend(glob.glob(p))
    return list(set(arquivos)) # Remove duplicatas

def formatar_valor(valor):
    """Formata valor para o padrão brasileiro: R$ 1.234,56"""
    try:
        val_float = float(str(valor).replace("R$", "").replace(".", "").replace(",", ".").strip())
    except:
        val_float = 0.0
        
    v = f"{val_float:,.2f}"
    return f"R$ {v.replace(',', 'X').replace('.', ',').replace('X', '.')}"

def extrair_metadados_arquivo(filename):
    """Extrai Tipo e Ciclo do nome do arquivo (ex: resultado_filtros_VD_202602.csv)."""
    base = os.path.basename(filename).replace(".csv", "")
    partes = base.split("_")
    # Esperado: ['resultado', 'filtros', 'TIPO', 'CICLO']
    if len(partes) >= 4:
        tipo = partes[2]
        ciclo = partes[3]
        return tipo, ciclo
    return "DESCONHECIDO", "N/A"

def processar_arquivo_e_enviar(caminho_arquivo):
    """Lê um CSV, formata a mensagem e envia."""
    logger.info(f"Processando arquivo: {caminho_arquivo}")
    
    tipo, ciclo = extrair_metadados_arquivo(caminho_arquivo)
    
    dados_lojas = []
    total_realizado = 0.0
    
    try:
        with open(caminho_arquivo, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                gerencia = row.get("Gerencia", "N/A")
                valor_str = row.get("Valor Praticado", "0")
                
                # Limpeza básica do valor para soma
                try:
                    valor_float = float(valor_str.replace("R$", "").replace(".", "").replace(",", ".").strip())
                except:
                    valor_float = 0.0
                
                total_realizado += valor_float
                dados_lojas.append({"loja": gerencia, "valor": valor_float})
                
    except Exception as e:
        logger.error(f"Erro ao ler arquivo {caminho_arquivo}: {e}")
        return

    # Se não houver dados, pula
    if not dados_lojas:
        logger.warning(f"Arquivo vazio ou sem dados válidos: {caminho_arquivo}")
        return

    # Monta Mensagem
    msg = [f"➡️ *Parcial Receita {tipo} - Ciclo {ciclo}*", ""]
    
    for item in dados_lojas:
        msg.append(f" {item['loja']}: {formatar_valor(item['valor'])}")
    
    msg.append("")
    
    # Busca meta dinâmica (VD ou EUD)
    META_ATUAL = get_meta(tipo, ciclo)
    
    if META_ATUAL > 0:
        logger.info(f"Calculando meta para {tipo} (Ciclo {ciclo})...")
        diff = total_realizado - META_ATUAL
        msg.append(f"🎯 *Meta*: {formatar_valor(META_ATUAL)}")
        msg.append(f"💰 *Realizado*: {formatar_valor(total_realizado)}")
        
        if diff < 0:
            msg.append(f"🔴 *Faltante*: {formatar_valor(abs(diff))}")
        else:
            msg.append(f"🎉 *Superavit*: {formatar_valor(diff)}")
    else:
         msg.append(f"💰 *Total*: {formatar_valor(total_realizado)}")

    texto_final = "\n".join(msg)
    
    # Envia
    enviar_para_whatsapp(texto_final)

def enviar_para_whatsapp(mensagem):
    if not EVOLUTION_API_URL or not EVOLUTION_API_KEY:
        logger.warning("Credenciais Evolution API não configuradas. Apenas logando mensagem.")
        logger.info(mensagem)
        return

    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY
    }
    
    payload = {
        "number": WHATSAPP_GROUP_VD,
        "text": mensagem,
        "delay": 2000,
        "linkPreview": False
    }
    
    try:
        logger.info(f"Enviando mensagem para {WHATSAPP_GROUP_VD}...")
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Sucesso! Status: {response.status_code}")
    except Exception as e:
        logger.error(f"Erro ao enviar WhatsApp: {e}")

if __name__ == "__main__":
    logger.info("--- Iniciando Processador de Notificações (Multi-Ciclo) ---")
    
    arquivos = listar_arquivos_extracao()
    
    if not arquivos:
        logger.warning("Nenhum arquivo CSV encontrado em 'extracoes/' ou raiz!")
    else:
        logger.info(f"Encontrados {len(arquivos)} arquivos para processar: {arquivos}")
        
        # Ordena para enviar em ordem lógica (ex: VD antes de EUD, ou por ciclo)
        arquivos.sort() 
        
        for arq in arquivos:
            processar_arquivo_e_enviar(arq)
            
    logger.info("--- Fim do Processamento ---")
