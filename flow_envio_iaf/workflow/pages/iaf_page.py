"""
Page Object para a página IAF Consolidated Summary.
Extrai dados de Panorama, Pilares e Indicadores do Programa.
"""

import logging
import time
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class IAFPage:
    """Extrai todos os dados da página IAF Consolidated Summary."""

    def __init__(self, page: Page):
        self.page = page

    async def aguardar_carregamento(self, timeout: int = 15000):
        """Aguarda a tabela de indicadores carregar na página."""
        logger.info("Aguardando carregamento da tabela de indicadores...")
        await self.page.wait_for_selector("#IAFConsolidatedIndicators", timeout=timeout)
        await self.page.wait_for_timeout(2000)
        logger.info("Tabela de indicadores carregada.")

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

        # Classificação (ex: "Não classificado")
        try:
            classificacao_el = self.page.locator("[data-flora='tag'][data-flora-text='Não classificado']").first
            classificacao = await classificacao_el.inner_text()
            panorama["classificacao"] = classificacao.strip()
        except Exception:
            try:
                # Tentar pegar qualquer tag de classificação no contexto de Panorama
                classificacao = await self.page.locator(".ant-space-item span[data-flora='tag']").first.inner_text()
                panorama["classificacao"] = classificacao.strip()
            except Exception as e:
                logger.warning(f"Erro ao extrair classificação: {e}")
                panorama["classificacao"] = "N/D"

        # Percentual de classificação (ex: "63,84%")
        try:
            pct_el = self.page.locator("span.sc-cHMHOW").first
            panorama["classificacao_pct"] = (await pct_el.inner_text()).strip()
        except Exception as e:
            logger.warning(f"Erro ao extrair % classificação: {e}")
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

        dados = {
            "panorama": await self.extrair_panorama(),
            "pilares": await self.extrair_pilares(),
            "indicadores": await self.extrair_indicadores(),
        }

        return dados

    @staticmethod
    def gerar_markdown(dados: dict) -> str:
        """Gera um arquivo Markdown estruturado a partir dos dados extraídos."""
        ts = time.strftime("%d/%m/%Y %H:%M", time.localtime())
        linhas = []

        linhas.append(f"# Resumo IAF Consolidado")
        linhas.append(f"> Extraído automaticamente em {ts}")
        linhas.append("")

        # Panorama
        pan = dados.get("panorama", {})
        linhas.append("## Panorama")
        linhas.append(f"- **Pontuação do CP:** {pan.get('pontuacao_cp', 'N/D')}")
        linhas.append(f"- **Classificação:** {pan.get('classificacao', 'N/D')} ({pan.get('classificacao_pct', 'N/D')})")
        linhas.append("")

        rankings = pan.get("rankings", {})
        if rankings:
            linhas.append("### Rankings")
            for label, valor in rankings.items():
                linhas.append(f"- **{label}:** {valor}")
            linhas.append("")

        # Pilares
        pilares = dados.get("pilares", [])
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
