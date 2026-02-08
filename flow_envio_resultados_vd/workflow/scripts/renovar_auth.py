
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
        logger.info("Iniciando processo de renovação de autenticação...")
        
        # Inicializa o browser
        page = await navegador.setup_browser()
        
        # Instancia a página de login
        login_page = LoginPage(page)
        
        # Navega para o link solicitado
        url = "https://sgi.e-boticario.com.br/Paginas/Acesso/Entrar.aspx?ReturnUrl=%2f"
        await login_page.navegar(url)
        
        # Aguarda um momento para possíveis redirecionamentos automáticos por cookie
        logger.info("Aguardando redirecionamentos automáticos...")
        await page.wait_for_timeout(5000)

        # Verifica se já está logado
        estamos_logados = False
        try:
             current_url = page.url.lower()
             title = await page.title()
             logger.info(f"URL atual: {current_url}")
             logger.info(f"Título atual: {title}")

             # Se saiu da tela de login ou foi para uma tela de "Aguardar" ou Dashboard
             if "entrar.aspx" not in current_url and "account/login" not in current_url:
                 estamos_logados = True
                 logger.info("URL mudou (não é mais login). Assumindo logado.")
             elif "aguardaracao" in current_url:
                 estamos_logados = True
                 logger.info("Redirecionado para AguardarAcao. Assumindo logado.")
             else:
                 # URL ainda parece ser de login, mas pode ser um falso negativo (estado restaurado)
                 logger.info("URL ainda é de login. Verificando se botão de login está visível...")
                 botao_login_visivel = await login_page.is_login_button_visible()
                 if not botao_login_visivel:
                     estamos_logados = True
                     logger.info("Botão de login NÃO está visível. Assumindo que sessão foi restaurada com sucesso!")

             # Verifica presença de elementos da Home se ainda estiver na dúvida
             # Exemplo: Menu "Força de Vendas"
             if not estamos_logados:
                 try:
                    # Pequeno timeout para check rápido
                    if await page.get_by_text("Força de Vendas").is_visible(timeout=5000):
                        estamos_logados = True
                        logger.info("Elemento 'Força de Vendas' encontrado. Estamos logados!")
                 except:
                    pass

        except Exception as e:
             logger.warning(f"Erro ao verificar estado de login: {e}")

        if estamos_logados:
             logger.info("Já estamos logados! Sessão válida.")

        if not estamos_logados:
            logger.info("Sessão expirada. Realizando novo login...")
            # Realiza a interação de login
            nova_pagina = await login_page.realizar_login_externo()
            
            # Se uma nova aba foi aberta, atualiza todas as referências de página
            if nova_pagina:
                page = nova_pagina
                navegador.update_page(page)  # Atualiza também no navegador
                login_page.page = page
                logger.info("Página de login atualizada para a nova aba.")

            # --- RE-VERIFICAÇÃO DE LOGIN ---
            logger.info("Login externo acionado. Aguardando possíveis redirecionamentos (SSO)...")
            await page.wait_for_timeout(5000)

            current_url = page.url.lower()
            
            # Verifica se estamos em uma página que indica login bem-sucedido
            # IMPORTANTE: accounts.google.com significa que AINDA precisamos fazer login no Google!
            url_e_google = "accounts.google.com" in current_url
            url_e_login_sgi = "entrar.aspx" in current_url or "account/login" in current_url
            url_e_aguardaracao = "aguardaracao" in current_url
            url_e_dashboard_sgi = "sgi.e-boticario.com.br" in current_url and not url_e_login_sgi
            
            logger.info(f"URL atual: {current_url}")
            logger.info(f"É Google: {url_e_google}, É login SGI: {url_e_login_sgi}, É AguardarAcao: {url_e_aguardaracao}, É Dashboard SGI: {url_e_dashboard_sgi}")
            
            if url_e_aguardaracao or url_e_dashboard_sgi:
                 logger.info("Redirecionamento para SGI detectado. Login já realizado via SSO!")
                 estamos_logados = True
            elif url_e_google:
                 logger.info("Estamos na tela de login do Google. Precisamos realizar autenticação...")
                 # NÃO marcar como logado - precisamos continuar com o login do Google
            else:
                 logger.info(f"URL não reconhecida. Tentando prosseguir com login Google...")
            
            if not estamos_logados:
                # Realiza o login no Google apenas se AINDA não estivermos logados
                email = os.environ.get("VD_USER")
                senha = os.environ.get("VD_PASS")
                
                if email and senha:
                    logger.info(f"Credenciais encontradas. Realizando login com: {email}")
                    await login_page.realizar_login_google(email, senha)
                    
                    # Aguarda login completar
                    await page.wait_for_load_state("networkidle")
                    titulo = await page.title()
                    logger.info(f"Login Google realizado! Título atual: {titulo}")
                    
                    # Check para tela de confirmação google
                    if "Confirme que é você" in titulo:
                         logger.warning("Tela de confirmação do Google detectada!")
                         await page.screenshot(path="debug_google_confirmation_renova.png")
                else:
                    logger.warning("Credenciais VD_USER ou VD_PASS não encontradas no ambiente!")

        # --- TRATAMENTO AGUARDAR AÇÃO / VALIDAÇÃO FINAL ---
        # Se estivermos na página de AguardarAcao, devemos esperar ela sair.
        if "aguardaracao" in page.url.lower():
            logger.info("Detectado página AguardarAcao. Aguardando redirecionamento final para garantir cookie válido...")
            try:
                # O mais seguro é esperar pelo carregamento do Menu Principal
                await page.wait_for_selector("#menu-cod-4", state="visible", timeout=60000)
                logger.info("Dashboard carregado! Sessão renovada com sucesso.")
            except Exception as e:
                logger.warning(f"Timeout aguardando Dashboard/Menu. Sessão pode não ter sido totalmente estabelecida. Erro: {e}")
        else:
            # Se não for AguardarAcao, pode ser que já esteja no Dashboard, vamos tentar validar
            # Aguarda um tempo incondicional para processamento de login/scripts da página
            logger.info("Aguardando 15 segundos para estabilização da página...")
            await page.wait_for_timeout(15000)

            try:
                if await page.get_by_text("Força de Vendas").is_visible(timeout=60000):
                    logger.info("Dashboard verificado via texto 'Força de Vendas'.")
                else:
                     logger.info("Elemento 'Força de Vendas' não encontrado após 60s")
            except:
                logger.info("Não foi possível confirmar visualmente o Dashboard, mas prosseguindo com salvamento de estado.")

        logger.info("Finalizando processo de renovação...")

    except Exception as e:
        logger.error(f"Ocorreu um erro durante a renovação da autenticação: {e}")
        # Tenta tirar screenshot do erro
        if 'page' in locals():
            try:
                await page.screenshot(path="erro_renovacao_auth.png")
                logger.info("Screenshot do erro salvo em: erro_renovacao_auth.png")
            except Exception:
                pass

    finally:
        # salva estado atualizado
        logger.info("Salvando estado da sessão (cookies/storage)...")
        try:
            await navegador.save_state()
            logger.info("Estado salvo com sucesso em state.json")
        except Exception as save_err:
            logger.error(f"Erro ao salvar estado da sessão: {save_err}")
        
        await navegador.stop_browser()

if __name__ == "__main__":
    asyncio.run(run())
