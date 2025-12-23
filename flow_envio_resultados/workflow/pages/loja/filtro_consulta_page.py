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
        logger.info("Navegando para Consulta Gerencial de Vendas...")
        await self.menu_venda.click()
        await self.menu_relatorios.click()
        await self.menu_consulta_gerencial.click()

    async def extrair_dados(self):
        await self.btn_consultar.click()
        await self.tabela_resultados.wait_for(state="visible", timeout=15000)
        
        linhas = self.tabela_resultados.locator(".flora-table-row")
        count = await linhas.count()
        resultados = []

        # Exclui a última linha (total)
        for i in range(count - 1):
            linha = linhas.nth(i)
            loja_el = linha.locator("div.flora-table-cell:nth-child(1)")
            gmv_el = linha.locator("div.flora-table-cell:nth-child(3)")
            
            loja = (await loja_el.inner_text()).strip()
            gmv_raw = await gmv_el.inner_text()
            
            # Limpeza de valor
            gmv_limpo = gmv_raw.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.').strip()
            try:
                resultados.append([loja, float(gmv_limpo)])
            except ValueError:
                continue
                
        return resultados
