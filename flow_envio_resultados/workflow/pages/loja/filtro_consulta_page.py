import logging
from playwright.async_api import Page
from ..base_page import BasePage

logger = logging.getLogger(__name__)

class ConsultaGerencialPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        
        # Menu Locators
        self.menu_venda = page.locator("//div[@data-cy='sidemenu-item-venda']")
        self.menu_relatorios = page.locator("//div[@data-cy='sidemenu-item-relatorios']")
        self.menu_consulta_gerencial = page.locator("//a[@data-cy='sidemenu-item-consulta-gerencial-de-vendas']")
        
        # Action Locators
        self.btn_consultar = page.locator("//button[@data-cy='consulta-gerencial-vendas-filtro-consultar-resultados-button']")
        self.tabela_resultados = page.locator(".flora-table")

    async def navegar_para_consulta(self):
        logger.info("Iniciando navegação pelos menus...")
        await self.menu_venda.click()
        logger.debug("Menu 'Venda' clicado.")
        await self.menu_relatorios.click()
        logger.debug("Menu 'Relatórios' clicado.")
        await self.menu_consulta_gerencial.click()
        logger.info("Página de Consulta Gerencial acessada.")

    async def extrair_dados(self):
        logger.info("Clicando no botão 'Consultar'...")
        await self.btn_consultar.click()
        
        logger.info("Aguardando visibilidade da tabela de resultados (.flora-table)...")
        await self.tabela_resultados.wait_for(state="visible", timeout=30000)
        
        linhas = self.tabela_resultados.locator(".flora-table-row")
        count = await linhas.count()
        logger.info(f"Tabela carregada. Total de linhas detectadas: {count}")
        
        resultados = []

        # Exclui a última linha (total)
        for i in range(count - 1):
            linha = linhas.nth(i)
            loja_el = linha.locator("div.flora-table-cell:nth-child(1)")
            gmv_el = linha.locator("div.flora-table-cell:nth-child(3)")
            
            try:
                loja = (await loja_el.inner_text()).strip()
                gmv_raw = await gmv_el.inner_text()
                
                # Limpeza de valor
                gmv_limpo = gmv_raw.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.').strip()
                valor_float = float(gmv_limpo)
                
                logger.debug(f"Processando linha {i+1}: Loja={loja}, Valor={valor_float}")
                resultados.append([loja, valor_float])
            except Exception as e:
                logger.warning(f"Erro ao processar linha {i+1}: {e}")
                continue
                
        logger.info(f"Extração concluída com sucesso. {len(resultados)} lojas capturadas.")
        return resultados
