import asyncio
import os
import sys
from workflow.components.navegador import Navegador

# Ajusta o PYTHONPATH para encontrar o módulo workflow
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def generate_state():
    # Instancia nosso navegador com as técnicas de evasão
    nav = Navegador()
    
    # Sobrescrevemos o setup_browser para abrir com interface visual LOCALMENTE
    # Mas mantemos todos os argumentos de stealth
    logger = nav.setup_browser.__globals__.get('logger')
    
    print("\n" + "="*60)
    print("INICIANDO NAVEGADOR COM STEALTH (GOOGLE SAFE MODE)")
    print("="*60)
    
    from playwright.async_api import async_playwright
    nav.playwright = await async_playwright().start()
    
    # Argumentos idênticos ao navegador.py para manter a segurança
    args = [
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--start-maximized"
    ]
    
    nav.browser = await nav.playwright.chromium.launch(
        headless=False, # Precisamos ver para logar
        args=args
    )
    
    # Criamos o contexto usando as mesmas configs do navegador.py
    # Exceto o storage_state que estamos criando agora
    nav.context = await nav.browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport=None
    )
    
    # Injeta os scripts de evasão do navegador.py
    await nav.context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
    """)
    
    page = await nav.context.new_page()
    
    print("\nPASSO A PASSO:")
    print("1. O navegador vai abrir. Faça o login manualmente.")
    print("2. Resolva o 2FA no seu celular.")
    print("3. QUANDO ESTIVER LOGADO na home do SGI, NÃO FECHE O NAVEGADOR.")
    print("4. VOLTE AQUI NO TERMINAL e pressione ENTER para salvar a sessão.")
    print("="*60 + "\n")

    await page.goto("https://sgi.e-boticario.com.br/Paginas/Acesso/Entrar.aspx")

    # Em vez de esperar o browser fechar, esperamos um input no terminal
    # Isso evita o erro de "closed pipe" no Windows
    await asyncio.to_thread(input, "--> Pressione ENTER aqui quando estiver logado para salvar a sessão...")

    # Salva o estado da sessão na raiz do projeto
    state_path = os.path.join(os.path.dirname(__file__), "state.json")
    await nav.context.storage_state(path=state_path)
    
    print(f"\nSESSÃO SALVA COM SUCESSO: {state_path}")
    print("Agora você pode fechar o navegador e subir o arquivo para o GitHub!")
    
    await nav.stop_browser()

if __name__ == "__main__":
    asyncio.run(generate_state())
