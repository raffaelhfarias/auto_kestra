"""
extrair_folha.py - Extração de dados da Folha de Pagamento (PDF → CSV)

Extrai NOME, CPF e LÍQUIDO de cada colaborador do PDF de folha de pagamento.
Gera um CSV com separador `;` pronto para importação em planilha modelo.

Uso:
    python extrair_folha.py --pdf "FOLHA DE PAGAMENTO.pdf"
    python extrair_folha.py --pdf "FOLHA DE PAGAMENTO.pdf" --output "resultado.csv"
"""

import argparse
import csv
import re
import sys
from pathlib import Path

import pdfplumber


# ── Regex Patterns ────────────────────────────────────────────────────────────

# Cabeçalho de colaborador: "NUM NOME NUM NUM Admissão em DD/MM/AAAA ..."
RE_COLABORADOR = re.compile(
    r"^\d+\s+"                        # Número do colaborador
    r"([A-ZÁÀÂÃÉÈÊÍÏÓÔÕÚÜÇ\s]+?)"     # NOME (letras maiúsculas + espaços)
    r"\s+\d+\s+\d+\s+"                # SF IR (dois números)
    r"Admiss",                         # Início "Admissão em..."
    re.UNICODE
)

# CPF: "CPF: 097.810.854-01"
RE_CPF = re.compile(r"CPF:\s*(\d{3}\.\d{3}\.\d{3}-\d{2})")

# Líquido: "Líquido -> 6.370,39" (aceita encoding com ou sem acento)
RE_LIQUIDO = re.compile(r"L[ií]quido\s*-\s*>\s*([\d.,]+)", re.IGNORECASE)

# Empresa: "Empresa: 15584 - TEJUCUPAPO PERFUMES LTDA ME Goiana/PE - CNPJ:..."
RE_EMPRESA = re.compile(
    r"Empresa:\s*\d+\s*-\s*"          # "Empresa: 15584 - "
    r"(.+?)"                           # Nome da empresa
    r"\s+\S+/\S+\s*-\s*CNPJ:",       # "Goiana/PE - CNPJ:"
    re.UNICODE
)


# ── Funções de Extração ──────────────────────────────────────────────────────

def extrair_texto_completo(pdf_path: str) -> str:
    """Extrai o texto de todas as páginas do PDF, concatenando-as."""
    texto_paginas = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                texto_paginas.append(text)
    return "\n".join(texto_paginas)


def extrair_nome_empresa(texto: str) -> str | None:
    """Extrai o nome da empresa do cabeçalho do PDF."""
    match = RE_EMPRESA.search(texto)
    if match:
        return match.group(1).strip()
    return None


def extrair_colaboradores(texto: str) -> list[dict]:
    """
    Extrai os dados de cada colaborador a partir do texto do PDF.
    
    Estratégia: percorre linha a linha, detectando o início de cada bloco
    de colaborador (pelo padrão NOME + Admissão). Dentro do bloco, busca
    CPF e Líquido. Cada Líquido fecha o bloco atual.
    """
    colaboradores = []
    linhas = texto.split("\n")

    nome_atual = None
    cpf_atual = None

    for linha in linhas:
        # 1. Detectar novo colaborador
        match_colab = RE_COLABORADOR.search(linha)
        if match_colab:
            nome_atual = match_colab.group(1).strip()
            cpf_atual = None  # Reset CPF para novo bloco
            continue

        # 2. Detectar CPF (pode estar na mesma ou próxima linha)
        match_cpf = RE_CPF.search(linha)
        if match_cpf and nome_atual:
            cpf_atual = match_cpf.group(1)
            continue

        # 3. Detectar Líquido (fecha o bloco do colaborador)
        match_liquido = RE_LIQUIDO.search(linha)
        if match_liquido and nome_atual and cpf_atual:
            liquido = match_liquido.group(1)

            colaboradores.append({
                "nome": nome_atual,
                "cpf": cpf_atual,
                "liquido": liquido,
            })

            # Reset para próximo colaborador
            nome_atual = None
            cpf_atual = None

    return colaboradores


def validar_dados(colaboradores: list[dict]) -> bool:
    """Valida integridade dos dados extraídos."""
    ok = True

    if not colaboradores:
        print("❌ ERRO: Nenhum colaborador encontrado!", file=sys.stderr)
        return False

    for i, c in enumerate(colaboradores, 1):
        erros = []
        if not c["nome"]:
            erros.append("nome vazio")
        if not re.match(r"\d{3}\.\d{3}\.\d{3}-\d{2}", c["cpf"]):
            erros.append(f"CPF inválido: {c['cpf']}")
        if not c["liquido"]:
            erros.append("líquido vazio")

        if erros:
            print(f"❌ Colaborador #{i}: {', '.join(erros)}", file=sys.stderr)
            ok = False

    return ok


def gerar_csv(colaboradores: list[dict], output_path: str) -> None:
    """Gera arquivo CSV com separador `;` e encoding UTF-8 BOM."""
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, 
            fieldnames=["nome", "cpf", "liquido"],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(colaboradores)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extrai Nome, CPF e Líquido da Folha de Pagamento (PDF)"
    )
    parser.add_argument(
        "--pdf", required=True, type=str,
        help="Caminho do PDF da folha de pagamento"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Caminho do CSV de saída (padrão: folha_pagamento.csv no mesmo diretório)"
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"❌ Arquivo não encontrado: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # ── 1. Extração ──────────────────────────────────────────────
    print(f"📄 Lendo PDF: {pdf_path.name}")
    texto = extrair_texto_completo(str(pdf_path))

    # Extrair nome da empresa para nomear o CSV
    nome_empresa = extrair_nome_empresa(texto)
    if nome_empresa:
        print(f"🏢 Empresa: {nome_empresa}")

    # Definir output padrão
    if args.output:
        output_path = Path(args.output).resolve()
    elif nome_empresa:
        # Sanitiza o nome para uso em arquivo (remove caracteres inválidos)
        nome_arquivo = re.sub(r'[<>:"/\\|?*]', '', nome_empresa)
        output_path = pdf_path.parent / f"{nome_arquivo}.csv"
    else:
        output_path = pdf_path.parent / "folha_pagamento.csv"

    # ── 2. Parsing ───────────────────────────────────────────────

    colaboradores = extrair_colaboradores(texto)

    # ── 3. Validação ─────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"📋 COLABORADORES EXTRAÍDOS: {len(colaboradores)}")
    print(f"{'='*60}")

    for i, c in enumerate(colaboradores, 1):
        print(f"  {i}. {c['nome']}")
        print(f"     CPF: {c['cpf']}")
        print(f"     Líquido: R$ {c['liquido']}")
        print()

    if not validar_dados(colaboradores):
        print("⚠️  Validação falhou. Revise o PDF.", file=sys.stderr)
        sys.exit(1)

    # ── 4. Verificação do total ──────────────────────────────
    # Converte líquido BR (1.234,56) para float
    total = sum(
        float(c["liquido"].replace(".", "").replace(",", "."))
        for c in colaboradores
    )
    print(f"💰 Total Líquido: R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # ── 5. Geração do CSV ────────────────────────────────────
    gerar_csv(colaboradores, str(output_path))
    print(f"\n✅ CSV gerado: {output_path}")


if __name__ == "__main__":
    main()
