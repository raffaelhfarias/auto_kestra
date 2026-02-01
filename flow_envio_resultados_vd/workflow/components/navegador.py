"""
Módulo para configuração do navegador Playwright com técnicas de evasão (Stealth).
"""

from playwright.async_api import async_playwright

import logging


logger = logging.getLogger(__name__)

# User-Agent moderno para evitar detecção pelo Google
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

class Navegador:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def setup_browser(self):        
        logger.info("Iniciando browser (Modo: Stealth/Google Login Optimized)...")
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
            "--remote-debugging-port=9222"
        ]

        self.browser = await self.playwright.chromium.launch(
            headless=False,
            channel="chromium",
            args=args,
            slow_mo=0 # Removido slow_mo para máxima performance dinâmica
        )

        # Verifica se existe um arquivo de sessão (Storage State)
        script_dir = os.path.dirname(__file__)
        state_path = os.path.join(script_dir, "..", "..", "state.json")
        storage_state = state_path if os.path.exists(state_path) else None
        
        if storage_state:
            logger.info(f"Carregando sessão existente de: {state_path}")

        self.context = await self.browser.new_context(
            user_agent=USER_AGENT,
            storage_state=storage_state,
            bypass_csp=True,
            locale='pt-BR',
            timezone_id='America/Sao_Paulo',
            accept_downloads=True,
            java_script_enabled=True,
            viewport=None,
            extra_http_headers={
                "sec-ch-ua": '\"Google Chrome\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '\"Windows\"',
            }
        )

        # Script avançado para evitar detecção de automação (Fingerprinting)
        await self.context.add_init_script(""""
            // Remove o flag webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // Mock de plugins para parecer um browser real
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer' },
                    { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer' },
                    { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer' },
                    { name: 'PDF Viewer', filename: 'internal-pdf-viewer' },
                    { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer' }
                ]
            });

            // Mock de linguagens
            Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });

            // Mock de hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
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
