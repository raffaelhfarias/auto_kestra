import logging
import csv
import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from workflow.components.navegador import Navegador
from workflow.pages.vd.login_page import LoginPage
from workflow.pages.vd.filtro_ranking_page import RankingVendasPage

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("ExtracaoVD")

# Configurações
load_dotenv()
EMAIL_GMAIL = os.environ.get("VD_GMAIL")
PASSWORD_GMAIL = os.environ.get("VD_PASS")

class ExtracaoVDOrquestrador:
    def __init__(self):
        self.navegador = Navegador()
        self.page = None

    def ler_ciclos_do_dia(self, path="extracoes/meta_dia.csv"):
        """Lê os ciclos do dia atual do arquivo meta_dia.csv."""
        ciclos = set()
        if not os.path.exists(path):
            logger.warning(f"Arquivo {path} não encontrado. Usando ciclo padrão [17].")
            return [17]

        hoje = datetime.now().strftime("%d/%m/%Y")
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    partes = [p.strip() for p in line.strip().split(";")]
                    if len(partes) == 4:
                        tipo, data_str, ciclo_str, _ = partes
                        if tipo.upper() in ("PEF", "EUD", "EUDORA") and data_str == hoje:
                            ciclos.add(int(ciclo_str))
        except Exception as e:
            logger.error(f"Erro ao ler ciclos: {e}")
        
        return sorted(ciclos) if ciclos else [17]

    def salvar_csv(self, dados, filename):
        os.makedirs("extracoes", exist_ok=True)
        filepath = os.path.join("extracoes", filename)
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["VD", "Valor Praticado"])
            writer.writerows(dados)
        logger.info(f"Dados salvos em {filepath}")

    async def executar(self):
        try:
            self.page = await self.navegador.setup_browser()
            
            login_page = LoginPage(self.page)
            ranking_page = RankingVendasPage(self.page)
            
            await login_page.login(EMAIL_GMAIL, PASSWORD_GMAIL)
            
            ciclos = self.ler_ciclos_do_dia()
            logger.info(f"Ciclos para processar: {ciclos}")

            for ciclo in ciclos:
                # Extração EUDORA
                logger.info(f"Iniciando EUDORA - Ciclo {ciclo}")
                await ranking_page.navegar_para_ranking()
                await ranking_page.configurar_datas_eudora()
                await ranking_page.selecionar_ciclo(ciclo)
                dados_eudora = await ranking_page.extrair_dados(codigo_produto="22960")
                self.salvar_csv(dados_eudora, f"resultado_eud_C{ciclo}.csv")

                # Extração PEF
                logger.info(f"Iniciando PEF - Ciclo {ciclo}")
                await ranking_page.navegar_para_ranking()
                await ranking_page.configurar_datas_pef()
                await ranking_page.selecionar_ciclo(ciclo)
                dados_pef = await ranking_page.extrair_dados(agrupamento_gerencia=True)
                self.salvar_csv(dados_pef, f"resultado_pef_C{ciclo}.csv")

            logger.info("Processo concluído com sucesso!")

        except Exception as e:
            logger.error(f"Falha na execução: {e}", exc_info=True)
        finally:
            await self.navegador.stop_browser()

if __name__ == "__main__":
    orquestrador = ExtracaoVDOrquestrador()
    asyncio.run(orquestrador.executar())
