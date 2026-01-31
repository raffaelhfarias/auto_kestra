
import csv
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
from workflow.pages.loja.ranking_vendas_page import RankingVendasPage

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
        
        # Instancia as páginas
        login_page = LoginPage(page)
        ranking_page = RankingVendasPage(page)
        
        # Navega para o link solicitado
        url = "https://sgi.e-boticario.com.br/Paginas/Acesso/Entrar.aspx?ReturnUrl=%2f"
        await login_page.navegar(url)
        
        # Realiza a interação de login
        await login_page.realizar_login_externo()

        # Realiza o login no Google
        email = os.environ.get("VD_USER")
        senha = os.environ.get("VD_PASS")
        
        if email and senha:
            # Gerar Token 2FA (Google Authenticator)
            # Secret fornecido: zebn gkh6 mejn e3et wuu7 f5ep e2lk emkd
            # Recomendável mover para variávei de ambiente VD_TOTP_SECRET posteriormente
            import pyotp
            secret = "zebngkh6mejne3etwuu7f5epe2lkemkd" 
            token_2fa = pyotp.TOTP(secret).now()
            
            await login_page.realizar_login_google(email, senha, token_2fa)
        else:
            logger.warning("Credenciais VD_USER ou VD_PASS não encontradas no .env!")
        
        # Aguarda login completar
        await page.wait_for_load_state("networkidle")
        titulo = await page.title()
        logger.info(f"Login realizado! Título atual: {titulo}")

        if "Confirme que é você" in titulo:
             logger.warning("Tela de confirmação do Google detectada! Salvando HTML para debug...")
             html_content = await page.content()
             with open("debug_google_confirmation.html", "w", encoding="utf-8") as f:
                 f.write(html_content)
             logger.info("HTML salvo em: debug_google_confirmation.html")
             # Pode ser útil tirar um screenshot também
             await page.screenshot(path="debug_google_confirmation.png")
             logger.info("Screenshot salvo em: debug_google_confirmation.png")


        # --- Fluxo de Ranking de Vendas ---
        logger.info("Iniciando fluxo de filtros...")

        configs = [
            {"tipo": "VD", "estrutura": None},
            {"tipo": "EUD", "estrutura": "22960"}
        ]

        for config in configs:
            tipo = config["tipo"]
            estrutura = config["estrutura"]
            logger.info(f"--- Iniciando extração: {tipo} ---")
        
            # 1. Navegar (Garante limpar estado/filtros anteriores)
            await ranking_page.navegar_para_ranking_vendas()
            
            # 2. Selecionar Datas (Faturamento)
            await ranking_page.selecionar_datas_faturamento()
            
            # Preencher estrutura se houver (EUD)
            if estrutura:
                await ranking_page.preencher_estrutura(estrutura)
            
            # 3. Selecionar Ciclos
            # Configurar conforme necessidade (Ex: "202602")
            ciclo_inicial_val = "202602"
            ciclo_final_val = "202602"
            await ranking_page.selecionar_ciclos(ciclo_inicial_val, ciclo_final_val)
            
            # 4. Filtros adicionais (Situação Fiscal, Agrupamento) e Buscar
            await ranking_page.preencher_filtros_adicionais()
            await ranking_page.buscar()

            # 4. Extrair e Salvar
            dados = await ranking_page.extrair_tabela()
            
            # Define caminho do arquivo
            caminho_csv = f"extracoes/resultado_filtros_{tipo}.csv"
            os.makedirs(os.path.dirname(caminho_csv), exist_ok=True)
            
            with open(caminho_csv, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Gerencia", "Valor Praticado"])
                writer.writerows(dados)
                
            logger.info(f"Dados salvos em: {caminho_csv}")



    except Exception as e:
        logger.error(f"Ocorreu um erro durante a execução: {e}")
        # Tenta tirar screenshot do erro se a página foi inicializada
        if 'page' in locals():
            try:
                await page.screenshot(path="erro_execucao.png")
                logger.info("Screenshot do erro salvo em: erro_execucao.png")
                
                # Salva também o HTML
                html_error = await page.content()
                with open("erro_execucao.html", "w", encoding="utf-8") as f:
                    f.write(html_error)
                logger.info("HTML do erro salvo em: erro_execucao.html")
            except Exception as screenshot_err:
                logger.error(f"Não foi possível salvar screenshot de erro: {screenshot_err}")

    finally:
        await navegador.stop_browser()

if __name__ == "__main__":
    asyncio.run(run())
