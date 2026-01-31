
import asyncio
import logging
import sys
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Adiciona o diretório raiz ao path para garantir importações corretas
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from workflow.components.navegador import Navegador
from workflow.pages.base_page import BasePage
from workflow.pages.loja.login_page import LoginPage

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def run():
    navegador = Navegador()
    try:
        # Inicializa o browser
        page = await navegador.setup_browser()
        
        # Instancia a LoginPage (que herda de BasePage)
        login_page = LoginPage(page)
        
        # Navega para o link solicitado
        url = "https://sgi.e-boticario.com.br/Paginas/Acesso/Entrar.aspx?ReturnUrl=%2f"
        await login_page.navegar(url)
        
        # Realiza a interação de login
        await login_page.realizar_login_externo()

        # Realiza o login no Google
        email = os.environ.get("VD_USER")
        senha = os.environ.get("VD_PASS")
        
        if email and senha:
            await login_page.realizar_login_google(email, senha)
        else:
            logger.warning("Credenciais VD_GMAIL ou VD_PASS não encontradas no .env!")
        
        # Verifica o título para confirmar sucesso (opcional, pode mudar pós clique)
        # As vezes o título muda ou redireciona
        await page.wait_for_load_state("domcontentloaded")
        titulo = await page.title()
        logger.info(f"Interação realizada! Título atual: {titulo}")

        # Tira um screenshot para evidência
        screenshot_path = "passo_login_externo.png"
        await page.screenshot(path=screenshot_path)
        logger.info(f"Screenshot salvo em: {screenshot_path}")

    except Exception as e:
        logger.error(f"Ocorreu um erro durante a execução: {e}")
    finally:
        await navegador.stop_browser()

if __name__ == "__main__":
    asyncio.run(run())
