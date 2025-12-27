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

            # Imprime APENAS o JSON no stdout
            sys.stdout.write(json.dumps(resultados_finais, ensure_ascii=False))
            sys.stdout.flush()

        except Exception as e:
            logger.error(f"Falha na execução Loja: {e}", exc_info=True)
            sys.exit(1)
        finally:
            await self.navegador.stop_browser()

if __name__ == "__main__":
    orquestrador = ExtracaoLojaOrquestrador()
    asyncio.run(orquestrador.executar())
