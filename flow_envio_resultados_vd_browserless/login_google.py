"""
Login automatizado no Google via Browserless com verificacao 2FA (TOTP).

Requisitos:
  - Browserless self-hosted com suporte a WebSocket CDP
  - Conta Google com autenticacao de dois fatores (TOTP) configurada
  - Variaveis de ambiente configuradas no .env

Configuracoes criticas do Browserless:
  - headless=false  -> Obrigatorio para o Google nao bloquear
  - stealth=true    -> Obrigatorio para evitar deteccao de automacao
  - timeout=300000  -> 5 minutos para o fluxo completo

Saida:
  - state.json -> Cookies e estado da sessao para reutilizacao
"""

import os
import asyncio
import json
from urllib.parse import quote
from playwright.async_api import async_playwright
import pyotp
from dotenv import load_dotenv

load_dotenv()

# Configuracoes do Browserless
BROWSERLESS_URL = os.getenv("SERVICE_URL_BROWSERLESS")
BROWSERLESS_TOKEN = os.getenv("SERVICE_PASSWORD_BROWSERLESS")

# Credenciais Google
GOOGLE_EMAIL = os.getenv("GOOGLE_EMAIL")
GOOGLE_PASSWORD = os.getenv("GOOGLE_PASSWORD")
GOOGLE_TOTP_SECRET = os.getenv("GOOGLE_TOTP_SECRET").replace(" ", "")


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


async def login_google():
    """Executa o fluxo completo de login no Google e salva o estado da sessao."""

    cdp_url = build_cdp_url()
    print("Conectando ao Browserless (stealth=ON, headless=OFF)...")

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
        )
        page = context.pages[0] if context.pages else await context.new_page()
        page.set_default_timeout(60000)

        # --- Etapa 1: Email ---
        print("[1/4] Navegando para Google Accounts...")
        await page.goto("https://accounts.google.com/", wait_until="networkidle")

        print("[1/4] Preenchendo email...")
        await page.wait_for_selector('input[type="email"]', state="visible")
        await page.fill('input[type="email"]', GOOGLE_EMAIL)
        await page.click("#identifierNext")

        # --- Etapa 2: Senha ---
        print("[2/4] Aguardando campo de senha...")
        await page.wait_for_selector('input[name="Passwd"]', state="visible", timeout=30000)
        print("[2/4] Preenchendo senha...")
        await page.fill('input[name="Passwd"]', GOOGLE_PASSWORD)
        await asyncio.sleep(1)
        await page.click("#passwordNext")

        # --- Etapa 3: 2FA (TOTP) ---
        print("[3/4] Aguardando 2FA...")
        await asyncio.sleep(3)

        try:
            await page.wait_for_selector('input[type="tel"]', state="visible", timeout=15000)

            totp = pyotp.TOTP(GOOGLE_TOTP_SECRET)
            code = totp.now()
            print(f"[3/4] Codigo TOTP gerado: {code}")

            await page.fill('input[type="tel"]', code)
            await asyncio.sleep(1)

            next_btn = page.locator('#totpNext button, button:has-text("Next"), button:has-text("Avancar")')
            if await next_btn.count() > 0:
                await next_btn.first.click()
            else:
                await page.keyboard.press("Enter")

            await asyncio.sleep(3)
            print("[3/4] TOTP enviado!")

        except Exception as e:
            print(f"[3/4] 2FA nao solicitado ou metodo diferente: {e}")

        # --- Etapa 4: Verificar e salvar ---
        print("[4/4] Aguardando login completar...")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        current_url = page.url
        print(f"[4/4] URL final: {current_url}")

        if "myaccount.google.com" in current_url:
            print("[4/4] LOGIN REALIZADO COM SUCESSO!")
        else:
            print("[4/4] Status incerto. Verifique manualmente.")

        await context.storage_state(path="state.json")
        print("[4/4] Estado da sessao salvo em state.json")

        await browser.close()
        print("\nFinalizado.")


if __name__ == "__main__":
    asyncio.run(login_google())
