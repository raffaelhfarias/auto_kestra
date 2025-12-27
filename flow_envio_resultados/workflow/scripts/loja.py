import logging
import json
import os
import sys
import asyncio
from dotenv import load_dotenv
from workflow.components.navegador import Navegador
from workflow.pages.loja.login_page import LojaLoginPage
from workflow.pages.loja.filtro_consulta_page import ConsultaGerencialPage

# Configuração de Logging para o stderr (não interfere no stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("ExtracaoLoja")

# Configurações
load_dotenv()
USERNAME = os.environ.get("LOJA_USER")
PASSWORD = os.environ.get("LOJA_PASS")

class ExtracaoLojaOrquestrador:
    def __init__(self):
        self.navegador = Navegador()
        self.page = None

    async def executar(self):
        try:
            logger.info("--- Iniciando Orquestração de Extração LOJA ---")
            self.page = await self.navegador.setup_browser()
            
            login_page = LojaLoginPage(self.page)
            consulta_page = ConsultaGerencialPage(self.page)
            
            await login_page.login(USERNAME, PASSWORD)
            await consulta_page.navegar_para_consulta()
            dados = await consulta_page.extrair_dados()
            
            # Formata os dados
            resultados_finais = []
            for item in dados:
                resultados_finais.append({
                    "loja": item[0],
                    "gmv": item[1]
                })

            # SALVAMENTO COMPATÍVEL COM KESTRA OUTPUTS
            output_filename = "resultado_loja.json"
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(resultados_finais, f, ensure_ascii=False, indent=4)
            
            # Print nativo Kestra (opcional)
            print(f"::{json.dumps({'outputs': {'resultado': resultados_finais}})}::")
            
            logger.info(f"Sucesso! {len(resultados_finais)} lojas salvas em {output_filename}")

        except Exception as e:
            logger.error(f"FALHA CRÍTICA: {e}", exc_info=True)
            if self.page:
                try:
                    await self.page.screenshot(path="erro_extracao.png")
                    logger.info("Screenshot de erro salva: erro_extracao.png")
                except:
                    logger.warning("Não foi possível tirar screenshot do erro.")
            sys.exit(1)
        finally:
            await self.navegador.stop_browser()
            logger.info("--- Finalizando Orquestração ---")

if __name__ == "__main__":
    orquestrador = ExtracaoLojaOrquestrador()
    asyncio.run(orquestrador.executar())
