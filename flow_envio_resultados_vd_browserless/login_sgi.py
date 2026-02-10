"""
Login automatizado no SGI (sgi.e-boticario.com.br) via Browserless.

Fluxo:
  1. Conecta ao Browserless (stealth=ON, headless=OFF)
  2. Carrega state.json (cookies/sessao anterior) se disponivel
  3. Navega ao SGI e verifica se ja esta logado
  4. Se nao logado:
     a. Clica em "Login Externo" -> "Entrar como colaborador/franqueado"
     b. Realiza login no Google (email + senha + TOTP 2FA)
  5. Aguarda o Dashboard carregar (menu visivel)
  6. Salva state.json atualizado

Requisitos:
  - Browserless self-hosted com suporte a WebSocket CDP
  - Conta Google com 2FA (TOTP) configurada
  - Variaveis de ambiente no .env
"""

import os
import re
import asyncio
import json
import logging
import sys
from urllib.parse import quote
from playwright.async_api import async_playwright
import pyotp
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------
# Configuracao de logs
# -------------------------------------------------------
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "login_sgi.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
    ]
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------
# Variaveis de ambiente
# -------------------------------------------------------
BROWSERLESS_URL = os.getenv("SERVICE_URL_BROWSERLESS")
BROWSERLESS_TOKEN = os.getenv("SERVICE_PASSWORD_BROWSERLESS")
GOOGLE_EMAIL = os.getenv("GOOGLE_EMAIL")
GOOGLE_PASSWORD = os.getenv("GOOGLE_PASSWORD")
GOOGLE_TOTP_SECRET = os.getenv("GOOGLE_TOTP_SECRET", "").replace(" ", "")

# Caminho do state.json (mesmo diretorio do script)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(SCRIPT_DIR, "state.json")

# URLs
SGI_LOGIN_URL = "https://sgi.e-boticario.com.br/Paginas/Acesso/Entrar.aspx?ReturnUrl=%2f"
SGI_AGUARDAR_URL = "https://sgi.e-boticario.com.br/Paginas/Inicializacao/AguardarAcao.aspx"


def build_cdp_url() -> str:
    """Monta a URL de conexao CDP com stealth e headless=false."""
    launch_config = quote(json.dumps({
        "headless": False,
        "stealth": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--window-size=1366,768",
        ]
    }))
    host = BROWSERLESS_URL.replace("https://", "").replace("http://", "")
    return f"wss://{host}?token={BROWSERLESS_TOKEN}&timeout=300000&launch={launch_config}"


async def verificar_se_logado(page) -> bool:
    """
    Verifica se ja estamos logados no SGI baseado na URL e elementos visiveis.
    Retorna True se logado, False se precisa logar.
    """
    current_url = page.url.lower()
    logger.info(f"URL atual: {current_url}")

    # Se estamos na pagina AguardarAcao ou no Dashboard, estamos logados
    if "aguardaracao" in current_url:
        logger.info("Detectado pagina AguardarAcao -> logado!")
        return True

    # Se nao estamos na tela de login, provavelmente estamos logados
    if "sgi.e-boticario.com.br" in current_url and "entrar.aspx" not in current_url and "account/login" not in current_url:
        logger.info("URL do SGI nao e de login -> provavelmente logado!")
        return True

    # Verifica se o botao de login externo esta visivel (indica que NAO estamos logados)
    try:
        btn_login = page.locator("#btnLoginExterno")
        if await btn_login.is_visible(timeout=3000):
            logger.info("Botao Login Externo visivel -> NAO logado.")
            return False
    except:
        pass

    # Verifica presenca de elementos do Dashboard
    try:
        menu = page.locator("#menu-cod-4")
        if await menu.is_visible(timeout=3000):
            logger.info("Menu 'Forca de Vendas' visivel -> logado!")
            return True
    except:
        pass

    logger.info("Nao foi possivel confirmar status de login. Assumindo NAO logado.")
    return False


async def clicar_login_externo(page):
    """
    Clica em 'Login Externo' e depois em 'Entrar como colaborador/franqueado'.
    Retorna a nova pagina se uma nova aba for aberta, ou a pagina atual.
    """
    logger.info("[SGI] Clicando em 'Login Externo' (#btnLoginExterno)...")
    btn = page.locator("#btnLoginExterno")
    await btn.wait_for(state="visible", timeout=10000)
    await btn.click()

    # Aguarda um momento para ver se ja ocorreu redirecionamento por SSO
    await asyncio.sleep(2)

    current_url = page.url.lower()
    if "aguardaracao" in current_url or ("entrar.aspx" not in current_url and "account/login" not in current_url and "sgi.e-boticario.com.br" in current_url):
        logger.info(f"[SGI] Redirecionamento automatico detectado! URL: {current_url}")
        return page, True  # ja logado

    # Procura o botao "Entrar como colaborador/franqueado"
    logger.info("[SGI] Procurando botao 'Entrar como colaborador/franqueado'...")
    botao_colaborador = page.get_by_role(
        "link",
        name=re.compile("entrar como colaborador", re.IGNORECASE)
    ).and_(page.locator("#GoogleExchange"))

    try:
        is_visible = await botao_colaborador.is_visible(timeout=5000)
    except:
        is_visible = False

    if not is_visible:
        logger.info("[SGI] Botao colaborador nao encontrado. Verificando se ja redirecionou...")
        if "entrar.aspx" not in page.url.lower():
            return page, True  # ja logado
        else:
            logger.warning("[SGI] Ainda na tela de login mas botao nao apareceu.")
            return page, False

    # O clique pode abrir uma nova aba - precisamos captura-la
    context = page.context
    new_page = None

    def on_page(p):
        nonlocal new_page
        new_page = p
        logger.info(f"[SGI] Nova aba detectada: {p.url}")

    context.on("page", on_page)

    try:
        await botao_colaborador.click()
        await asyncio.sleep(3)
    except Exception as e:
        logger.warning(f"[SGI] Possivel erro no clique (pode ser normal): {e}")
    finally:
        context.remove_listener("page", on_page)

    if new_page:
        logger.info("[SGI] Alternando para nova aba...")
        await new_page.wait_for_load_state("domcontentloaded")
        return new_page, False
    else:
        return page, False


async def realizar_login_google(page):
    """
    Realiza o login no Google com email, senha e 2FA (TOTP).
    Detecta automaticamente o estado atual da tela do Google.
    """
    logger.info("[GOOGLE] Iniciando autenticacao Google...")

    # Detecta o estado atual da tela
    campo_email_visivel = False
    campo_senha_visivel = False
    tela_selecao_conta = False

    try:
        campo_email_visivel = await page.locator("#identifierId").is_visible(timeout=3000)
    except:
        pass

    try:
        campo_senha_visivel = await page.locator('input[name="Passwd"]').is_visible(timeout=1000)
    except:
        pass

    # Verifica tela de selecao de conta
    try:
        conta = page.locator(f'div[data-identifier="{GOOGLE_EMAIL}"]')
        tela_selecao_conta = await conta.is_visible(timeout=2000)
    except:
        pass

    logger.info(f"[GOOGLE] Email visivel: {campo_email_visivel}, Senha visivel: {campo_senha_visivel}, Selecao conta: {tela_selecao_conta}")

    # CASO 1: Tela de selecao de conta
    if tela_selecao_conta:
        logger.info(f"[GOOGLE] Selecionando conta: {GOOGLE_EMAIL}...")
        await page.locator(f'div[data-identifier="{GOOGLE_EMAIL}"]').click()
        await page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=10000)

    # CASO 2: Campo de email visivel (login completo)
    elif campo_email_visivel:
        logger.info("[GOOGLE] Preenchendo email...")
        await page.fill("#identifierId", GOOGLE_EMAIL)
        await asyncio.sleep(0.5)

        # Clica em Avancar
        next_btn = page.locator("#identifierNext")
        await next_btn.click()
        logger.info("[GOOGLE] Aguardando campo de senha...")
        await page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=15000)

    # CASO 3: Campo de senha ja visivel
    elif campo_senha_visivel:
        logger.info("[GOOGLE] Sessao parcial detectada - campo de senha ja visivel.")

    # CASO 4: Nenhum campo visivel - aguarda e tenta de novo
    else:
        logger.info("[GOOGLE] Nenhum campo visivel. Aguardando...")
        await asyncio.sleep(3)

        # Tenta encontrar o campo de email ou senha
        try:
            if await page.locator("#identifierId").is_visible(timeout=3000):
                await page.fill("#identifierId", GOOGLE_EMAIL)
                await page.locator("#identifierNext").click()
                await page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=15000)
            elif await page.locator('input[name="Passwd"]').is_visible(timeout=3000):
                pass  # Vai preencher senha abaixo
            else:
                logger.error("[GOOGLE] Nao encontrou campos de login!")
                await page.screenshot(path=os.path.join(SCRIPT_DIR, "debug_google_no_fields.png"))
                raise Exception("Campos de login do Google nao encontrados")
        except Exception as e:
            logger.error(f"[GOOGLE] Erro ao tentar encontrar campos: {e}")
            raise

    # --- Preencher Senha ---
    logger.info("[GOOGLE] Preenchendo senha...")
    await page.locator('input[name="Passwd"]').fill(GOOGLE_PASSWORD)
    await asyncio.sleep(1)
    await page.locator("#passwordNext").click()

    # --- 2FA (TOTP) ---
    logger.info("[GOOGLE] Aguardando 2FA...")
    await asyncio.sleep(3)

    try:
        await page.wait_for_selector('input[type="tel"]', state="visible", timeout=15000)

        totp = pyotp.TOTP(GOOGLE_TOTP_SECRET)
        code = totp.now()
        logger.info(f"[GOOGLE] Codigo TOTP gerado: {code}")

        await page.fill('input[type="tel"]', code)
        await asyncio.sleep(1)

        # Clicar no botao de avancar do TOTP
        next_btn = page.locator('#totpNext button, button:has-text("Next"), button:has-text("Avançar")')
        if await next_btn.count() > 0:
            await next_btn.first.click()
        else:
            await page.keyboard.press("Enter")

        await asyncio.sleep(3)
        logger.info("[GOOGLE] TOTP enviado com sucesso!")

    except Exception as e:
        logger.info(f"[GOOGLE] 2FA nao solicitado ou metodo diferente: {e}")

    # Aguarda login completar
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)

    current_url = page.url
    logger.info(f"[GOOGLE] URL apos login: {current_url}")

    # Verifica tela de confirmacao do Google
    try:
        titulo = await page.title()
        if "Confirme que é você" in titulo or "Confirm it's you" in titulo:
            logger.warning("[GOOGLE] Tela de confirmacao detectada! Pode precisar de intervencao manual.")
            await page.screenshot(path=os.path.join(SCRIPT_DIR, "debug_google_confirmation.png"))
    except:
        pass


async def aguardar_dashboard(page, timeout=60000):
    """
    Aguarda o Dashboard do SGI carregar apos o login.
    A pagina AguardarAcao.aspx redireciona automaticamente para o Dashboard.
    """
    current_url = page.url.lower()

    if "aguardaracao" in current_url:
        logger.info("[SGI] Na pagina AguardarAcao. Aguardando Dashboard carregar...")
        try:
            await page.wait_for_selector("#menu-cod-4", state="visible", timeout=timeout)
            logger.info("[SGI] Dashboard carregado! Menu visivel.")
            return True
        except Exception as e:
            logger.warning(f"[SGI] Timeout aguardando Dashboard: {e}")
            return False
    else:
        # Ja passou do AguardarAcao, verifica se o menu esta visivel
        try:
            if await page.locator("#menu-cod-4").is_visible(timeout=10000):
                logger.info("[SGI] Dashboard ja esta carregado!")
                return True
        except:
            pass

        # Tenta verificar por texto "Forca de Vendas"
        try:
            if await page.get_by_text("Força de Vendas").is_visible(timeout=5000):
                logger.info("[SGI] Dashboard confirmado via texto 'Forca de Vendas'.")
                return True
        except:
            pass

        logger.warning("[SGI] Nao foi possivel confirmar carregamento do Dashboard.")
        return False


async def login_sgi():
    """Fluxo principal: login no SGI via Browserless com Google SSO + TOTP."""

    cdp_url = build_cdp_url()
    logger.info("=" * 60)
    logger.info("INICIO - Login SGI via Browserless")
    logger.info("=" * 60)
    logger.info("Conectando ao Browserless (stealth=ON, headless=OFF)...")

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)

        # Carrega state.json se existir (para restaurar sessao anterior)
        storage_state = STATE_PATH if os.path.exists(STATE_PATH) else None

        if storage_state:
            logger.info(f"Carregando sessao anterior de: {STATE_PATH}")
            context = await browser.new_context(
                viewport={"width": 1366, "height": 768},
                locale="pt-BR",
                storage_state=storage_state,
            )
        else:
            # Tenta usar contexto existente do Browserless, ou cria um novo
            if browser.contexts:
                context = browser.contexts[0]
                logger.info("Usando contexto existente do Browserless.")
            else:
                context = await browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    locale="pt-BR",
                )
                logger.info("Novo contexto criado (sem sessao anterior).")

        page = await context.new_page()
        page.set_default_timeout(60000)

        try:
            # --- Etapa 1: Navegar para o SGI ---
            logger.info("[1/5] Navegando para o SGI...")
            await page.goto(SGI_LOGIN_URL, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # --- Etapa 2: Verificar se ja esta logado ---
            logger.info("[2/5] Verificando status de login...")
            ja_logado = await verificar_se_logado(page)

            if ja_logado:
                logger.info("[2/5] Sessao ativa! Pulando login.")
            else:
                # --- Etapa 3: Login Externo ---
                logger.info("[3/5] Realizando Login Externo no SGI...")
                page, sso_logado = await clicar_login_externo(page)

                if not sso_logado:
                    # Verifica se fomos redirecionados para o Google
                    current_url = page.url.lower()
                    logger.info(f"[3/5] URL apos Login Externo: {current_url}")

                    if "accounts.google.com" in current_url or "login-vdmais.grupoboticario.com.br" in current_url:
                        # --- Etapa 4: Login Google + TOTP ---
                        logger.info("[4/5] Realizando login no Google...")

                        # Se estiver na pagina do Azure B2C, aguarda redirecionamento para Google
                        if "login-vdmais.grupoboticario.com.br" in current_url:
                            logger.info("[4/5] Na pagina Azure B2C. Aguardando redirecionamento para Google...")
                            try:
                                await page.wait_for_url("**/accounts.google.com/**", timeout=15000)
                            except:
                                logger.info("[4/5] Timeout esperando Google. Verificando URL atual...")
                                current_url = page.url.lower()
                                if "sgi.e-boticario.com.br" in current_url:
                                    logger.info("[4/5] Ja redirecionou para SGI! SSO automatico.")
                                    sso_logado = True

                        if not sso_logado:
                            await realizar_login_google(page)
                    else:
                        logger.info(f"[3/5] URL nao reconhecida: {current_url}")
                        await page.screenshot(path=os.path.join(SCRIPT_DIR, "debug_url_desconhecida.png"))

            # --- Etapa 5: Aguardar Dashboard ---
            logger.info("[5/5] Aguardando Dashboard do SGI...")

            # Aguarda ate chegar no SGI (pode levar um tempo apos login Google)
            for tentativa in range(3):
                current_url = page.url.lower()
                if "sgi.e-boticario.com.br" in current_url:
                    break
                logger.info(f"[5/5] Ainda nao no SGI (tentativa {tentativa + 1}/3). Aguardando...")
                await asyncio.sleep(5)

            dashboard_ok = await aguardar_dashboard(page)

            if dashboard_ok:
                logger.info("=" * 60)
                logger.info("LOGIN SGI REALIZADO COM SUCESSO!")
                logger.info("=" * 60)
            else:
                logger.warning("Dashboard nao confirmado, mas sessao pode estar ativa.")
                await page.screenshot(path=os.path.join(SCRIPT_DIR, "debug_dashboard_nao_confirmado.png"))

            # --- Salvar state.json ---
            logger.info("Salvando estado da sessao...")
            await context.storage_state(path=STATE_PATH)
            logger.info(f"Estado salvo em: {STATE_PATH}")

        except Exception as e:
            logger.error(f"Erro durante login SGI: {e}")
            try:
                await page.screenshot(path=os.path.join(SCRIPT_DIR, "erro_login_sgi.png"))
                logger.info("Screenshot do erro salvo.")
            except:
                pass
            raise

        finally:
            await browser.close()
            logger.info("Browser encerrado.")


if __name__ == "__main__":
    asyncio.run(login_sgi())
