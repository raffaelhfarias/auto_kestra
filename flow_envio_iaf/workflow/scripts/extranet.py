import asyncio
import os
import sys
import logging
import json
import uuid
import time
from dotenv import load_dotenv

# Adiciona o diretório raiz do projeto ao sys.path para importações da pasta workflow funcionarem perfeitamente
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from workflow.components.navegador import Navegador
from workflow.pages.base_page import BasePage

# Reconfigura a saída padrão (stdout) para utf-8, resolvendo problemas de acentuação no Windows/Powershell
sys.stdout.reconfigure(encoding='utf-8')

# Configuração básica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def main():
    start_time = time.time()
    
    # Inicializando o Wide Event com informações do contexto
    wide_event = {
        "event_id": str(uuid.uuid4()),
        "script": "extranet.py",
        "action": "login_iaf_consolidated",
        "status": "started",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    load_dotenv()
    usuario = os.environ.get("EXTRANET_USER")
    senha = os.environ.get("EXTRANET_PASS")

    if not usuario or not senha:
        wide_event["status"] = "error"
        wide_event["error"] = "Credenciais não encontradas no arquivo .env"
        wide_event["duration_ms"] = int((time.time() - start_time) * 1000)
        logger.info(f"Wide Event: {json.dumps(wide_event)}")
        return

    navegador = Navegador()
    try:
        page = await navegador.setup_browser()
        base_page = BasePage(page)
        
        login_start = time.time()
        await base_page.realizar_login(usuario, senha)
        wide_event["login_duration_ms"] = int((time.time() - login_start) * 1000)

        # Extrair dados da página IAF
        extracao_start = time.time()
        logger.info("Iniciando extração de dados da página IAF...")
        
        from workflow.pages.iaf_page import IAFPage
        iaf_page = IAFPage(page)
        dados_iaf = await iaf_page.extrair_tudo()
        
        md_content = iaf_page.gerar_markdown(dados_iaf)
        
        # Salva o arquivo markdown localmente para ser engolido via RAG
        md_filename = "resumo_iaf.md"
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(md_content)
            
        # Formata e salva a mensagem pro Whatsapp
        from workflow.scripts.formatador_whatsapp import FormatadorWhatsapp
        msg_whatsapp = FormatadorWhatsapp.formatar(dados_iaf)
        zap_filename = "mensagem_whatsapp.txt"
        with open(zap_filename, "w", encoding="utf-8") as f:
            f.write(msg_whatsapp)
        
        wide_event["extraction_duration_ms"] = int((time.time() - extracao_start) * 1000)
        wide_event["extraction_status"] = "success"
        wide_event["saved_files"] = [md_filename, zap_filename]
        
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
        
        # Emite o Wide Event ao final do processamento, unindo todo o contexto num log só
        logger.info(f"Wide Event Consolidado:\n{json.dumps(wide_event, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    asyncio.run(main())
