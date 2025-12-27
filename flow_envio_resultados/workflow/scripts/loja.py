import logging
import json
import os
import asyncio
from dotenv import load_dotenv
from workflow.components.navegador import Navegador
from workflow.pages.loja.login_page import LojaLoginPage
from workflow.pages.loja.filtro_consulta_page import ConsultaGerencialPage

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
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
            
            # Formata os dados para uma lista de dicionários (mais fácil no Kestra/Evolution)
            resultados_finais = []
            for item in dados:
                resultados_finais.append({
                    "loja": item[0],
                    "gmv": item[1]
                })

            # Exibe o JSON para o Kestra capturar
            # O Kestra captura tudo que for impresso no formato ::{ "key": "value" }::
            print(f"::{{ \"outputs\": {json.dumps(resultados_finais)} }}::")
            
            logger.info(f"Processo Loja concluído! {len(resultados_finais)} lojas extraídas.")

        except Exception as e:
            logger.error(f"Falha na execução Loja: {e}", exc_info=True)
        finally:
            await self.navegador.stop_browser()

if __name__ == "__main__":
    orquestrador = ExtracaoLojaOrquestrador()
    asyncio.run(orquestrador.executar())
