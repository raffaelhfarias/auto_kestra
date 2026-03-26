"""
Page Object para a página IAF Consolidated Summary.
Extrai dados de Panorama, Pilares e Indicadores do Programa.
"""

import logging
import time
import re
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class IAFPage:
    """Extrai todos os dados da página IAF Consolidated Summary."""

    def __init__(self, page: Page):
        self.page = page

    async def fechar_modal_satisfacao(self):
        """Fecha o modal de pesquisa de satisfação do IAF, se aparecer."""
        logger.info("Aguardando o modal de satisfação surgir (até 8 segundos)...")
        
        # Como "satisfação" pode ter problemas de encoding, buscamos "dashboard de IAF" que faz parte da mesma frase
        modal_loc = self.page.locator("div[role='dialog'][data-flora='modal-content']:has-text('dashboard de IAF')")
        
        try:
            await modal_loc.first.wait_for(state="visible", timeout=8000)
            logger.info("Modal de satisfação detectado. Fechando...")
            
            close_btn = modal_loc.first.locator("button[data-flora='modal-close']")
            if await close_btn.count() > 0:
                await close_btn.first.click()
                logger.info("Modal fechado via botão de fechar.")
            else:
                await self.page.keyboard.press("Escape")
                logger.info("Modal fechado via Escape.")
            
            # Aguardar o modal desaparecer
            await modal_loc.first.wait_for(state="hidden", timeout=5000)
            logger.info("Tratamento do modal de satisfação concluído.")
        except Exception:
            logger.info("Nenhum modal de satisfação encontrado no tempo limite. Continuando fluxo.")

    async def aguardar_carregamento(self, timeout: int = 15000):
        """Aguarda a tabela de indicadores carregar na página."""
        logger.info("Aguardando carregamento da tabela de indicadores...")
        await self.fechar_modal_satisfacao()
        await self.page.wait_for_selector("#IAFConsolidatedIndicators", timeout=timeout)
        await self.page.wait_for_timeout(2000)
        logger.info("Tabela de indicadores carregada.")

    async def extrair_data_atualizacao(self) -> str:
        """Extrai a data de atualização exibida no dashboard IAF."""
        logger.info("Extraindo data de atualização...")
        try:
            seletor = "span.sc-dlWCHZ"
            await self.page.wait_for_selector(seletor, timeout=5000)
            elemento = self.page.locator(seletor).first
            texto = await elemento.inner_text()
            logger.info(f"Data de atualização extraída: '{texto.strip()}'")
            return texto.strip()
        except Exception as e:
            logger.warning(f"Erro ao extrair data de atualização: {e}")
            return "N/D"

    async def extrair_panorama(self) -> dict:
        """Extrai os dados da seção Panorama (pontuação, classificação, rankings)."""
        logger.info("Extraindo dados do Panorama...")
        panorama = {}

        # Pontuação do CP (ex: "587,30 pts")
        try:
            pontuacao_el = self.page.locator("span:has-text('Pontuação do CP')").first
            await pontuacao_el.wait_for(state="visible", timeout=5000)

            # O valor da pontuação está logo após o título, dentro de um <p> com classe faOdEG
            container = pontuacao_el.locator("..").locator("..")
            valor_pontuacao = await container.locator("p.flora--c-PJLV-faOdEG-cv").first.inner_text()
            panorama["pontuacao_cp"] = valor_pontuacao.strip()
        except Exception as e:
            logger.warning(f"Erro ao extrair pontuação do CP: {e}")
            panorama["pontuacao_cp"] = "N/D"

        # Calcular Classificação e Percentual a partir da pontuação
        META_CP = 915.0
        try:
            if panorama["pontuacao_cp"] != "N/D":
                # Limpa a string (ex: "587,30 pts" ou "1.587,30")
                num_str = panorama["pontuacao_cp"].replace(" pts", "").replace(" pts.", "").replace(".", "").replace(",", ".")
                pontos_float = float(num_str)
                atingimento_pct = pontos_float / META_CP
                
                panorama["classificacao_pct"] = f"{(atingimento_pct * 100):.2f}%".replace(".", ",")
                
                if atingimento_pct >= 0.95:
                    panorama["classificacao"] = "Diamante"
                elif atingimento_pct >= 0.85:
                    panorama["classificacao"] = "Ouro"
                elif atingimento_pct >= 0.75:
                    panorama["classificacao"] = "Prata"
                elif atingimento_pct >= 0.65:
                    panorama["classificacao"] = "Bronze"
                else:
                    panorama["classificacao"] = "Sem classificação"
            else:
                panorama["classificacao"] = "N/D"
                panorama["classificacao_pct"] = "N/D"
        except Exception as e:
            logger.warning(f"Erro ao calcular classificação: {e}")
            panorama["classificacao"] = "N/D"
            panorama["classificacao_pct"] = "N/D"

        # Rankings (Brasil, Regional, MUSK/Clube)
        panorama["rankings"] = {}
        try:
            cards_ranking = self.page.locator("[data-flora='card'] .flora--c-PJLV-blyrBC-cv")
            count = await cards_ranking.count()
            labels_ranking = self.page.locator("[data-flora='card'] .flora--c-PJLV-faOdEG-cv")

            for i in range(count):
                label = (await labels_ranking.nth(i).inner_text()).strip()
                valor = (await cards_ranking.nth(i).inner_text()).strip()
                panorama["rankings"][label] = valor
        except Exception as e:
            logger.warning(f"Erro ao extrair rankings: {e}")

        logger.info(f"Panorama extraído: {panorama}")
        return panorama

    async def extrair_pilares(self) -> list:
        """Extrai os dados da seção Pilares."""
        logger.info("Extraindo dados dos Pilares...")
        pilares = []

        try:
            cards = self.page.locator("div[data-flora='card'].flora--c-jAOGHF-iZiwDu-css")
            count = await cards.count()
            logger.info(f"Encontrados {count} cards de pilares.")

            for i in range(count):
                card = cards.nth(i)
                pilar = {}

                # Nome do pilar
                try:
                    nome = await card.locator("p.flora--c-PJLV-iimjeqz-css").first.inner_text()
                    pilar["nome"] = nome.strip()
                except Exception:
                    pilar["nome"] = "N/D"

                # Pontos atuais
                try:
                    pontos = await card.locator("p.flora--c-PJLV-faOdEG-cv").first.inner_text()
                    pilar["pontos"] = pontos.strip()
                except Exception:
                    pilar["pontos"] = "N/D"

                # Meta
                try:
                    meta = await card.locator("p.flora--c-PJLV-idVWDIH-css").first.inner_text()
                    pilar["meta"] = meta.strip()
                except Exception:
                    pilar["meta"] = "N/D"

                # Atingimento e Falta p/ Meta (dentro dos tags)
                try:
                    tags = card.locator("span[data-flora='tag'] p")
                    tag_count = await tags.count()
                    if tag_count >= 2:
                        pilar["atingimento"] = (await tags.nth(0).inner_text()).strip()
                        pilar["falta_meta"] = (await tags.nth(1).inner_text()).strip()
                    elif tag_count == 1:
                        pilar["atingimento"] = (await tags.nth(0).inner_text()).strip()
                        pilar["falta_meta"] = "N/D"
                    else:
                        pilar["atingimento"] = "N/D"
                        pilar["falta_meta"] = "N/D"
                except Exception:
                    pilar["atingimento"] = "N/D"
                    pilar["falta_meta"] = "N/D"

                pilares.append(pilar)

        except Exception as e:
            logger.error(f"Erro ao extrair pilares: {e}")

        logger.info(f"Pilares extraídos: {len(pilares)}")
        return pilares

    async def extrair_indicadores(self) -> list:
        """Extrai os dados da tabela de Indicadores do Programa."""
        logger.info("Extraindo dados dos Indicadores do Programa...")
        indicadores = []

        try:
            linhas = self.page.locator("#IAFConsolidatedIndicators .ant-table-body .ant-table-row")
            count = await linhas.count()
            logger.info(f"Encontradas {count} linhas de indicadores.")

            for i in range(count):
                linha = linhas.nth(i)
                indicador = {}

                colunas = linha.locator("td.ant-table-cell")

                # Coluna 0 - Nome do indicador (texto do link)
                try:
                    indicador["nome"] = (await colunas.nth(0).inner_text()).strip()
                except Exception:
                    indicador["nome"] = "N/D"

                # Coluna 1 - Habilitador
                try:
                    indicador["habilitador"] = (await colunas.nth(1).inner_text()).strip()
                except Exception:
                    indicador["habilitador"] = "N/D"

                # Coluna 2 - Realizado
                try:
                    indicador["realizado"] = (await colunas.nth(2).inner_text()).strip()
                except Exception:
                    indicador["realizado"] = "N/D"

                # Coluna 3 - Atingimento (pontos + %)
                try:
                    indicador["atingimento"] = (await colunas.nth(3).inner_text()).strip()
                except Exception:
                    indicador["atingimento"] = "N/D"

                # Coluna 4 - Meta (pontos + valor)
                try:
                    indicador["meta"] = (await colunas.nth(4).inner_text()).strip()
                except Exception:
                    indicador["meta"] = "N/D"

                # Coluna 5 - Falta p/ Meta (pontos + %)
                try:
                    indicador["falta_meta"] = (await colunas.nth(5).inner_text()).strip()
                except Exception:
                    indicador["falta_meta"] = "N/D"

                indicadores.append(indicador)

        except Exception as e:
            logger.error(f"Erro ao extrair indicadores: {e}")

        logger.info(f"Indicadores extraídos: {len(indicadores)}")
        return indicadores

    async def extrair_tudo(self) -> dict:
        """Extrai todos os dados da página IAF e retorna um dicionário consolidado."""
        await self.aguardar_carregamento()

        panorama = await self.extrair_panorama()
        pilares = await self.extrair_pilares()
        
        # Corrigir o panorama utilizando a soma dos pilares (se houver variação do site)
        try:
            soma_pontos = 0.0
            for p in pilares:
                pontos_str = p.get("pontos", "0")
                match_pts = re.search(r'([\d\.,]+)\s*pts?', pontos_str) if pontos_str and pontos_str != "N/D" else None
                if match_pts:
                    num_str = match_pts.group(1).replace('.', '').replace(',', '.')
                    try:
                        soma_pontos += float(num_str)
                    except ValueError:
                        pass
            
            if soma_pontos > 0:
                META_CP = 915.0
                atingimento_pct = soma_pontos / META_CP
                
                panorama["pontuacao_cp"] = f"{soma_pontos:.2f} pts".replace('.', ',')
                panorama["classificacao_pct"] = f"{(atingimento_pct * 100):.2f}%".replace(".", ",")
                
                if atingimento_pct >= 0.95:
                    panorama["classificacao"] = "Diamante"
                elif atingimento_pct >= 0.85:
                    panorama["classificacao"] = "Ouro"
                elif atingimento_pct >= 0.75:
                    panorama["classificacao"] = "Prata"
                elif atingimento_pct >= 0.65:
                    panorama["classificacao"] = "Bronze"
                else:
                    panorama["classificacao"] = "Não classificado"
        except Exception as e:
            logger.warning(f"Erro ao recalcular panorama pela soma de pilares: {e}")

        dados = {
            "data_atualizacao": await self.extrair_data_atualizacao(),
            "panorama": panorama,
            "pilares": pilares,
            "indicadores": await self.extrair_indicadores(),
        }

        return dados

    @staticmethod
    def gerar_markdown(dados: dict) -> str:
        """Gera um arquivo Markdown estruturado a partir dos dados extraídos."""
        data_atualizacao_raw = dados.get("data_atualizacao", "N/D")
        match_dt = re.search(r'(\d{2}/\d{2}/\d{4})[^\d]*(\d{2}:\d{2})', data_atualizacao_raw)
        if match_dt:
            data_hora = f"{match_dt.group(1)} {match_dt.group(2)}"
        else:
            if data_atualizacao_raw != "N/D" and data_atualizacao_raw:
                data_hora = data_atualizacao_raw
            else:
                data_hora = time.strftime("%d/%m/%Y %H:%M", time.localtime())

        linhas = []

        linhas.append(f"# Resumo IAF Consolidado")
        linhas.append(f"> Dashboard atualizado em: {data_hora}")
        linhas.append("")

        # Panorama
        pan = dados.get("panorama", {})
        pilares = dados.get("pilares", [])
        
        # Calcular pontuação do CP como soma dos pontos dos pilares
        soma_pontos = 0.0
        for p in pilares:
            pontos_str = p.get("pontos", "0")
            match_pts = re.search(r'([\d\.,]+)\s*pts?', pontos_str) if pontos_str and pontos_str != "N/D" else None
            if match_pts:
                num_str = match_pts.group(1).replace('.', '').replace(',', '.')
                try:
                    soma_pontos += float(num_str)
                except ValueError:
                    pass
        
        if soma_pontos == int(soma_pontos):
            pontuacao_fmt = f"{int(soma_pontos)} pts"
        else:
            pontuacao_fmt = f"{soma_pontos:.2f} pts".replace('.', ',')
        
        linhas.append("## Panorama")
        linhas.append(f"- **Pontuação do CP:** {pontuacao_fmt}")
        linhas.append(f"- **Classificação:** {pan.get('classificacao', 'N/D')} ({pan.get('classificacao_pct', 'N/D')})")
        linhas.append("")

        rankings = pan.get("rankings", {})
        if rankings:
            linhas.append("### Rankings")
            for label, valor in rankings.items():
                linhas.append(f"- **{label}:** {valor}")
            linhas.append("")

        # Pilares
        if pilares:
            linhas.append("## Pilares")
            linhas.append("| Pilar | Pontos | Meta | Atingimento | Falta p/ Meta |")
            linhas.append("|---|---|---|---|---|")
            for p in pilares:
                linhas.append(f"| {p['nome']} | {p['pontos']} | {p['meta']} | {p['atingimento']} | {p['falta_meta']} |")
            linhas.append("")

        # Indicadores
        indicadores = dados.get("indicadores", [])
        if indicadores:
            linhas.append("## Indicadores do Programa")
            linhas.append("| Indicador | Habilitador | Realizado | Atingimento | Meta | Falta p/ Meta |")
            linhas.append("|---|---|---|---|---|---|")
            for ind in indicadores:
                # Substitui as quebras de linha dentro do texto por "<br>" para não quebrar a tabela Markdown
                atingimento = ind.get('atingimento', '').replace('\n', ' <br> ')
                meta = ind.get('meta', '').replace('\n', ' <br> ')
                falta_meta = ind.get('falta_meta', '').replace('\n', ' <br> ')
                
                linhas.append(
                    f"| {ind.get('nome', 'N/D')} | {ind.get('habilitador', 'N/D')} | {ind.get('realizado', 'N/D')} | "
                    f"{atingimento} | {meta} | {falta_meta} |"
                )
            linhas.append("")

        return "\n".join(linhas)
