import logging
from playwright.async_api import Page
from ..base_page import BasePage

logger = logging.getLogger(__name__)

class VidibrLoginPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = "https://cliente.vidibr.com/"
        
        # Locators robustos usando data-cy (especificando input para evitar duplicidade com ion-input)
        self.input_usuario = page.locator("input[data-cy='login']")
        self.input_senha = page.locator("input[data-cy='senha']")
        self.btn_entrar = page.locator("button[data-cy='entrar']")
        self.home_indicator = page.get_by_role("button", name="Avaliações Realizadas")

    async def navigate(self):
        logger.info(f"Acessando VIDIBR: {self.url}")
        await self.page.goto(self.url)

    async def login(self, username, password):
        await self.navigate()
        await self.page.wait_for_load_state('networkidle')
        
        # Verifica se já está logado
        if await self.home_indicator.count() > 0:
            logger.info("Sessão ativa detectada.")
            return

        # Proteção contra username None para evitar erro 'NoneType' object is not subscriptable
        user_display = (username[:3] + "***") if username else "NÃO DEFINIDO"
        logger.info(f"Preenchendo credenciais para usuário: {user_display}")
        
        if not username or not password:
            raise ValueError("Usuário ou Senha não foram fornecidos (verifique as variáveis de ambiente).")

        await self.input_usuario.wait_for(state="visible", timeout=15000)
        await self.input_usuario.fill(username)
        await self.input_senha.fill(password)
        await self.btn_entrar.click()
        
        logger.info("Aguardando confirmação de login...")
        try:
            # Aumentado timeout para garantir carregamento em conexões lentas
            await self.home_indicator.wait_for(state="visible", timeout=30000)
            logger.info("Login VIDIBR realizado com sucesso!")
        except Exception as e:
            logger.error(f"Falha ao confirmar login. URL atual: {self.page.url}")
            raise e
