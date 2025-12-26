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
        import asyncio
        # Define caminho para screenshots
        script_dir = os.path.dirname(__file__)
        screenshot_dir = os.path.join(script_dir, "..", "..", "..", "extracoes")
        os.makedirs(screenshot_dir, exist_ok=True)

        async def safe_screenshot(name, timeout=5000):
            """Tenta tirar um print sem travar o fluxo se as fontes demorarem."""
            path = os.path.join(screenshot_dir, name)
            try:
                await self.page.screenshot(path=path, timeout=timeout)
                logger.info(f"Screenshot salva: {name}")
            except Exception as e:
                logger.warning(f"Não foi possível salvar screenshot {name}: {e}")

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
        # Usa type com delay para parecer mais humano
        await self.input_email.press_sequentially(email, delay=100)
        await asyncio.sleep(1)
        await self.page.keyboard.press("Enter")
        
        # DEBUG: Screenshot segura após o Enter no email
        await asyncio.sleep(4)
        await safe_screenshot("debug_pos_email.png")

        # Fluxo Google - Senha
        logger.info("Preenchendo senha...")
        try:
            # Aguarda o campo de senha sumir de 'hidden' ou aparecer no DOM
            await self.input_password.wait_for(state="visible", timeout=20000)
            await self.input_password.focus()
            await self.input_password.fill(password)
            await asyncio.sleep(1)
            await self.page.keyboard.press("Enter")
        except Exception as e:
            await safe_screenshot("erro_campo_senha.png")
            logger.error(f"Campo de senha não apareceu. URL atual: {self.page.url}")
            raise e

        # Tratativa de telas intermediárias do Google
        await asyncio.sleep(3)
        try:
            await self.page.wait_for_function(
                "() => !window.location.href.includes('signin/challenge/pwd') && !window.location.href.includes('signin/v2/challenge')",
                timeout=15000
            )
        except:
            logger.warning("Ainda na página de desafio. Tentando pular...")
            for texto in ["Not now", "Agora não", "Done", "Concluído", "Confirm", "Confirmar", "Seguinte"]:
                btn = self.page.get_by_role("button", name=texto)
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    await asyncio.sleep(2)
                    break

        logger.info("Aguardando redirecionamento para o SGI...")
        try:
            # Timeout estendido para carregar o SGI após OAuth
            await self.menu_marketing.wait_for(state="visible", timeout=60000)
            logger.info("Login realizado com sucesso!")
        except Exception as e:
            await safe_screenshot("falha_final_login.png")
            logger.error(f"Falha ao validar login. URL atual: {self.page.url}")
            raise e

        await self.ocultar_painel_superior()
