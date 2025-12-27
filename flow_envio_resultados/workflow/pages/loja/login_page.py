import logging
from playwright.async_api import Page
from ..base_page import BasePage

logger = logging.getLogger(__name__)

class LojaLoginPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "https://cp10356.retaguarda.grupoboticario.com.br/app/#/login"
        
        # Locators usando data-cy (Melhor prática Playwright)
        self.input_usuario = page.locator("//input[@data-cy='login-usuario-input-field']")
        self.input_senha = page.locator("//input[@data-cy='login-senha-input-field']")
        self.btn_entrar = page.locator("//button[@data-cy='login-entrar-button']")

    async def navigate(self):
        logger.info(f"Acessando login Loja: {self.url}")
        await self.page.goto(self.url)

    async def login(self, username, password):
        await self.navigate()
        
        logger.info("Aguardando carregamento da rede (networkidle)...")
        await self.page.wait_for_load_state('networkidle')
        
        logger.info(f"Procurando campo de usuário: {username[:3]}***")
        await self.input_usuario.wait_for(state="visible", timeout=15000)
        await self.input_usuario.fill(username)
        
        logger.info("Preenchendo campo de senha...")
        await self.input_senha.wait_for(state="visible", timeout=10000)
        await self.input_senha.fill(password)
        
        logger.info("Clicando no botão 'Entrar'...")
        await self.btn_entrar.click()
        
        logger.info("Aguardando confirmação de login (URL da Home)...")
        try:
            await self.page.wait_for_url("**/app/#/", timeout=20000)
            logger.info("Login Loja realizado com sucesso!")
        except Exception as e:
            logger.error(f"Falha ao confirmar login. URL atual: {self.page.url}")
            raise e
