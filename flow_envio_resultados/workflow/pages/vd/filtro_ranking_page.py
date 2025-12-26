import logging
from datetime import datetime
from playwright.async_api import Page
from ..base_page import BasePage

logger = logging.getLogger(__name__)

class RankingVendasPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        
        # Menu Locators
        self.menu_marketing = page.get_by_role("link", name="Marketing")
        self.menu_consultas = page.get_by_role("link", name="Consultas")
        self.menu_ranking_vendas = page.get_by_role("link", name="Consultar Ranking Vendas")
        
        # Filter Locators
        self.input_codigo_produto = page.locator("#ContentPlaceHolder1_txtEstruturaProdutoCodigo_T2")
        self.btn_data_inicio = page.locator("#ContentPlaceHolder1_cedDataFaturamentoInicio_s1a")
        self.btn_limpar_data = page.locator(".ajax__calendar_container > span:nth-child(3)")
        self.btn_footer_calendar = page.locator(".ajax__calendar_footer")
        self.btn_data_fim = page.locator("#ContentPlaceHolder1_cedDataFaturamentoFim_s1a")
        self.btn_hoje_data = page.locator("div.linha_form:nth-child(2) > span:nth-child(4) > span:nth-child(6) > div:nth-child(1) > span:nth-child(3)")
        self.btn_limpar_data_pef_fim = page.locator("div.linha_form:nth-child(2) > span:nth-child(4) > span:nth-child(6) > div:nth-child(1) > span:nth-child(3) > div:nth-child(1)")
        
        self.select_ciclo_inicio = page.locator("#ContentPlaceHolder1_ddlCicloFaturamentoInicial_d1")
        self.select_ciclo_fim = page.locator("#ContentPlaceHolder1_ddlCicloFaturamentoFinal_d1")
        self.select_situacao_fiscal = page.locator("#ContentPlaceHolder1_ddlSituacaoFiscal_d1")
        
        self.radio_agrupamento_gerencia = page.locator("#ContentPlaceHolder1_rdbAgrupamentoGerencia")
        self.btn_agrupamento_geral = page.locator("#divAgrupamento > span:nth-child(1) > span:nth-child(6)")
        self.btn_buscar = page.locator("#ContentPlaceHolder1_btnBuscar_btn")
        
        # Results
        self.grid_resultados = page.locator("#ContentPlaceHolder1_grdRankingVendas")
        self.painel_mensagem = page.locator("#mensagemPanel")
        self.btn_ok_mensagem = page.locator("#popupOkButton")

    async def navegar_para_ranking(self):
        logger.info("Navegando para Ranking de Vendas...")
        await self.click_and_wait(self.menu_marketing)
        await self.click_and_wait(self.menu_consultas)
        await self.click_and_wait(self.menu_ranking_vendas)

    async def configurar_datas_eudora(self):
        """Data Início: Limpar | Data Fim: Hoje"""
        logger.info("Configurando datas para EUDORA (Início: Limpar, Fim: Hoje)")
        await self.btn_data_inicio.click()
        await self.btn_limpar_data.click()
        await self.btn_data_fim.click()
        await self.btn_hoje_data.click()

    async def configurar_datas_pef(self):
        """Data Início: Limpar | Data Fim: Limpar (conforme fluxo original)"""
        logger.info("Configurando datas para PEF (Início: Limpar, Fim: Limpar)")
        await self.btn_data_inicio.click()
        await self.btn_footer_calendar.click()
        await self.btn_data_fim.click()
        await self.btn_limpar_data_pef_fim.click()

    async def selecionar_ciclo(self, ciclo: int):
        hoje = datetime.now()
        ano_atual = hoje.year
        
        # Lógica de transição de ano:
        # Se estamos em Novembro/Dezembro e o ciclo é pequeno (1, 2, 3...), provalvelmente é do ano que vem.
        # Se o ciclo é grande (16, 17...) e estamos no começo do ano, é do ano passado.
        if ciclo < 10 and hoje.month >= 11:
            ano_alvo = ano_atual + 1
        elif ciclo > 10 and hoje.month <= 2:
            ano_alvo = ano_atual - 1
        else:
            ano_alvo = ano_atual
            
        value_esperado = f"{ano_alvo}{ciclo:02d}"
        logger.info(f"Tentando selecionar ciclo {ciclo} (Ano: {ano_alvo}, Value: {value_esperado})")
        
        # Tenta selecionar o ciclo. Se falhar, tenta o ano atual como fallback.
        try:
            await self.select_ciclo_inicio.select_option(value=value_esperado)
            await self.select_ciclo_fim.select_option(value=value_esperado)
            await self.wait_for_loader()
        except:
            logger.warning(f"Não encontrou value {value_esperado}. Tentando fallback com outro ano...")
            ano_fallback = ano_atual if ano_alvo != ano_atual else ano_atual - 1
            value_fallback = f"{ano_fallback}{ciclo:02d}"
            try:
                await self.select_ciclo_inicio.select_option(value=value_fallback)
                await self.select_ciclo_fim.select_option(value=value_fallback)
                await self.wait_for_loader()
                logger.info(f"Selecionado via fallback: {value_fallback}")
            except Exception as e:
                logger.error(f"Falha total ao selecionar ciclo {ciclo}: {e}")
                raise e

    async def extrair_dados(self, codigo_produto=None, agrupamento_gerencia=False):
        """Configura filtros e extrai dados da grid."""
        if codigo_produto:
            await self.input_codigo_produto.fill(codigo_produto)
            await self.page.keyboard.press("Tab")
            await self.wait_for_loader()

        # Configura Situação Fiscal Normal (value="2")
        await self.select_situacao_fiscal.select_option(value="2")
        await self.wait_for_loader()

        if agrupamento_gerencia:
            await self.click_and_wait(self.radio_agrupamento_gerencia)
        else:
            await self.click_and_wait(self.btn_agrupamento_geral)

        await self.click_and_wait(self.btn_buscar, timeout=60000)

        # Verifica se há mensagem de sem resultados
        if await self.painel_mensagem.is_visible():
            logger.info("Nenhum resultado encontrado.")
            if await self.btn_ok_mensagem.is_visible():
                await self.btn_ok_mensagem.click()
            return []

        return await self._extrair_grid()

    async def _extrair_grid(self):
        await self.grid_resultados.wait_for(state="visible", timeout=15000)
        linhas = self.grid_resultados.locator("tr")
        count = await linhas.count()
        resultados = []

        for i in range(count):
            linha = linhas.nth(i)
            celulas = linha.locator("td.grid_celula")
            if await celulas.count() >= 5:
                vd = (await celulas.nth(0).inner_text()).strip()
                valor_raw = await celulas.nth(4).inner_text()
                valor_limpo = valor_raw.replace('.', '').replace(',', '.').replace('\xa0', '').strip()
                try:
                    resultados.append([vd, float(valor_limpo)])
                except ValueError:
                    continue
        return resultados
