"""
Page Object para o sistema Solides/Tangerino.
Responsável por login e navegação até a página de relatórios.
"""

import asyncio
import os
import logging

logger = logging.getLogger(__name__)

# Mapa de filiais disponíveis no sistema (value -> nome legível)
FILIAIS = {
    "": "Todas",
    "2385814": "Caaporã Perfumes Ltda - ME",
    "2385822": "Edalice Perfumes Ltda - ME",
    "2385808": "Edgar e Alice Perfumes Ltda - EPP",
    "2385809": "ESGN Perfumes Ltda - ME",
    "2385812": "Goianinha Perfumes Ltda - ME",
    "2385811": "Lua Branca Perfumes Ltda - ME",
    "2385804": "Maracatu Perfumes Ltda - EPP",
    "2380190": "Matriz",
    "2385800": "Millenium Perfumes Ltda - EPP",
    "2385818": "Pirauá Perfmues Ltda - ME",
    "2385798": "Sobralana Perfumes Ltda - EPP",
    "2385810": "Tejucupapo Perfumes Ltda - ME",
    "2385823": "Timbauba Perfumes Ltda",
}


class SolidesPage:
    """Page Object para interações com o Solides/Tangerino."""

    def __init__(self, page):
        self.page = page

    async def realizar_login(self, user: str, password: str):
        """Faz login no sistema Tangerino."""
        url = "https://app.tangerino.com.br/Tangerino/pages/LoginPage"
        logger.info(f"Navegando para {url}...")
        await self.page.goto(url, wait_until="networkidle")

        logger.info("Preenchendo credenciais...")
        await self.page.fill('input[name="login"]', user)
        await self.page.fill('input[name="password"]', password)

        logger.info("Clicando no botão Entrar...")
        await self.page.click('input[name="btnLogin"]')

        logger.info("Aguardando carregamento pós-login...")
        try:
            await self.page.wait_for_load_state("networkidle", timeout=60000)
            logger.info("Aguardando renderização dos menus...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.warning(f"Timeout ou erro esperando carregamento: {e}")

    async def navegar_para_banco_horas(self):
        """Navega pelos menus: Ponto > Relatórios > Banco de horas / Hora extra."""
        logger.info("Clicando no menu 'Ponto'...")
        await self.page.click('span.nome-menu:has-text("Ponto")')
        await asyncio.sleep(2)

        logger.info("Clicando no submenu 'Relatórios'...")
        await self.page.click('span.nome-menu-nivel-2:has-text("Relatórios")')
        await asyncio.sleep(2)

        logger.info("Clicando em 'Banco de horas / Hora extra'...")
        await self.page.click('span:has-text("Banco de horas / Hora extra")')

        logger.info("Aguardando carregamento do relatório...")
        try:
            await self.page.wait_for_selector(
                'text="Banco de horas / Hora extra"', state="visible", timeout=10000
            )
        except Exception:
            logger.warning("Texto do relatório demorou a aparecer, continuando...")

        await self.page.wait_for_timeout(5000)
        logger.info("Página de Banco de Horas carregada com sucesso!")

    async def selecionar_filial_select2(self, nome_filial: str):
        """
        Seleciona a filial no dropdown Select2.
        O Select2 exige: clicar no container -> digitar no campo de busca -> clicar na opção.
        """
        logger.info(f"Selecionando filial: {nome_filial}...")

        # 1. Clica no container Select2 do dropdown de Filiais
        select2_container = self.page.locator(
            'select.dropdown-empresa'
        ).locator('xpath=..').locator('.select2-selection')
        await select2_container.click()
        await asyncio.sleep(1)

        # 2. Digita o nome da filial no campo de busca do Select2
        search_input = self.page.locator('.select2-search__field')
        await search_input.fill(nome_filial)
        await asyncio.sleep(1)

        # 3. Clica na opção que aparece no dropdown
        option = self.page.locator(f'.select2-results__option:has-text("{nome_filial}")')
        await option.click()
        await asyncio.sleep(1)

        logger.info(f"Filial '{nome_filial}' selecionada.")

    async def preencher_datas(self, data_inicio: str, data_fim: str):
        """
        Preenche os campos de Data Início e Data Final.
        Formato esperado: DD/MM/AAAA (ex: 01/03/2026).
        Usa triple click + fill para limpar e substituir o valor existente.
        """
        logger.info(f"Preenchendo datas: {data_inicio} até {data_fim}...")

        # Data de Início
        campo_inicio = self.page.locator('input[name="containerDataInicio:dataInicio"]')
        await campo_inicio.click(click_count=3)  # Seleciona todo o texto
        await campo_inicio.fill(data_inicio)

        # Data Final
        campo_fim = self.page.locator('input[name="containerDataFim:dataFim"]')
        await campo_fim.click(click_count=3)
        await campo_fim.fill(data_fim)

        logger.info("Datas preenchidas.")

    async def selecionar_formato_excel(self):
        """Altera o formato de saída para Excel (value=0)."""
        logger.info("Selecionando formato de saída: Excel...")

        select2_container = self.page.locator(
            'select.containerFormat'
        ).locator('xpath=..').locator('.select2-selection')
        await select2_container.click()
        await asyncio.sleep(1)

        option = self.page.locator('.select2-results__option:has-text("Excel")')
        await option.click()
        await asyncio.sleep(1)

        logger.info("Formato Excel selecionado.")

    async def gerar_relatorio(self) -> str:
        """Clica no botão 'Gerar Relatório', aguarda o processamento e baixa o arquivo."""
        logger.info("Clicando em 'Gerar Relatório' e aguardando download...")
        
        # Puxa o diretório de destino relativo à estrutura do projeto
        # sólidos.py está em workflow/pages/solides.py, queremos scrape_solides/relatorios
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        download_dir = os.path.join(base_dir, "relatorios")
        os.makedirs(download_dir, exist_ok=True)
        
        async with self.page.expect_download(timeout=120000) as download_info:
            await self.page.click(
                'input.botaoConsultar[value="Gerar Relatório"]',
                no_wait_after=True,
            )
            
        download = await download_info.value
        file_path = os.path.join(download_dir, download.suggested_filename)
        
        logger.info(f"Salvando download em: {file_path}")
        await download.save_as(file_path)
                    
        # Checando tamanho do arquivo
        size = os.path.getsize(file_path)
        logger.info(f"Relatório salvo com sucesso em: {file_path} | Tamanho: {size} bytes")
        
        return file_path
