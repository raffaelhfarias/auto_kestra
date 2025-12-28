import logging
import json
import os
import sys
import asyncio
from dotenv import load_dotenv
from workflow.components.navegador import Navegador
from workflow.pages.vidibr.login_page import VidibrLoginPage
from workflow.pages.vidibr.auditoria_page import VidibrAuditoriaPage

# Log para stderr para não sujar stdout do Kestra
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("ProcessarAuditoria")

load_dotenv()
USERNAME = os.environ.get("VIDIBR_USER")
PASSWORD = os.environ.get("VIDIBR_PASS")
LAST_FORM_FILE = "ultimo_formulario.txt"

class AuditoriaOrquestrador:
    def __init__(self):
        self.navegador = Navegador()
        self.page = None

    async def executar(self):
        try:
            logger.info("--- Iniciando Orquestração Auditoria VIDIBR ---")
            self.page = await self.navegador.setup_browser()
            
            login = VidibrLoginPage(self.page)
            auditoria = VidibrAuditoriaPage(self.page)
            
            await login.login(USERNAME, PASSWORD)
            await auditoria.abrir_selecao_jobs()
            formularios = await auditoria.listar_formularios()
            
            if not formularios:
                logger.warning("Nenhum formulário listado.")
                return

            ultimo_visto = None
            if os.path.exists(LAST_FORM_FILE):
                with open(LAST_FORM_FILE, "r", encoding="utf-8") as f:
                    ultimo_visto = f.read().strip() or None

            formulario_atual = formularios[0]
            resultado = {"total_formularios": len(formularios)}

            if ultimo_visto is None:
                logger.info(f"Primeiro registro: {formulario_atual}")
                with open(LAST_FORM_FILE, "w", encoding="utf-8") as f: f.write(formulario_atual)
                resultado.update({"status": "primeiro_registro", "formulario": formulario_atual})
            elif formulario_atual != ultimo_visto:
                logger.info(f"Nova auditoria detectada: {formulario_atual}")
                await auditoria.selecionar_formulario_e_entrar(formulario_atual)
                detalhes = await auditoria.extrair_detalhes()
                with open(LAST_FORM_FILE, "w", encoding="utf-8") as f: f.write(formulario_atual)
                resultado.update({
                    "status": "novo_formulario",
                    "formulario": formulario_atual,
                    "detalhes": detalhes
                })
            else:
                logger.info("Nada novo.")
                resultado.update({"status": "sem_novidades", "formulario_atual": formulario_atual})

            with open("novo_formulario.json", "w", encoding="utf-8") as f:
                json.dump(resultado, f, ensure_ascii=False, indent=4)
            
            # Output para o Kestra
            print(f"::{json.dumps({'outputs': {'resultado': resultado}})}::")

        except Exception as e:
            logger.error(f"Erro Crítico: {e}", exc_info=True)
            sys.exit(1)
        finally:
            await self.navegador.stop_browser()

if __name__ == "__main__":
    asyncio.run(AuditoriaOrquestrador().executar())
