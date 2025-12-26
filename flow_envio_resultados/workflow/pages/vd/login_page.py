import logging
from playwright.async_api import Page
from ..base_page import BasePage

logger = logging.getLogger(__name__)

class LoginPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "https://sgi.e-boticario.com.br/Paginas/Acesso/Entrar.aspx?ReturnUrl=%2fDefault.aspx"
        
        # Locators using Elementos.py logic
        self.btn_login_externo = page.locator("#btnLoginExterno")
        self.btn_google_exchange = page.locator("#GoogleExchange")
        self.input_email = page.locator("#identifierId")
        self.btn_email_next = page.locator("//button//span[text()='Avançar']")
        
        self.input_password = page.locator("input[name='Passwd']")
        self.btn_password_next = page.locator("//button//span[text()='Avançar']")
        
        # Menu principal (para validar login)
        self.menu_marketing = page.locator("//div[@id='menu-cod-8']//a[text()='Marketing']")

    async def navigate(self):
        logger.info(f"Navegando para {self.url}")
        await self.page.goto(self.url, wait_until="domcontentloaded")

    async def login(self, email, password):
        logger.info("Iniciando processo de login...")
        await self.navigate()
        
        await self.btn_login_externo.click()
        
        # Tenta clicar no botão do Google (GoogleExchange) ou no link de colaborador
        try:
            await self.btn_google_exchange.wait_for(state="visible", timeout=5000)
            await self.btn_google_exchange.click()
        except:
            await self.page.get_by_role("link", name="Entrar como Colaborador de Franqueado").click()
        
        # Fluxo Google
        await self.input_email.fill(email)
        await self.btn_email_next.click()

        await self.input_password.fill(password)
        # Aguarda 1 segundo antes de clicar em 'Seguinte'
        import asyncio
        await asyncio.sleep(1)
        await self.btn_password_next.click()

        # Aguarda navegação após clicar em 'Seguinte'
        await self.page.wait_for_load_state("networkidle", timeout=10000)

        # Screenshot após fluxo de login, antes de aguardar menu
        await self.page.screenshot(path="screenshot_pos_login.png", full_page=True)
        logger.info("Screenshot pós-login salva como screenshot_pos_login.png")

        # Log da URL atual após login
        current_url = self.page.url
        logger.info(f"URL atual após login: {current_url}")

        # Aguarda o menu principal
        # Aguarda 1 segundo antes de aguardar o menu principal
        await asyncio.sleep(1)
        await self.menu_marketing.wait_for(state="visible", timeout=30000)
        logger.info("Login realizado com sucesso!")

        # Tenta fechar painel superior
        await self.ocultar_painel_superior()
