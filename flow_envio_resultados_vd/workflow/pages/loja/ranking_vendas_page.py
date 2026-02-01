import logging
import datetime
from workflow.pages.base_page import BasePage

logger = logging.getLogger(__name__)

class RankingVendasPage(BasePage):
    
    # Método obter_ano_ciclo removido pois não estava sendo utilizado.

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

    async def aguardar_loader_flexivel(self, timeout: int = 60000):
        """
        Aguarda o loader #UpdateProgress1 ficar oculto.
        O elemento muda de display:none para display:block quando está carregando.
        """
        logger.info("Aguardando carregamento (loader)...")
        try:
            loader = self.page.locator("#UpdateProgress1")
            
            # Primeiro, verifica se o loader aparece (display != none)
            # Aguarda um curto período para verificar se ele apareceu
            await self.page.wait_for_timeout(500)
            
            # Aguarda até que o loader tenha display:none ou aria-hidden=true
            # Usamos uma função de espera customizada
            await self.page.wait_for_function(
                """() => {
                    const loader = document.querySelector('#UpdateProgress1');
                    if (!loader) return true; // Se não existe, prossegue
                    const style = window.getComputedStyle(loader);
                    return style.display === 'none' || loader.getAttribute('aria-hidden') === 'true';
                }""",
                timeout=timeout
            )
            logger.info("Carregamento concluído!")
            
        except Exception as e:
            logger.warning(f"Timeout ou erro ao aguardar loader: {e}. Prosseguindo...")

    async def extrair_tabela(self):
        """Extrai dados da tabela de Ranking de Vendas."""
        logger.info("Iniciando extração da tabela...")
        
        resultados = []
        try:
            # Verifica se apareceu a mensagem de "Nenhum registro" RAPIDAMENTE
            # O seletor pode variar, mas geralmente é uma div ou span com o texto
            # Vamos arriscar um check no body text ou um seletor comum de grid vazio se houver
            # Na dúvida, usamos o wait com Promise.race se fosse JS, aqui fazemos checks sequenciais com timeout curto para o negativo
            
            # Tenta verificar mensagem de vazio primeiro (timeout curto)
            if await self.page.get_by_text("Nenhum registro", exact=False).is_visible(timeout=2000):
                logger.info("Mensagem de 'Nenhum registro' detectada. Retornando lista vazia.")
                return []

            # Aguarda tabela aparecer (se não estava vazio, deve aparecer a tabela)
            tabela = self.page.locator("#ContentPlaceHolder1_grdRankingVendas")
            if await tabela.is_visible(timeout=5000): # Reduzido timeout pois já testamos o vazio
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
            else:
                logger.warning("Tabela não apareceu e nem mensagem de vazio. Verifique se houve erro no carregamento.")
                return []
            
        except Exception as e:
            logger.error(f"Erro na extração da tabela: {e}")
            return []
