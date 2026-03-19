"""
Page Object para o sistema Retaguarda.
Responsavel por login e navegacao ate a pagina de baixas.
"""

import asyncio
import os
import logging
from datetime import datetime, timezone, timedelta

# Fuso horário de Fortaleza/São Paulo (UTC-3)
TZ_BRASIL = timezone(timedelta(hours=-3))

logger = logging.getLogger(__name__)


class RetaguardaPage:
    """Page Object para interacoes com o sistema Retaguarda."""

    def __init__(self, page):
        self.page = page

    async def realizar_login(self, user: str, password: str):
        """Faz login no sistema Retaguarda."""
        url = "https://cp10356.retaguarda.grupoboticario.com.br/app/#/login" 
        logger.info(f"Navegando para {url}...")
        await self.page.goto(url, wait_until="domcontentloaded")
        
        # Garante que o campo de login está presente (usando data-cy conforme fornecido)
        await self.page.wait_for_selector('[data-cy="login-usuario-input-field"]', timeout=30000)

        logger.info("Preenchendo credenciais...")
        await self.page.fill('[data-cy="login-usuario-input-field"]', user)
        await self.page.fill('[data-cy="login-senha-input-field"]', password)

        logger.info("Clicando no botão Entrar...")        
        await asyncio.sleep(1.5)
        await self.page.click('[data-cy="login-entrar-button"]')

        logger.info("Aguardando carregamento pós-login...")
        try:
            # Espera a URL mudar para a home
            await self.page.wait_for_url("**/app/#/", timeout=60000)
            logger.info("Login realizado com sucesso.")
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"Timeout ou erro pós-login: {e}")

    async def navegar_para_baixas(self):
        """Navega ate a tela de Baixas via link direto."""
        url_baixa = "https://cp10356.retaguarda.grupoboticario.com.br/app/#/estoque/requisicao-mercadoria/cadastro"
        logger.info(f"Navegando diretamente para: {url_baixa}")
        await self.page.goto(url_baixa, wait_until="domcontentloaded")
        
        # Aguarda o formulário de requisição estar de fato renderizado na SPA
        try:
            await self.page.wait_for_selector(
                '[data-cy="select-requisicao-mercadoria-loja-input-field"]',
                state='visible',
                timeout=15000
            )
        except Exception:
            # Fallback: espera fixa caso o seletor mude
            await asyncio.sleep(3)
        
        await asyncio.sleep(1)
        logger.info("Página de Baixas (Requisicao Mercadoria) acessada.")

    async def selecionar_opcao_dropdown(self, selector_input: str, texto_opcao: str, max_tentativas: int = 3):
        """
        Auxiliar para clicar em dropdowns 'flora' e selecionar opcao.
        Possui retry: se as opções não aparecerem, re-clica no input para reabrir o dropdown.
        """
        logger.info(f"Selecionando '{texto_opcao}' no campo {selector_input}")
        option_selector = f'.flora-dropdown__option:has-text("{texto_opcao}")'

        for tentativa in range(1, max_tentativas + 1):
            try:
                # Clica no input para abrir o dropdown
                await self.page.click(selector_input)
                
                # Aguarda as opções do dropdown aparecerem de fato
                await self.page.wait_for_selector(
                    option_selector,
                    state='visible',
                    timeout=10000
                )
                
                # Clica na opção desejada
                await self.page.click(option_selector)
                await asyncio.sleep(0.5)
                return  # Sucesso, sai do loop
                
            except Exception as e:
                logger.warning(
                    f"Tentativa {tentativa}/{max_tentativas} falhou ao selecionar '{texto_opcao}' "
                    f"no campo {selector_input}: {e}"
                )
                if tentativa < max_tentativas:
                    # Fecha qualquer dropdown aberto clicando fora e aguarda antes de tentar novamente
                    await self.page.keyboard.press('Escape')
                    await asyncio.sleep(1.5)
                else:
                    raise Exception(
                        f"Falha ao selecionar '{texto_opcao}' no campo {selector_input} "
                        f"apos {max_tentativas} tentativas."
                    )

    async def preencher_cabecalho_baixa(self, nome_arquivo: str, nome_guia: str):
        """
        Preenche o cabecalho da requisicao de mercadoria (baixa).
        
        Args:
            nome_arquivo: Nome do arquivo (ex: CP8374_2026-03-16.xls)
            nome_guia: Nome da guia da planilha (ex: 'Produtos Vencidos')
        """
        # 1. Extrair codigo da loja do nome do arquivo (ex: CP8374 -> 8374)
        # Pega a parte antes do primeiro '_' e remove letras
        base_name = os.path.basename(nome_arquivo)
        codigo_loja = "".join(filter(str.isdigit, base_name.split('_')[0]))
        logger.info(f"Loja identificada no arquivo: {codigo_loja}")

        # 2. Mapear Motivo baseado na guia
        mapeamento_motivo = {
            "Avarias": "AVARIAS",
            "Brindes ou Doações": "BRINDES",
            "Demonstradores": "DEMONSTRADORES",
            "Produtos Vencidos": "PRODUTOS VENCIDOS"
        }
        # Se nao encontrar, assume AVARIAS por seguranca ou conforme pedido
        motivo_sistema = mapeamento_motivo.get(nome_guia, "AVARIAS")
        logger.info(f"Motivo mapeado da guia '{nome_guia}': {motivo_sistema}")

        # 3. Preencher Loja
        await self.selecionar_opcao_dropdown(
            '[data-cy="select-requisicao-mercadoria-loja-input-field"]', 
            codigo_loja
        )

        # 4. Preencher Local de Origem (Sempre 1 - GERAL)
        await self.selecionar_opcao_dropdown(
            '[data-cy="select-requisicao-mercadoria-local-origem-input-field"]', 
            "1 - GERAL"
        )

        # 5. Preencher Motivo
        await self.selecionar_opcao_dropdown(
            '[data-cy="select-requisicao-mercadoria-motivo-input-field"]', 
            motivo_sistema
        )

        # 6. Preencher Setor (Sempre GERAL)
        await self.selecionar_opcao_dropdown(
            '[data-cy="select-requisicao-mercadoria-setor-input-field"]', 
            "GERAL"
        )

        # 7. Preencher Observação (data completa com horário para versionamento)
        observacao = datetime.now(TZ_BRASIL).strftime("%d/%m/%Y - %H:%M")
        
        logger.info(f"Preenchendo observacao com: {observacao}")
        await self.page.fill('[data-cy="requisicao-mercadoria-observacao-input-field"]', observacao)
        
        logger.info("Cabecalho da baixa preenchido com sucesso.")

    async def adicionar_produto(self, codigo_produto: str, quantidade: str):
        """
        Adiciona um unico produto na requisicao de mercadoria.
        Assume que o modal ja esta aberto.

        Args:
            codigo_produto: Codigo do produto (ex: '250589')
            quantidade: Quantidade a transferir (ex: '2')
        """
        # Obter o locator do modal. Usamos o filter de visibilidade para garantir que pegamos o modal ativo.
        modal = self.page.locator('.flora-modal__content, [role="dialog"]').locator("visible=true").last

        # 1. Clicar no campo de busca para garantir foco e depois digitar o produto
        logger.info(f"Digitando produto: {codigo_produto}")
        campo_produto = modal.locator('[data-cy="select-list-input-field"]').first
        await campo_produto.click()
        await asyncio.sleep(0.5)
        await campo_produto.fill("")
        await campo_produto.type(codigo_produto, delay=50)

        # 2. Aguardar a lista suspensa carregar e clicar no produto
        await asyncio.sleep(1.5)
        try:
            opcao_produto = self.page.locator(f'.flora-dropdown__option:has-text("{codigo_produto}")').locator("visible=true").first
            await opcao_produto.wait_for(timeout=10000)
            await opcao_produto.click()
            logger.info(f"Produto {codigo_produto} selecionado da lista.")
        except Exception as e:
            logger.error(f"Produto {codigo_produto} nao encontrado na lista suspensa: {e}")
            raise

        await asyncio.sleep(0.5)

        # 3. Preencher quantidade transferida
        logger.info(f"Preenchendo quantidade: {quantidade}")
        campo_qtd = modal.locator('[data-cy="modal-produto-requisicao-mercadoria-qtd-transferida-input-field"]').first
        await campo_qtd.click()
        await campo_qtd.fill("")
        await campo_qtd.fill(str(quantidade))

        await asyncio.sleep(0.5)

        # 4. Clicar no botao Adicionar do modal
        botao_confirmar = modal.locator('button.flora-button--standard:has-text("Adicionar")').first
        await botao_confirmar.click()
        logger.info(f"Produto {codigo_produto} (qtd: {quantidade}) adicionado.")

        # 5. Verificar se apareceu o modal de "produto sem estoque suficiente"
        botao_continuar = '[data-cy="produto-sem-saldo-requisicao-mercadoria-continuar-button"]'
        
        try:
            # Aguarda até 4 segundos pelo alerta
            await self.page.wait_for_selector(botao_continuar, state='visible', timeout=4000)
            logger.info(f"Produto {codigo_produto} sem saldo suficiente. Confirmando continuacao...")
            await self.page.click(botao_continuar)
            # Aguarda o alerta sumir para continuar fluentemente
            await self.page.wait_for_selector(botao_continuar, state='hidden', timeout=5000)
        except Exception:
            # O timeout indica que o alerta não apareceu, então segue o fluxo normalmente
            pass

        logger.info(f"Produto {codigo_produto} processado com sucesso.")
        await asyncio.sleep(1)

    async def iterar_produtos_guia(self, produtos: list):
        """
        Itera sobre todos os produtos de uma guia e adiciona cada um.

        Args:
            produtos: Lista de dicts com 'produto' e 'quantidade'.
                      Ex: [{"produto": "250589", "quantidade": "2"}, ...]
        """
        total = len(produtos)
        logger.info(f"Iniciando iteracao de {total} produto(s)...")

        for idx, item in enumerate(produtos, start=1):
            codigo = item["produto"]
            qtd = item["quantidade"]
            logger.info(f"--- Produto {idx}/{total}: {codigo} (qtd: {qtd}) ---")

            # Clicar no botao 'Adicionar' da pagina para abrir o modal
            botao_adicionar_pagina = '[data-cy="requisicao-mercadoria-adicionar-produto-button"]'
            await self.page.click(botao_adicionar_pagina)
            logger.info("Modal de produto aberto.")
            await asyncio.sleep(1)

            # Aguardar o modal estar visivel (selector genérico para a marcação do modal)
            await self.page.wait_for_selector('.flora-modal__content, [role="dialog"]', timeout=10000)

            # Adicionar o produto dentro do modal
            await self.adicionar_produto(codigo, qtd)

        logger.info(f"Todos os {total} produto(s) foram adicionados com sucesso.")

    async def gravar_requisicao(self):
        """Clica no botao 'Gravar' para salvar a requisicao de mercadoria."""
        logger.info("Clicando em 'Gravar' para salvar a requisicao...")
        botao_gravar = '[data-cy="requisicao-mercadoria-gravar-button"]'
        await self.page.click(botao_gravar)
        
        # Aguarda o sistema processar a gravacao (algum feedback visual ou mudanca de URL)
        await asyncio.sleep(3)
        logger.info("Requisicao gravada com sucesso.")

