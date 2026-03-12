"""
scrapeSolides.py - Orquestrador do fluxo de extração de Banco de Horas do Solides/Tangerino.

Responsabilidades:
  1. Configurar logging (log_setup)
  2. Iniciar o navegador (navegador.py)
  3. Executar login e navegação (solides.py - Page Object)
  4. Solicitar interação do usuário (filial, datas)
  5. Preencher filtros e gerar relatório
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Adiciona a raiz do projeto ao path para imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from workflow.components.log_setup import setup_file_logging
from workflow.components.navegador import Navegador
from workflow.pages.solides import SolidesPage, FILIAIS

logger = logging.getLogger(__name__)


def solicitar_filial() -> str:
    """
    Exibe as filiais disponíveis e solicita a escolha do usuário.
    Retorna o nome da filial selecionada.
    """
    print("\n" + "=" * 60)
    print("📋 FILIAIS DISPONÍVEIS")
    print("=" * 60)

    filiais_list = list(FILIAIS.items())
    for i, (value, nome) in enumerate(filiais_list):
        marcador = "→" if value == "" else " "
        print(f"  {marcador} [{i}] {nome}")

    print("=" * 60)

    while True:
        try:
            escolha = input("\n🏢 Digite o número da filial desejada (ou Enter para 'Todas'): ").strip()
            if escolha == "":
                return "Todas"
            idx = int(escolha)
            if 0 <= idx < len(filiais_list):
                _, nome = filiais_list[idx]
                print(f"  ✅ Filial selecionada: {nome}")
                return nome
            else:
                print("  ❌ Número fora do intervalo. Tente novamente.")
        except ValueError:
            print("  ❌ Entrada inválida. Digite um número.")


def solicitar_datas() -> tuple[str, str]:
    """
    Solicita as datas de início e fim ao usuário.
    Formato: DD/MM/AAAA
    """
    print("\n" + "=" * 60)
    print("📅 PERÍODO DO RELATÓRIO")
    print("=" * 60)

    while True:
        data_inicio = input("  Data de Início (DD/MM/AAAA): ").strip()
        if len(data_inicio) == 10 and data_inicio.count("/") == 2:
            break
        print("  ❌ Formato inválido. Use DD/MM/AAAA (ex: 01/03/2026)")

    while True:
        data_fim = input("  Data Final     (DD/MM/AAAA): ").strip()
        if len(data_fim) == 10 and data_fim.count("/") == 2:
            break
        print("  ❌ Formato inválido. Use DD/MM/AAAA (ex: 31/03/2026)")

    print(f"  ✅ Período: {data_inicio} até {data_fim}")
    return data_inicio, data_fim


def processar_planilha(file_path: str) -> list[str]:
    """Lê a planilha Excel e retorna uma lista de linhas formatadas para o CSV."""
    import xlrd
    master_rows = []
    try:
        wb = xlrd.open_workbook(file_path)
        sh = wb.sheet_by_index(0)
        
        # O nome do primeiro usuário normalmente aparece na linha 4 (index 4)
        if sh.nrows > 4:
            current_name = str(sh.row_values(4)[0]).strip()
            
            for rx in range(sh.nrows):
                row = sh.row_values(rx)
                col0 = str(row[0]).strip()
                
                if 'Total Praticado Hora Excedente' in col0:
                    col_saldo_texto = str(row[6]).strip()
                    col_saldo_valor = str(row[12]).strip() if len(row) > 12 else ""
                    
                    # Nome;Saldo Acumulado até DD/MM/AAAA: HH:MM
                    master_rows.append(f"{current_name};{col_saldo_texto} {col_saldo_valor}")
                    
                    # O próximo nome geralmente está na linha seguinte após o fechamento
                    if rx + 1 < sh.nrows:
                       next_val = str(sh.row_values(rx + 1)[0]).strip()
                       if next_val and not next_val.startswith('Total'):
                           current_name = next_val
    except Exception as e:
        logger.error(f"Erro ao processar arquivo {file_path}: {e}")
    
    return master_rows


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extração de Banco de Horas Solides")
    parser.add_argument("--filial", type=str, help="Nome da filial ou 'Todas' para todas as filiais")
    parser.add_argument("--datainicio", type=str, help="Data Inicial (DD/MM/AAAA)")
    parser.add_argument("--datafim", type=str, help="Data Final (DD/MM/AAAA)")
    args = parser.parse_args()

    # ── 1. Configuração ──────────────────────────────────────
    load_dotenv(PROJECT_ROOT / ".env")
    setup_file_logging("scrapeSolides")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    user = os.environ.get("TANGERINO_USER")
    password = os.environ.get("TANGERINO_PASS")

    if not user or not password:
        logger.error("Credenciais TANGERINO_USER ou TANGERINO_PASS não configuradas no .env")
        return

    # ── 2. Interação com o usuário / Argumentos ──────────────
    print("\n" + "=" * 60)
    print("🔄 SCRAPE SOLIDES - Extração de Banco de Horas")
    print("=" * 60)

    if args.filial and args.datainicio and args.datafim:
        filial_escolhida = args.filial
        data_inicio = args.datainicio
        data_fim = args.datafim
    else:
        filial_escolhida = solicitar_filial()
        data_inicio, data_fim = solicitar_datas()

    print("\n" + "=" * 60)
    print("🚀 INICIANDO AUTOMAÇÃO")
    print(f"   Filial Escolhida:  {filial_escolhida}")
    print(f"   Período: {data_inicio} → {data_fim}")
    print("=" * 60 + "\n")

    # ── 3. Automação ─────────────────────────────────────────
    nav = Navegador()
    try:
        page = await nav.setup_browser()
        solides = SolidesPage(page)

        # 3.1 Login
        await solides.realizar_login(user, password)

        # Lista de filiais a processar
        filiais_a_processar = []
        if filial_escolhida == "Todas":
            # Pega todos os nomes do mapa, exceto o vazio ("Todas")
            filiais_a_processar = [nome for val, nome in FILIAIS.items() if val != ""]
        else:
            filiais_a_processar = [filial_escolhida]

        resultados_acumulados = []

        # Itera sobre as filiais
        for filial in filiais_a_processar:
            try:
                logger.info(f">>> Processando Filial: {filial}")
                
                # Navega até a página de relatórios
                await solides.navegar_para_banco_horas()

                # Seleciona a filial
                await solides.selecionar_filial_select2(filial)

                # Preencher datas
                await solides.preencher_datas(data_inicio, data_fim)

                # Selecionar formato Excel
                await solides.selecionar_formato_excel()

                # Gerar relatório e baixar
                file_path = await solides.gerar_relatorio()
                
                # Extrai dados desta filial
                linhas_csv = processar_planilha(file_path)
                resultados_acumulados.extend(linhas_csv)
                
                logger.info(f"✅ Filial {filial} processada. Colaboradores encontrados: {len(linhas_csv)}")
                
            except Exception as fe:
                logger.error(f"Erro ao processar filial {filial}: {fe}")
                continue

        # ── 4. Consolidação de Resultados ─────────────────────────
        qtd_total = len(resultados_acumulados)
        analise_geral = f"📋 *Análise Geral*\nTotal de Colaboradores: {qtd_total}\n"
        analise_geral += f"Período: {data_inicio} até {data_fim}"
        
        # Pasta de extrações
        extracoes_dir = "extracoes"
        os.makedirs(extracoes_dir, exist_ok=True)
        
        # Exporta TXT (Resumo para WhatsApp)
        txt_path = os.path.join(extracoes_dir, "resumo_banco_horas.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(analise_geral)
            
        # Exporta CSV (Dados unificados)
        csv_path = os.path.join(extracoes_dir, "resumo_banco_horas.csv")
        with open(csv_path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(resultados_acumulados))
            
        print("\n" + "=" * 60)
        print("✅ PROCESSO FINALIZADO!")
        print(analise_geral)
        print(f"\n📂 Arquivos gerados em: {os.path.abspath(extracoes_dir)}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Erro crítico durante a automação: {e}", exc_info=True)
    finally:
        await nav.stop_browser()


if __name__ == "__main__":
    asyncio.run(main())
