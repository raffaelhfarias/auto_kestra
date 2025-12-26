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
        import os
        # Define caminho para screenshots na pasta monitorada pelo Kestra
        script_dir = os.path.dirname(__file__)
        screenshot_dir = os.path.join(script_dir, "..", "..", "..", "extracoes")
        os.makedirs(screenshot_dir, exist_ok=True)

        logger.info("Iniciando processo de login...")
        await self.navigate()
        
        logger.info("Clicando em botão de login externo...")
        await self.btn_login_externo.click()
        
        try:
            logger.info("Aguardando botão Google...")
            await self.btn_google_exchange.wait_for(state="visible", timeout=10000)
            await self.btn_google_exchange.click()
        except:
            logger.info("Botão Google não encontrado, tentando link de colaborador...")
            await self.page.get_by_role("link", name="Entrar como Colaborador de Franqueado").click()
        
        # Fluxo Google - Email
        logger.info("Preenchendo email...")
        await self.input_email.wait_for(state="visible", timeout=15000)
        await self.input_email.focus()
        await self.input_email.fill(email)
        await self.page.keyboard.press("Enter")
        
        # DEBUG: Screenshot logo após o Enter no email
        import asyncio
        await asyncio.sleep(3)
        debug_email_path = os.path.join(screenshot_dir, "debug_pos_email.png")
        await self.page.screenshot(path=debug_email_path)
        logger.info(f"Screenshot pós-email salva em: {debug_email_path}")

        # Fluxo Google - Senha
        logger.info("Preenchendo senha...")
        try:
            await self.input_password.wait_for(state="visible", timeout=20000)
            await self.input_password.focus()
            await self.input_password.fill(password)
            await asyncio.sleep(1)
            await self.page.keyboard.press("Enter")
        except Exception as e:
            error_path = os.path.join(screenshot_dir, "erro_campo_senha.png")
            await self.page.screenshot(path=error_path)
            logger.error(f"Campo de senha não apareceu. Screenshot de erro: {error_path}")
            raise e

        # Tratativa de telas intermediárias do Google
        try:
            await self.page.wait_for_function(
                "() => !window.location.href.includes('signin/challenge/pwd') && !window.location.href.includes('signin/v2/challenge')",
                timeout=15000
            )
        except:
            logger.warning("Ainda na página de desafio. Tentando pular...")
            for texto in ["Not now", "Agora não", "Done", "Concluído", "Confirm", "Confirmar"]:
                btn = self.page.get_by_role("button", name=texto)
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    break

        logger.info("Aguardando redirecionamento para o SGI...")
        try:
            await self.menu_marketing.wait_for(state="visible", timeout=45000)
            logger.info("Login realizado com sucesso!")
        except Exception as e:
            final_error_path = os.path.join(screenshot_dir, "falha_final_login.png")
            await self.page.screenshot(path=final_error_path)
            logger.error(f"Falha ao validar login. Screenshot: {final_error_path}")
            raise e

        await self.ocultar_painel_superior()
