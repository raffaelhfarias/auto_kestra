"""
Modulo para configuracao do navegador Playwright via Browserless (CDP).

Configuracoes criticas:
  - headless=false  -> Obrigatorio para o Google nao bloquear
  - stealth=true    -> Obrigatorio para evitar deteccao de automacao
  - timeout=300000  -> 5 minutos para o fluxo completo

IMPORTANTE: Sempre usar o contexto default do Browserless (browser.contexts[0])
para manter as flags anti-deteccao. Criar um new_context() perde o stealth.
Cookies do state.json sao injetados manualmente no contexto default.
"""

from playwright.async_api import async_playwright

import json
import logging
import os
from urllib.parse import quote

logger = logging.getLogger(__name__)


class Navegador:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def setup_browser(self):
        """
        Inicia o browser localmente.
        """
        logger.info("Iniciando browser local (Playwright)...")
        self.playwright = await async_playwright().start()

        # Verifica se estamos em ambiente Docker/Kestra (geralmente sem display)
        # Se estiver rodando local no Windows, headless=False ajuda a ver o que ocorre.
        is_docker = os.path.exists("/.dockerenv")
        headless = True if is_docker else False

        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )

        self.context = await self.browser.new_context(
            # viewport={"width": 1366, "height": 768},
            locale="pt-BR",
            accept_downloads=True
        )
        logger.info(f"Contexto criado (headless={headless}, downloads=ON).")

        # Carrega cookies do state.json manualmente se existir
        script_dir = os.path.dirname(__file__)
        state_path = os.path.join(script_dir, "..", "..", "state.json")

        if os.path.exists(state_path):
            logger.info(f"Carregando cookies de: {state_path}")
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    state_data = json.load(f)

                cookies = state_data.get("cookies", [])
                if cookies:
                    await self.context.add_cookies(cookies)
                    logger.info(f"{len(cookies)} cookies carregados no contexto.")
            except Exception as e:
                logger.warning(f"Erro ao carregar state.json: {e}")
        else:
            logger.info("Nenhum state.json encontrado. Sessao limpa.")

        self.page = await self.context.new_page()
        self.page.set_default_timeout(60000)
        return self.page

    def update_page(self, new_page):
        """Atualiza a referencia da pagina quando uma nova aba e aberta."""
        self.page = new_page
        logger.info("Referencia da pagina atualizada no navegador.")

    async def save_state(self):
        """Salva o estado da sessao (cookies, localStorage) no arquivo state.json."""
        try:
            if self.context:
                script_dir = os.path.dirname(__file__)
                state_path = os.path.join(script_dir, "..", "..", "state.json")
                await self.context.storage_state(path=state_path)
                logger.info(f"Estado da sessao salvo em: {state_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar estado da sessao: {e}")

    async def stop_browser(self):
        """Fecha o browser e limpa os recursos."""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser encerrado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao fechar browser: {e}")
