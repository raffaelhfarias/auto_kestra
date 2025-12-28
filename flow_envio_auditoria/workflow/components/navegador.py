"""
Módulo para configuração do navegador Playwright com técnicas de evasão (Stealth).
"""

from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)

# User-Agent moderno para evitar detecção
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

class Navegador:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def setup_browser(self):        
        logger.info("Iniciando browser (Modo: Stealth)...")
        self.playwright = await async_playwright().start()

        # Argumentos críticos para estabilidade e evasão
        args = [
            #"--headless=new",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--start-maximized",
            "--disable-infobars",
            "--ignore-certificate-errors",
            "--disable-extensions",
        ]

        self.browser = await self.playwright.chromium.launch(
            headless=False,
            channel="chromium",
            args=args
        )

        self.context = await self.browser.new_context(
            user_agent=USER_AGENT,
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
            viewport={'width': 1920, 'height': 1080}
        )

        # Script avançado para evitar detecção de automação
        await self.context.add_init_script(""""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)

        self.page = await self.context.new_page()
        return self.page

    async def stop_browser(self):
        """Fecha o browser e limpa os recursos."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser encerrado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao fechar browser: {e}")
