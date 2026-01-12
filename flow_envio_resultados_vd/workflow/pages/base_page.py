import logging
from playwright.async_api import Page, expect

logger = logging.getLogger(__name__)

class BasePage:
    def __init__(self, page: Page):
        self.page = page

    async def wait_for_loader(self, timeout: int = 60000):
        """Aguarda o loader sumir da tela."""
        loader_selector = "#UpdateProgress1"
        try:
            # Aguarda o loader ficar invisível ou sumir do DOM
            await self.page.wait_for_function(
                """(selector) => {
                    const loader = document.querySelector(selector);
                    return !loader || loader.getAttribute('aria-hidden') === 'true' || loader.style.display === 'none';
                }""",
                arg=loader_selector,
                timeout=timeout
            )
        except Exception as e:
            logger.debug(f"Timeout aguardando loader: {e}")

    async def click_and_wait(self, locator, timeout: int = 10000):
        """Clica em um elemento e aguarda o loader."""
        await locator.wait_for(state="visible", timeout=timeout)
        await locator.click()
        await self.wait_for_loader()

    async def ocultar_painel_superior(self):
        """Tenta fechar o painel superior de aviso após login."""
        btn_close = self.page.locator("#painelSuperior .btn-close, .top_panel .btn-close")
        try:
            if await btn_close.is_visible(timeout=3000):
                await btn_close.click()
                logger.info("Painel superior fechado.")
        except Exception:
            pass
