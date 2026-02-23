import logging
from playwright.async_api import Page, Response
import os

logger = logging.getLogger(__name__)

class BasePage:
    """
    Classe base para todas as páginas (Page Objects).
    Contém métodos genéricos e comuns a todas as páginas.
    """

    def __init__(self, page: Page):
        self.page = page

    async def navegar(self, url: str):
        """Navega para uma URL específica."""
        logger.info(f"Navegando para: {url}")
        response = await self.page.goto(url, wait_until="domcontentloaded")
        return response

    async def extrair_texto(self, seletor: str, timeout: int = 5000) -> str:
        """Espera um elemento e retorna seu texto."""
        try:
            elemento = self.page.locator(seletor).first
            await elemento.wait_for(state="visible", timeout=timeout)
            return await elemento.inner_text()
        except Exception as e:
            logger.warning(f"Erro ao extrair texto de {seletor}: {e}")
            return ""

    async def clicar(self, seletor: str, timeout: int = 5000):
        """Clica em um elemento."""
        try:
            elemento = self.page.locator(seletor).first
            await elemento.wait_for(state="visible", timeout=timeout)
            await elemento.click()
        except Exception as e:
            logger.error(f"Erro ao clicar em {seletor}: {e}")
            raise e

    async def preencher(self, seletor: str, valor: str, timeout: int = 5000):
        """Preenche um campo de input."""
        try:
            elemento = self.page.locator(seletor).first
            await elemento.wait_for(state="visible", timeout=timeout)
            await elemento.fill(valor)
        except Exception as e:
            logger.error(f"Erro ao preencher {seletor}: {e}")
            raise e

    async def realizar_login(self, usuario: str, senha: str):
        """
        Realiza o login utilizando credenciais e, logo após, 
        navega para a página alvo (iaf-consolidated summary).
        """
        logger.info("Iniciando processo de login...")
        
        # Navega para a página de login
        url_login = "https://login.extranet.grupoboticario.com.br/1e6392bd-5377-48f0-9a8e-467f5b381b18/oauth2/v2.0/authorize?p=B2C_1A_JIT_SIGNUPORSIGNIN_FEDCORP_APIGEE_PRD&client_id=b3001e60-a8e0-4da8-82ba-c3a701405f08&redirect_uri=https%3A%2F%2Fextranet.grupoboticario.com.br%2Fauth%2Fcallback&response_type=code&scope=openid%20email%20https%3A%2F%2Fgboticariob2c.onmicrosoft.com%2Fa6cd4fe6-3d71-455a-b99d-f458a07cc0d1%2Fextranet.api%20offline_access&state=285d8d9f509a465b95b56feb7673abc2&code_challenge=W-eMqAmGg34WsB1lURbyxo417cZLZJC3bS_MjtV2n4Q&code_challenge_method=S256&response_mode=query"
        await self.navegar(url_login)
        
        # Preenche os dados de acesso
        await self.preencher("#signInName", usuario)
        await self.preencher("#password", senha)
        
        # Clica no botão Entrar
        logger.info("Clicando no botão de login...")
        await self.clicar("#next")
        
        # Aguarda o redirecionamento do callback OAuth completar
        # O login redireciona para extranet.grupoboticario.com.br/auth/callback e depois para a home
        logger.info("Aguardando redirecionamento do login (callback OAuth)...")
        await self.page.wait_for_url("**/extranet.grupoboticario.com.br/**", timeout=30000)
        logger.info(f"Redirecionamento concluído. URL atual: {self.page.url}")
        
        # Aguarda a página pós-login estabilizar (SPA pode não atingir networkidle)
        await self.page.wait_for_load_state("domcontentloaded")
        await self.page.wait_for_timeout(3000)
        logger.info("Página pós-login estabilizada.")
        
        # Navega para a página desejada
        url_alvo = "https://extranet.grupoboticario.com.br/mfe/gi/iaf-consolidated/summary"
        logger.info(f"Navegando para a URL alvo: {url_alvo}")
        await self.page.goto(url_alvo, wait_until="domcontentloaded", timeout=30000)
        
        # Aguarda a SPA renderizar o conteúdo
        await self.page.wait_for_timeout(3000)
        logger.info("Login realizado e navegação para a URL alvo concluída.")
