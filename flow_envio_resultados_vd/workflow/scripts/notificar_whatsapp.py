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

# Carrega metas do ambiente
# Formato esperado: {"VD_202602":150000,"EUD_202602":50000,"VD_202603":5000}
METAS_JSON_RAW = os.environ.get("VD_METAS_JSON", "{}")
try:
    METAS = json.loads(METAS_JSON_RAW)
    logger.info(f"Metas carregadas: {METAS}")
except json.JSONDecodeError as e:
    logger.warning(f"Erro ao parsear VD_METAS_JSON: {e}. Usando metas vazias.")
    METAS = {}

# Configurações da Evolution API
EVOLUTION_API_URL = os.environ.get("EVOLUTION_API_URL")
EVOLUTION_API_KEY = os.environ.get("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE = os.environ.get("EVOLUTION_INSTANCE")
WHATSAPP_GROUP_VD = os.environ.get("WHATSAPP_GROUP_VD")


def listar_arquivos_extracao():
    """Encontra todos os CSVs de extração no diretório 'extracoes/' ou raiz."""
    padroes = ["extracoes/resultado_filtros_*.csv", "resultado_filtros_*.csv"]
    arquivos = []
    for p in padroes:
        arquivos.extend(glob.glob(p))
    return list(set(arquivos))


def formatar_valor(valor):
    """Formata valor float para o padrão brasileiro: R$ 1.234,56"""
    try:
        val_float = float(valor)
    except:
        val_float = 0.0
    
    # Formata com separadores brasileiros
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


def extrair_numero_ciclo(ciclo_completo):
    """Extrai número do ciclo de '202602' -> '2'"""
    # Pega os últimos 2 dígitos e remove zero à esquerda
    if len(ciclo_completo) >= 2:
        return str(int(ciclo_completo[-2:]))  # "02" -> "2"
    return ciclo_completo


def mapear_tipo_exibicao(tipo):
    """Mapeia tipo interno para nome de exibição: VD -> PEF"""
    mapeamento = {
        "VD": "PEF",
        "EUD": "EUD"
    }
    return mapeamento.get(tipo, tipo)


def processar_arquivo(caminho_arquivo):
    """Lê um CSV e retorna dados formatados."""
    logger.info(f"Processando arquivo: {caminho_arquivo}")
    
    tipo, ciclo = extrair_metadados_arquivo(caminho_arquivo)
    tipo_exibicao = mapear_tipo_exibicao(tipo)
    numero_ciclo = extrair_numero_ciclo(ciclo)
    
    dados_lojas = []
    total_realizado = 0.0
    
    try:
        with open(caminho_arquivo, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                gerencia = row.get("Gerencia", "N/A").strip()
                valor_str = row.get("Valor Praticado", "0").strip()
                
                # Valor já vem como decimal (ex: 1220.08)
                try:
                    valor_float = float(valor_str)
                except:
                    valor_float = 0.0
                
                if gerencia and valor_float > 0:
                    total_realizado += valor_float
                    dados_lojas.append({"loja": gerencia, "valor": valor_float})
                    
    except Exception as e:
        logger.error(f"Erro ao ler arquivo {caminho_arquivo}: {e}")
        return None

    if not dados_lojas:
        logger.warning(f"Arquivo vazio ou sem dados válidos: {caminho_arquivo}")
        return None

    # Busca a meta correspondente (chave: TIPO_CICLO, ex: VD_202602)
    chave_meta = f"{tipo}_{ciclo}"
    meta_valor = METAS.get(chave_meta)
    
    diferenca = None
    if meta_valor and meta_valor > 0:
        diferenca = total_realizado - meta_valor
        logger.info(f"Meta encontrada para {chave_meta}: {meta_valor} | Diferença: {diferenca:.2f}")
    else:
        logger.info(f"Nenhuma meta configurada para {chave_meta}")

    return {
        "tipo": tipo,
        "tipo_exibicao": tipo_exibicao,
        "ciclo": ciclo,
        "numero_ciclo": numero_ciclo,
        "lojas": dados_lojas,
        "total": total_realizado,
        "meta": meta_valor,
        "diferenca": diferenca
    }


def montar_bloco_mensagem(dados):
    """Monta bloco de mensagem para um tipo (PEF ou EUD), incluindo meta e atingimento."""
    linhas = [f"➡️ *Parcial Receita {dados['tipo_exibicao']} - Ciclo {dados['numero_ciclo']}*", ""]
    
    for item in dados["lojas"]:
        linhas.append(f" {item['loja']}: {formatar_valor(item['valor'])}")
    
    linhas.append("")
    linhas.append(f"💰 *Realizado*: {formatar_valor(dados['total'])}")
    
    # Adiciona meta e diferença se disponíveis
    if dados.get("meta"):
        linhas.append(f"🎯 *Meta*: {formatar_valor(dados['meta'])}")
    
    if dados.get("diferenca") is not None:
        dif = dados["diferenca"]
        if dif >= 0:
            linhas.append(f"🟢 *Ultrapassou*: {formatar_valor(dif)}")
        else:
            linhas.append(f"🔴 *Faltante*: {formatar_valor(dif)}")
    
    return "\n".join(linhas)


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
    logger.info("--- Iniciando Processador de Notificações ---")
    
    arquivos = listar_arquivos_extracao()
    
    if not arquivos:
        logger.warning("Nenhum arquivo CSV encontrado em 'extracoes/' ou raiz!")
        sys.exit(0)
    
    logger.info(f"Encontrados {len(arquivos)} arquivos para processar: {arquivos}")
    
    # Processa todos os arquivos
    todos_dados = []
    for arq in arquivos:
        dados = processar_arquivo(arq)
        if dados:
            todos_dados.append(dados)
    
    if not todos_dados:
        logger.warning("Nenhum dado válido encontrado nos arquivos!")
        sys.exit(0)
    
    # Agrupa dados por número do ciclo
    dados_por_ciclo = {}
    for item in todos_dados:
        ciclo = item["numero_ciclo"]
        if ciclo not in dados_por_ciclo:
            dados_por_ciclo[ciclo] = []
        dados_por_ciclo[ciclo].append(item)
    
    # Ordena ciclos para envio sequencial
    ciclos_ordenados = sorted(dados_por_ciclo.keys())
    
    separador = "\n\n────────────────────\n\n"
    ordem_tipos = {"VD": 1, "EUD": 2}

    logger.info(f"Ciclos identificados para envio: {ciclos_ordenados}")

    # Envia uma mensagem por ciclo
    for ciclo in ciclos_ordenados:
        itens_ciclo = dados_por_ciclo[ciclo]
        
        # Ordena dentro do ciclo: PEF (VD) primeiro, depois EUD
        itens_ciclo.sort(key=lambda x: ordem_tipos.get(x["tipo"], 99))
        
        blocos = []
        for dados in itens_ciclo:
            bloco = montar_bloco_mensagem(dados)
            blocos.append(bloco)
            
        mensagem_ciclo = separador.join(blocos)
        
        logger.info(f"--- Enviando mensagem consolidada do Ciclo {ciclo} ---")
        enviar_para_whatsapp(mensagem_ciclo)
    
    logger.info("--- Fim do Processamento ---")
