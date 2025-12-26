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
        await self.input_email.fill(email)
        await self.page.keyboard.press("Enter")
        
        # Fluxo Google - Senha
        logger.info("Preenchendo senha...")
        # O seletor de senha pode demorar um pouco após o Enter no email
        await self.input_password.wait_for(state="visible", timeout=15000)
        await self.input_password.fill(password)
        
        import asyncio
        await asyncio.sleep(2) # Pausa humana deliberada
        
        logger.info("Enviando senha via tecla Enter...")
        await self.page.keyboard.press("Enter")

        # Tratativa de telas intermediárias do Google (Recovery email, Protect account, etc)
        # Aguarda um tempo para ver se a URL muda ou se aparece um desafio
        try:
            # Espera até 15s por uma tela que NÃO seja o login do Google ou que seja o SGI
            await self.page.wait_for_function(
                "() => !window.location.href.includes('signin/challenge/pwd') && !window.location.href.includes('signin/v2/challenge')",
                timeout=15000
            )
        except:
            logger.warning("Ainda na página de desafio do Google. Tentando detectar botões de 'Agora não' ou 'Confirmar'...")
            # Tenta clicar em "Agora não" ou botões similares se aparecerem
            botoes_pular = [
                "Not now", "Agora não", "Done", "Concluído", "Confirm", "Confirmar"
            ]
            for texto in botoes_pular:
                btn = self.page.get_by_role("button", name=texto)
                if await btn.is_visible(timeout=500):
                    await btn.click()
                    logger.info(f"Clicou em botão de escape: {texto}")
                    break

        logger.info("Aguardando redirecionamento para o SGI...")
        # Aguarda o menu principal com um timeout generoso
        try:
            await self.menu_marketing.wait_for(state="visible", timeout=45000)
            logger.info("Login realizado com sucesso!")
        except Exception as e:
            await self.page.screenshot(path="falha_login_vd.png", full_page=True)
            logger.error(f"Falha ao validar login. Screenshot salva em falha_login_vd.png. URL atual: {self.page.url}")
            raise e

        # Tenta fechar painel superior
        await self.ocultar_painel_superior()
