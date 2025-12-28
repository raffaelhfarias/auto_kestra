import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)

class BasePage:
    def __init__(self, page: Page):
        self.page = page

    async def wait_for_loader(self, selector="#UpdateProgress1", timeout: int = 60000):
        """Aguarda o loader sumir da tela."""
        try:
            await self.page.wait_for_function(
                """(selector) => {
                    const loader = document.querySelector(selector);
                    return !loader || loader.getAttribute('aria-hidden') === 'true' || loader.style.display === 'none';
                }""",
                arg=selector,
                timeout=timeout
            )
        except Exception as e:
            logger.debug(f"Timeout aguardando loader: {e}")
