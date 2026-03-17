import asyncio
import os
import glob
import logging
from pathlib import Path

# Adiciona o diretório base ao sys.path para permitir imports relativos dos componentes e páginas
import sys

# No Kestra, PYTHONPATH = flow_financeiro/baixas, e o CWD é o WorkingDirectory raiz.
# Localmente, __file__ resolve para o caminho absoluto.
IS_KESTRA = os.environ.get("KESTRA_MODE", "").lower() == "true"

if IS_KESTRA:
    # No container Kestra, o WorkingDirectory contém tudo
    BASE_DIR = Path.cwd() / "flow_financeiro" / "baixas"
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(BASE_DIR))

from workflow.components.navegador import Navegador
from workflow.components.leitor_planilha import ler_planilha_baixas
from workflow.pages.retaguarda import RetaguardaPage

# Configuração de logging básica
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Caminhos das pastas de dados
INBOX_DIR = BASE_DIR / "data" / "inbox"
PROCESSADOS_DIR = BASE_DIR / "data" / "processados"
ERRO_DIR = BASE_DIR / "data" / "erro"


async def processar_arquivo(retaguarda: RetaguardaPage, caminho_arquivo: str):
    """
    Processa um unico arquivo de baixas.
    - Guias 'Produtos Vencidos' e 'Avarias' sao unificadas em uma unica requisicao.
    - Demais guias sao processadas individualmente (cada uma gera uma requisicao separada).
    Ao final de cada lote, clica em 'Gravar'.
    """
    nome_arquivo = os.path.basename(caminho_arquivo)
    logger.info(f"=== Processando arquivo: {nome_arquivo} ===")

    # 1. Ler planilha e extrair produtos por guia
    dados_guias = ler_planilha_baixas(caminho_arquivo)

    if not dados_guias:
        logger.warning(f"Nenhum dado valido encontrado em {nome_arquivo}. Movendo para erro/.")
        return False

    # 2. Separar guias unificaveis das individuais
    GUIAS_UNIFICAVEIS = {"Produtos Vencidos", "Avarias"}
    guias_unificadas = {}
    guias_individuais = {}

    for nome_guia, produtos in dados_guias.items():
        if nome_guia in GUIAS_UNIFICAVEIS:
            guias_unificadas[nome_guia] = produtos
        else:
            guias_individuais[nome_guia] = produtos

    # 3. Processar guias unificadas (Produtos Vencidos + Avarias) em uma unica requisicao
    if guias_unificadas:
        # Junta todos os produtos das guias unificaveis
        produtos_unificados = []
        nomes_guias = []
        for nome_guia, produtos in guias_unificadas.items():
            nomes_guias.append(nome_guia)
            produtos_unificados.extend(produtos)

        logger.info(
            f"--- Processando guias unificadas: {', '.join(nomes_guias)} "
            f"({len(produtos_unificados)} produtos no total) ---"
        )

        # Navegar para a pagina de cadastro
        await retaguarda.navegar_para_baixas()

        # Preencher cabecalho usando a primeira guia como referencia para o motivo
        # Como sao unificadas, usamos a primeira guia encontrada
        guia_referencia = nomes_guias[0]
        await retaguarda.preencher_cabecalho_baixa(nome_arquivo, guia_referencia)

        # Adicionar todos os produtos de uma vez
        await retaguarda.iterar_produtos_guia(produtos_unificados)

        # Clicar em Gravar
        await retaguarda.gravar_requisicao()

        logger.info(f"Guias unificadas ({', '.join(nomes_guias)}) gravadas com sucesso.")

    # 4. Processar guias individuais (cada uma em sua propria requisicao)
    for nome_guia, produtos in guias_individuais.items():
        logger.info(f"--- Processando guia individual: {nome_guia} ({len(produtos)} produtos) ---")

        # Navegar para a pagina de cadastro (nova requisicao)
        await retaguarda.navegar_para_baixas()

        # Preencher cabecalho
        await retaguarda.preencher_cabecalho_baixa(nome_arquivo, nome_guia)

        # Iterar e adicionar todos os produtos
        await retaguarda.iterar_produtos_guia(produtos)

        # Clicar em Gravar
        await retaguarda.gravar_requisicao()

        logger.info(f"Guia '{nome_guia}' gravada com sucesso.")

    return True



async def main():
    """
    Orquestrador principal para o fluxo de Baixas no Retaguarda.
    Varre a pasta inbox/ e processa cada arquivo .xls encontrado.
    """
    # 1. Carregar variáveis de ambiente
    #    No Kestra, as credenciais vêm via env (kv store). Localmente, carrega do .env.
    if not IS_KESTRA:
        try:
            from dotenv import load_dotenv
            load_dotenv(BASE_DIR / ".env")
        except ImportError:
            logger.warning("python-dotenv não instalado, usando variáveis de ambiente do sistema.")

    user = os.environ.get("RETAGUARDA_USER")
    password = os.environ.get("RETAGUARDA_PASS")

    if not user or not password:
        logger.error("Credenciais RETAGUARDA_USER ou RETAGUARDA_PASS não encontradas.")
        return

    # Garantir que as pastas existem
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSADOS_DIR.mkdir(parents=True, exist_ok=True)
    ERRO_DIR.mkdir(parents=True, exist_ok=True)

    # === Log de contexto ===
    arquivo_id = os.environ.get("GOOGLE_ARQUIVO_ID", "")
    arquivo_nome = os.environ.get("GOOGLE_ARQUIVO_NOME", "")

    if IS_KESTRA:
        logger.info(f"=== KESTRA: Arquivo '{arquivo_nome}' (ID: {arquivo_id}) já baixado via Drive Download ===")
    else:
        logger.info("=== LOCAL: Rodando em modo local ==")

    # 2. Buscar arquivos na inbox
    arquivos = glob.glob(str(INBOX_DIR / "CP*.xls"))
    if not arquivos:
        logger.info("Nenhum arquivo encontrado na pasta inbox/. Nada a processar.")
        return

    logger.info(f"Encontrado(s) {len(arquivos)} arquivo(s) para processar.")

    # 3. Inicializar Navegador
    navegador = Navegador()
    page = await navegador.setup_browser()

    try:
        # 4. Inicializar Page Object e fazer Login
        retaguarda = RetaguardaPage(page)
        await retaguarda.realizar_login(user, password)

        # 5. Processar cada arquivo
        for caminho in arquivos:
            nome = os.path.basename(caminho)
            try:
                sucesso = await processar_arquivo(retaguarda, caminho)

                # Mover arquivo para processados/ ou erro/
                destino = PROCESSADOS_DIR if sucesso else ERRO_DIR
                destino_final = destino / nome
                os.rename(caminho, str(destino_final))
                logger.info(f"Arquivo '{nome}' movido para {destino.name}/")

            except Exception as e:
                logger.error(f"Erro ao processar '{nome}': {e}")
                # Mover para erro/
                try:
                    os.rename(caminho, str(ERRO_DIR / nome))
                    logger.info(f"Arquivo '{nome}' movido para erro/")
                except Exception:
                    logger.error(f"Falha ao mover '{nome}' para erro/")

    except Exception as e:
        logger.error(f"Erro durante a execução do fluxo: {e}")
    finally:
        # 6. Encerrar Browser
        await navegador.stop_browser()

if __name__ == "__main__":
    asyncio.run(main())

