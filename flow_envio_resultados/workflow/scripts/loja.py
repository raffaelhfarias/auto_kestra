import logging
import csv
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

    def salvar_csv(self, dados, filename="resultado_loja.csv"):
        os.makedirs("extracoes", exist_ok=True)
        filepath = os.path.join("extracoes", filename)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Loja", "GMV"])
            writer.writerows(dados)
        logger.info(f"Dados salvos em {filepath}")

    async def executar(self):
        try:
            self.page = await self.navegador.setup_browser()
            
            login_page = LojaLoginPage(self.page)
            consulta_page = ConsultaGerencialPage(self.page)
            
            await login_page.login(USERNAME, PASSWORD)
            await consulta_page.navegar_para_consulta()
            dados = await consulta_page.extrair_dados()
            
            self.salvar_csv(dados)
            logger.info("Processo Loja concluído com sucesso!")

        except Exception as e:
            logger.error(f"Falha na execução Loja: {e}", exc_info=True)
        finally:
            await self.navegador.stop_browser()

if __name__ == "__main__":
    orquestrador = ExtracaoLojaOrquestrador()
    asyncio.run(orquestrador.executar())
