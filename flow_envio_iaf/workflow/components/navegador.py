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
        Conecta ao Browserless via CDP com stealth e headless=false.
        Usa o contexto default do Browserless (para manter stealth).
        Carrega cookies do state.json manualmente se existir.
        """
        logger.info("Iniciando browser via Browserless (stealth=ON, headless=OFF)...")
        self.playwright = await async_playwright().start()

        # Monta URL CDP do Browserless
        cdp_url = self._build_cdp_url()

        # Conecta ao Browserless
        self.browser = await self.playwright.chromium.connect_over_cdp(cdp_url)

        # IMPORTANTE: Usar o contexto default do Browserless para manter stealth!
        # Criar new_context() perde as flags anti-deteccao e o Google bloqueia.
        if self.browser.contexts:
            self.context = self.browser.contexts[0]
            logger.info("Usando contexto default do Browserless (stealth preservado).")
        else:
            self.context = await self.browser.new_context(
                viewport={"width": 1366, "height": 768},
                locale="pt-BR",
            )
            logger.info("Novo contexto criado (Browserless sem contexto default).")

        # Carrega cookies do state.json manualmente no contexto default
        script_dir = os.path.dirname(__file__)
        state_path = os.path.join(script_dir, "..", "..", "state.json")

        if os.path.exists(state_path):
            logger.info(f"Carregando cookies de: {state_path}")
            try:
                with open(state_path, "r", encoding="utf-8") as f:
                    state_data = json.load(f)

                # Injeta cookies
                cookies = state_data.get("cookies", [])
                if cookies:
                    await self.context.add_cookies(cookies)
                    logger.info(f"{len(cookies)} cookies carregados no contexto.")

                # Injeta localStorage via script (para cada origin)
                origins = state_data.get("origins", [])
                for origin_data in origins:
                    origin = origin_data.get("origin", "")
                    local_storage = origin_data.get("localStorage", [])
                    if local_storage and origin:
                        logger.info(f"Carregando {len(local_storage)} itens de localStorage para {origin}")
                        # localStorage sera aplicado quando navegarmos para a pagina
            except Exception as e:
                logger.warning(f"Erro ao carregar state.json: {e}")
        else:
            logger.info("Nenhum state.json encontrado. Sessao limpa.")

        # Usa pagina existente ou cria nova
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        self.page.set_default_timeout(60000)

        # Força timezone do browser para America/Sao_Paulo via CDP
        try:
            cdp_session = await self.context.new_cdp_session(self.page)
            await cdp_session.send("Emulation.setTimezoneOverride", {"timezoneId": "America/Sao_Paulo"})
            logger.info("Timezone do browser forçado para America/Sao_Paulo via CDP.")
        except Exception as e:
            logger.warning(f"Não foi possível forçar timezone via CDP: {e}")

        return self.page

    def _build_cdp_url(self) -> str:
        """Monta a URL de conexao CDP com stealth e headless=false."""
        browserless_url = os.environ.get("SERVICE_URL_BROWSERLESS", "")
        browserless_token = os.environ.get("SERVICE_PASSWORD_BROWSERLESS", "")

        if not browserless_url or not browserless_token:
            raise ValueError(
                "Variaveis SERVICE_URL_BROWSERLESS e SERVICE_PASSWORD_BROWSERLESS sao obrigatorias!"
            )

        launch_config = quote(json.dumps({
            "headless": False,
            "stealth": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--window-size=1366,768",
            ]
        }))

        host = browserless_url.replace("https://", "").replace("http://", "")
        return f"wss://{host}?token={browserless_token}&timeout=300000&launch={launch_config}"

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
