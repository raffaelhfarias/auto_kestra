"""
Componente para leitura de planilhas .xls de baixas.
Le as guias relevantes e extrai produtos (coluna A) e quantidades (coluna C).
"""

import os
import logging
import xlrd

logger = logging.getLogger(__name__)

# Guias validas que devem ser processadas e seu mapeamento para o motivo no sistema
GUIAS_VALIDAS = {
    "Avarias": "AVARIAS",
    "Brindes ou Doações": "BRINDES",
    "Demonstradores": "DEMONSTRADORES",
    "Produtos Vencidos": "PRODUTOS VENCIDOS",
}


def ler_planilha_baixas(caminho_arquivo: str) -> dict:
    """
    Le uma planilha .xls e retorna os produtos de cada guia valida.

    Args:
        caminho_arquivo: Caminho absoluto para o arquivo .xls

    Returns:
        Dicionario com chave = nome da guia e valor = lista de dicts com 'produto' e 'quantidade'.
        Exemplo:
        {
            "Avarias": [
                {"produto": "250589", "quantidade": "2"},
                {"produto": "253072", "quantidade": "1"},
            ],
            "Produtos Vencidos": [
                {"produto": "253130", "quantidade": "5"},
            ]
        }
    """
    if not os.path.exists(caminho_arquivo):
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho_arquivo}")

    logger.info(f"Abrindo planilha: {caminho_arquivo}")
    workbook = xlrd.open_workbook(caminho_arquivo)

    resultado = {}

    for nome_guia in workbook.sheet_names():
        # Verifica se a guia eh valida para processamento
        if nome_guia not in GUIAS_VALIDAS:
            logger.info(f"Guia '{nome_guia}' ignorada (nao eh uma guia de baixa valida).")
            continue

        sheet = workbook.sheet_by_name(nome_guia)
        produtos = []

        # Itera pelas linhas (pula o cabecalho na linha 0)
        for row_idx in range(1, sheet.nrows):
            # Coluna A (indice 0) = codigo do produto
            cell_produto = sheet.cell_value(row_idx, 0)
            # Coluna C (indice 2) = quantidade
            cell_quantidade = sheet.cell_value(row_idx, 2)

            # Converte para string e limpa
            codigo_produto = str(cell_produto).strip()
            quantidade = str(cell_quantidade).strip()

            # Trata numeros float do Excel (ex: 250589.0 -> 250589)
            if codigo_produto.endswith(".0"):
                codigo_produto = codigo_produto[:-2]
            if quantidade.endswith(".0"):
                quantidade = quantidade[:-2]

            # Pula linhas vazias
            if not codigo_produto or not quantidade:
                logger.debug(f"Linha {row_idx + 1} da guia '{nome_guia}' vazia, pulando.")
                continue

            produtos.append({
                "produto": codigo_produto,
                "quantidade": quantidade,
            })

        if produtos:
            resultado[nome_guia] = produtos
            logger.info(f"Guia '{nome_guia}': {len(produtos)} produto(s) encontrado(s).")
        else:
            logger.warning(f"Guia '{nome_guia}' nao possui produtos validos.")

    if not resultado:
        logger.warning("Nenhuma guia valida com produtos encontrada na planilha.")

    return resultado
