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
        motivo_vazio = None  # Para rastrear por que retornou vazio
        
        try:
            # Aguarda um momento para garantir estabilidade da página após busca
            await self.page.wait_for_timeout(2000)
            
            # DEBUG: Log da URL atual
            logger.info(f"[DEBUG] URL atual: {self.page.url}")
            
            # 1. Verifica se apareceu o POP-UP de "Nenhum registro encontrado"
            # O modal tem id="mensagemPanel" e o botão OK tem id="popupOkButton"
            popup_visivel = False
            try:
                await self.page.locator("#mensagemPanel").wait_for(state="visible", timeout=2000)
                popup_visivel = True
            except:
                pass  # Popup não apareceu, prosseguir
            
            if popup_visivel:
                logger.info("Pop-up de alerta detectado.")
                try:
                    # Tenta ler a mensagem para logar
                    msg = await self.extrair_texto("#mensagemLabel", timeout=1000)
                    logger.info(f"Mensagem do alerta: '{msg}'")
                    
                    # Clica em OK
                    logger.info("Clicando em OK no pop-up...")
                    await self.clicar("#popupOkButton")
                    
                    # Aguarda modal fechar para garantir que a interface está limpa
                    await self.page.locator("#mensagemPanel").wait_for(state="hidden", timeout=5000)
                    
                    motivo_vazio = "popup_nenhum_registro"
                    return []
                except Exception as e_modal:
                    logger.warning(f"Erro ao tratar pop-up: {e_modal}")


            # 2. Verificação de "Nenhum registro" removida - causava falsos positivos
            # A tabela pode existir mesmo com esse texto em outro lugar da página

            # 3. Aguarda tabela aparecer
            logger.info("Aguardando tabela de resultados...")
            tabela = self.page.locator("#ContentPlaceHolder1_grdRankingVendas")
            try:
                await tabela.wait_for(state="visible", timeout=10000)
                logger.info("[DEBUG] Tabela encontrada e visível!")
            except Exception as e_tabela:
                logger.warning(f"Tabela não apareceu no timeout: {e_tabela}")
                motivo_vazio = "tabela_nao_apareceu"
                # Salva debug
                await self._salvar_debug_extracao("tabela_timeout")
                return []
            
            # DEBUG: Pega o HTML da tabela para análise
            try:
                tabela_html = await tabela.inner_html()
                logger.info(f"[DEBUG] HTML da tabela (primeiros 1000 chars): {tabela_html[:1000]}...")
            except Exception as e_html:
                logger.warning(f"[DEBUG] Não foi possível obter HTML da tabela: {e_html}")
            
            # NOVA ABORDAGEM: Busca diretamente as células com classe grid_celula
            # e agrupa por linhas (cada linha de dados tem 6 células)
            logger.info("[DEBUG] Usando abordagem direta: buscando todas as células td.grid_celula...")
            
            todas_celulas = await tabela.locator('[class="grid_celula"]').all()
            logger.info(f"[DEBUG] Total de células grid_celula encontradas: {len(todas_celulas)}")
            
            # Se encontrou células, processa em grupos de 6 (uma linha tem 6 colunas)
            if todas_celulas:
                colunas_por_linha = 6  # Gerência, Qtd Itens, Qtd Revendedor, Faturamento, Valor Praticado, Valor Venda
                
                for i in range(0, len(todas_celulas), colunas_por_linha):
                    if i + colunas_por_linha <= len(todas_celulas):
                        # Pega as 6 células desta linha
                        celulas_linha = todas_celulas[i:i + colunas_por_linha]
                        
                        gerencia = await celulas_linha[0].inner_text()
                        valor_praticado = await celulas_linha[4].inner_text()  # Índice 4 = Valor Praticado
                        
                        gerencia = gerencia.strip()
                        valor_praticado = valor_praticado.strip()
                        
                        logger.info(f"[DEBUG] Linha {i // colunas_por_linha}: Gerencia='{gerencia}', ValorPraticado='{valor_praticado}'")
                        
                        # Tratamento numérico (pt-BR para float)
                        # Ex: 1.234,56 -> 1234.56
                        valor_limpo = valor_praticado.replace('.', '').replace(',', '.')
                        
                        try:
                            valor_float = float(valor_limpo)
                        except ValueError:
                            valor_float = 0.0
                            logger.warning(f"Falha ao converter valor: {valor_praticado} (Gerencia: {gerencia})")
                        
                        resultados.append([gerencia, valor_float])
            else:
                # FALLBACK: Tenta a abordagem antiga iterando sobre tr
                logger.info("[DEBUG] Nenhuma célula td.grid_celula encontrada. Tentando abordagem por linhas (tr)...")
                
                linhas = await tabela.locator("tbody > tr").all()
                logger.info(f"[DEBUG] Total de linhas (tbody > tr): {len(linhas)}")
                
                # Se não encontrou com tbody, tenta sem
                if not linhas:
                    linhas = await tabela.locator("tr").all()
                    logger.info(f"[DEBUG] Total de linhas (tr direto): {len(linhas)}")
                
                for i, linha in enumerate(linhas):
                    # DEBUG: Log do HTML de cada linha
                    try:
                        linha_html = await linha.inner_html()
                        logger.info(f"[DEBUG] Linha {i} HTML (primeiros 300 chars): {linha_html[:300]}...")
                    except:
                        pass
                    
                    # Tenta pegar células genéricas (td)
                    tds = await linha.locator("td").all()
                    
                    if not tds:
                        # Provavelmente é header (th)
                        ths = await linha.locator("th").all()
                        if ths:
                            logger.info(f"[DEBUG] Linha {i}: Cabeçalho detectado ({len(ths)} ths).")
                        continue

                    if len(tds) >= 5:
                        gerencia = await tds[0].inner_text()
                        valor_praticado = await tds[4].inner_text()
                        
                        gerencia = gerencia.strip()
                        valor_praticado = valor_praticado.strip()
                        
                        logger.info(f"[DEBUG] Linha {i}: Gerencia='{gerencia}', ValorPraticado='{valor_praticado}'")
                        
                        valor_limpo = valor_praticado.replace('.', '').replace(',', '.')
                        
                        try:
                            valor_float = float(valor_limpo)
                        except ValueError:
                            valor_float = 0.0
                            logger.warning(f"Falha ao converter valor: {valor_praticado} (Gerencia: {gerencia})")
                        
                        resultados.append([gerencia, valor_float])
                    else:
                        logger.warning(f"Linha {i} ignorada: Apenas {len(tds)} colunas encontradas (esperado >= 5).")
                    
            logger.info(f"Extraídos {len(resultados)} registros.")
            
            # Se extraiu 0 registros mas a tabela existia, salva debug
            if len(resultados) == 0:
                motivo_vazio = "tabela_sem_dados"
                await self._salvar_debug_extracao("tabela_vazia")
            
            return resultados
            
        except Exception as e:
            logger.error(f"Erro na extração da tabela: {e}")
            await self._salvar_debug_extracao("erro_extracao")
            return []
        finally:
            if motivo_vazio:
                logger.warning(f"[DEBUG] Extração retornou vazio. Motivo: {motivo_vazio}")
    
    async def _salvar_debug_extracao(self, prefixo: str):
        """Salva screenshot e HTML para debug quando extração falha."""
        try:
            import os
            os.makedirs("extracoes/debug", exist_ok=True)
            
            # Screenshot
            screenshot_path = f"extracoes/debug/{prefixo}_screenshot.png"
            await self.page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"[DEBUG] Screenshot salvo: {screenshot_path}")
            
            # HTML
            html_path = f"extracoes/debug/{prefixo}_page.html"
            html_content = await self.page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"[DEBUG] HTML salvo: {html_path}")
            
        except Exception as e:
            logger.error(f"[DEBUG] Falha ao salvar debug: {e}")
