"""
Script de verificação de atualização do dashboard IAF.

Responsável por:
1. Realizar login na Extranet
2. Navegar até a página IAF Consolidated
3. Verificar se a "Data de atualização" corresponde à data de hoje
4. Retornar exit code 0 se atualizado, 1 se não atualizado

Será usado em janela de verificação (polling) antes de disparar
o fluxo completo de extração + envio.
"""

import asyncio
import os
import sys
import logging
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# Adiciona o diretório raiz do projeto ao sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from workflow.components.navegador import Navegador
from workflow.pages.base_page import BasePage

# Reconfigura stdout para UTF-8 (Windows/PowerShell)
sys.stdout.reconfigure(encoding='utf-8')

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def extrair_data_atualizacao(page) -> str:
    """Extrai a data de atualização exibida no dashboard IAF."""
    try:
        # Aguarda o elemento de data de atualização aparecer
        seletor = "span.sc-dlWCHZ"
        await page.wait_for_selector(seletor, timeout=15000)
        
        elemento = page.locator(seletor).first
        texto = await elemento.inner_text()
        
        logger.info(f"Texto de atualização encontrado: '{texto}'")
        return texto.strip()
    except Exception as e:
        logger.error(f"Erro ao extrair data de atualização: {e}")
        return ""


def verificar_data_hoje(texto_data: str) -> bool:
    """
    Verifica se a data extraída corresponde à data de hoje.
    
    Formato esperado: "23/02/2026, às 09:56:06"
    Compara apenas a parte da data (dd/mm/yyyy) com a data atual.
    """
    if not texto_data:
        logger.warning("Texto de data vazio, não é possível verificar.")
        return False
    
    hoje = datetime.now().strftime("%d/%m/%Y")
    
    # Extrai apenas a parte da data (antes da vírgula)
    data_extraida = texto_data.split(",")[0].strip()
    
    logger.info(f"Data de hoje: {hoje}")
    logger.info(f"Data extraída do dashboard: {data_extraida}")
    
    atualizado = (data_extraida == hoje)
    
    if atualizado:
        logger.info("✅ Dashboard IAF foi atualizado hoje!")
    else:
        logger.info(f"⏳ Dashboard IAF NÃO foi atualizado hoje (última atualização: {data_extraida})")
    
    return atualizado


async def main():
    start_time = time.time()
    
    wide_event = {
        "script": "verificar_atualizacao_iaf.py",
        "action": "check_update",
        "status": "started",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    load_dotenv()
    usuario = os.environ.get("EXTRANET_USER")
    senha = os.environ.get("EXTRANET_PASS")

    if not usuario or not senha:
        wide_event["status"] = "error"
        wide_event["error"] = "Credenciais não encontradas no arquivo .env"
        logger.error(json.dumps(wide_event, indent=2, ensure_ascii=False))
        sys.exit(1)

    navegador = Navegador()
    atualizado = False
    
    try:
        page = await navegador.setup_browser()
        base_page = BasePage(page)
        
        # Login e navegação
        login_start = time.time()
        await base_page.realizar_login(usuario, senha)
        wide_event["login_duration_ms"] = int((time.time() - login_start) * 1000)

        # Aguarda a página carregar completamente
        await page.wait_for_timeout(3000)
        
        # Extrai a data de atualização
        texto_data = await extrair_data_atualizacao(page)
        wide_event["data_atualizacao_raw"] = texto_data
        
        # Verifica se é de hoje
        atualizado = verificar_data_hoje(texto_data)
        wide_event["atualizado_hoje"] = atualizado
        wide_event["status"] = "success"
        
    except Exception as e:
        wide_event["status"] = "error"
        wide_event["error"] = {
            "type": type(e).__name__,
            "message": str(e)
        }
    finally:
        await navegador.stop_browser()
        wide_event["duration_ms"] = int((time.time() - start_time) * 1000)
        
        logger.info(f"Wide Event Consolidado:\n{json.dumps(wide_event, indent=2, ensure_ascii=False)}")

    # Exit code para uso em orquestração (Kestra, shell script, etc.)
    # 0 = atualizado (pode prosseguir), 1 = não atualizado (aguardar)
    if atualizado:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
