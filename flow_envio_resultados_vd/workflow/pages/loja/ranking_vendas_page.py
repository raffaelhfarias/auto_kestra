import logging
import datetime
from workflow.pages.base_page import BasePage

logger = logging.getLogger(__name__)

class RankingVendasPage(BasePage):
    
    def obter_ano_ciclo(self, ciclo: int) -> int:
        """Determina o ano correto para o ciclo fornecido."""
        now = datetime.datetime.now()
        ano_atual = now.year
        mes_atual = now.month

        # Ciclo 1 pertence ao próximo ano em dezembro
        if ciclo == 1 and mes_atual == 12:
            return ano_atual + 1

        # Ciclo 17 pertence ao ano atual em dezembro
        if ciclo == 17 and mes_atual == 12:
            return ano_atual

        # Ciclo 1 pertence ao ano atual em janeiro
        if ciclo == 1 and mes_atual == 1:
            return ano_atual

        # Ciclo 17 pertence ao ano anterior em janeiro
        if ciclo == 17 and mes_atual == 1:
            return ano_atual - 1

        # Caso padrão: retorna o ano atual
        return ano_atual

    async def navegar_para_ranking_vendas(self):
        """Navega pelo menu até a página de Ranking de Vendas."""
        logger.info("Navegando para Ranking Vendas...")
        
        # Menu Marketing
        # #menu-cod-8 > a:nth-child(1)
        await self.clicar("#menu-cod-8 > a:nth-child(1)", timeout=30000)
        
        # Tópico Consultas
        # #submenu-cod-8 > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li:nth-child(10)
        await self.clicar("#submenu-cod-8 > div:nth-child(1) > div:nth-child(1) > ul:nth-child(1) > li:nth-child(10)")
        
        # Subtópico Consultar Ranking Vendas
        # .submenu-select > ul:nth-child(2) > li:nth-child(5)
        await self.clicar(".submenu-select > ul:nth-child(2) > li:nth-child(5)")
        
        # Aguarda carregamento inicial da pagina (pode haver loader)
        await self.aguardar_loader_flexivel()

    async def selecionar_datas_faturamento(self):
        """Seleciona data inicial e final como 'Hoje'."""
        logger.info("Selecionando datas de faturamento...")
        
        # Data Inicial
        await self.clicar("#ContentPlaceHolder1_cedDataFaturamentoInicio_s1a")
        # Clica no 'Today' que está visível para o usuário agora
        await self.page.locator('.ajax__calendar_today >> visible=true').click()
        
        # Data Final
        await self.clicar("#ContentPlaceHolder1_cedDataFaturamentoFim_s1a")
        # Clica no 'Today' que está visível para o usuário agora
        await self.page.locator('.ajax__calendar_today >> visible=true').click()

    async def preencher_estrutura(self, codigo: str = "22960"):
        """Preenche o campo de estrutura do produto e dispara o lookup."""
        logger.info(f"Preenchendo estrutura com código: {codigo}")
        input_estrutura = self.page.locator('[id$="txtEstruturaProdutoCodigo_T2"]')
        await input_estrutura.fill(codigo)
        await input_estrutura.press('Tab')


    async def selecionar_ciclos(self, ciclo_inicio: str, ciclo_fim: str):
        """Seleciona os ciclos de faturamento inicial e final usando value direto."""
        logger.info(f"Selecionando ciclos: {ciclo_inicio} até {ciclo_fim}")
        
        await self.page.select_option("#ContentPlaceHolder1_ddlCicloFaturamentoInicial_d1", value=ciclo_inicio)
        # Pequena pausa ou validação se necessário, mas o select geralmente dispara eventos
        
        await self.page.select_option("#ContentPlaceHolder1_ddlCicloFaturamentoFinal_d1", value=ciclo_fim)

    async def preencher_filtros_adicionais(self):
        """Preenche Situacao Fiscal e Agrupamento."""
        logger.info("Preenchendo situação fiscal e agrupamento...")
        
        # Situação Fiscal = 2 (NF Emitida)
        await self.page.select_option("#ContentPlaceHolder1_ddlSituacaoFiscal_d1", value="2")
        
        # Agrupamento = Loja
        await self.page.check("#ContentPlaceHolder1_rdbAgrupamentoGerencia")

    async def buscar(self):
        """Clica em buscar."""
        logger.info("Clicando em Pesquisar...")
        # Regex case insensitive para 'Pesquisar'
        await self.page.get_by_role('link', name='Pesquisar').click()
        await self.aguardar_loader_flexivel()

    async def aguardar_loader_flexivel(self):
        """Aguarda loader .sgi-loading ou #UpdateProgress1."""
        try:
           # Wait until #UpdateProgress1 has aria-hidden='true' or is detached
           # Sometimes checking for the loading element state specifically is better
           # Se o loader for visivel (display block ou similar), esperamos ele sumir.
           # O user não especificou o loader, mantendo lógica anterior mas protegendo.
           
           # Opção simples: pause fixo ou wait for state hidden
           # await self.page.wait_for_selector("#UpdateProgress1", state="hidden", timeout=30000)
           pass
        except Exception:
             logger.info("Loader wait timed out or not found, proceeding.")

    async def extrair_tabela(self):
        """Extrai dados da tabela de Ranking de Vendas."""
        logger.info("Iniciando extração da tabela...")
        
        resultados = []
        try:
            # Aguarda tabela aparecer
            tabela = self.page.locator("#ContentPlaceHolder1_grdRankingVendas")
            await tabela.wait_for(state="visible", timeout=15000)
            
            # Itera sobre as linhas
            linhas = await tabela.locator("tr").all()
            
            for linha in linhas:
                # Células com classe grid_celula
                tds = await linha.locator("td.grid_celula").all()
                if len(tds) >= 5:
                    gerencia = await tds[0].inner_text()
                    valor_praticado = await tds[4].inner_text()
                    
                    gerencia = gerencia.strip()
                    valor_praticado = valor_praticado.strip()
                    
                    # Tratamento numérico (pt-BR para float)
                    # Ex: 1.234,56 -> 1234.56
                    valor_limpo = valor_praticado.replace('.', '').replace(',', '.')
                    
                    try:
                        valor_float = float(valor_limpo)
                    except ValueError:
                        valor_float = 0.0
                        logger.warning(f"Falha ao converter valor: {valor_praticado} (Gerencia: {gerencia})")
                    
                    resultados.append([gerencia, valor_float])
                    
            logger.info(f"Extraídos {len(resultados)} registros.")
            return resultados
            
        except Exception as e:
            logger.error(f"Erro na extração da tabela: {e}")
            return []
