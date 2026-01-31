
import logging
from playwright.async_api import Page, Response

logger = logging.getLogger(__name__)

class BasePage:
    """
    Classe base para todas as páginas (Page Objects).
    Contém métodos genéricos e comuns a todas as páginas.
    """

    def __init__(self, page: Page):
        self.page = page

    async def navegar(self, url: str):
        """Navega para uma URL específica."""
        logger.info(f"Navegando para: {url}")
        response = await self.page.goto(url, wait_until="domcontentloaded")
        return response

    async def extrair_texto(self, seletor: str, timeout: int = 5000) -> str:
        """Espera um elemento e retorna seu texto."""
        try:
            elemento = self.page.locator(seletor).first
            await elemento.wait_for(state="visible", timeout=timeout)
            return await elemento.inner_text()
        except Exception as e:
            logger.warning(f"Erro ao extrair texto de {seletor}: {e}")
            return ""

    async def clicar(self, seletor: str, timeout: int = 5000):
        """Clica em um elemento."""
        try:
            elemento = self.page.locator(seletor).first
            await elemento.wait_for(state="visible", timeout=timeout)
            await elemento.click()
        except Exception as e:
            logger.error(f"Erro ao clicar em {seletor}: {e}")
            raise e

    async def preencher(self, seletor: str, valor: str, timeout: int = 5000):
        """Preenche um campo de input."""
        try:
            elemento = self.page.locator(seletor).first
            await elemento.wait_for(state="visible", timeout=timeout)
            await elemento.fill(valor)
        except Exception as e:
            logger.error(f"Erro ao preencher {seletor}: {e}")
            raise e
