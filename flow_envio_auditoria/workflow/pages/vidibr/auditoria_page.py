import logging
import asyncio
from typing import List, Dict
from playwright.async_api import Page
from ..base_page import BasePage

logger = logging.getLogger(__name__)

class VidibrAuditoriaPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        # Botão principal da Home usando data-cy fornecido
        self.btn_avaliacoes = page.locator("button[data-cy='avaliacoes-realizadas']")
        
        # Elementos do Pop-up de Jobs
        self.dialog_wrapper = page.locator(".alert-wrapper")
        self.radio_options = page.locator("button.alert-radio")
        self.radio_labels = page.locator(".alert-radio-label")
        self.btn_ok = page.locator("button.alert-button").filter(has_text="OK")
        self.btn_cancel = page.locator("button.alert-button").filter(has_text="Cancel")

    async def abrir_selecao_jobs(self):
        logger.info("Abrindo seleção de Avaliações Realizadas (data-cy)...")
        await self.btn_avaliacoes.wait_for(state="visible", timeout=15000)
        await self.btn_avaliacoes.click()
        await self.dialog_wrapper.wait_for(state="visible", timeout=15000)

    async def listar_formularios(self) -> List[str]:
        """Lista os nomes dos formulários disponíveis no pop-up."""
        logger.info("Listando formulários disponíveis no alerta...")
        # Aguarda as labels estarem presentes
        await self.radio_labels.first.wait_for(state="visible", timeout=10000)
        
        labels = await self.radio_labels.all_text_contents()
        formularios = [text.strip() for text in labels if text and text.strip().lower() != 'todos']
        
        logger.info(f"Formulários encontrados: {len(formularios)}")
        return formularios

    async def selecionar_formulario_e_entrar(self, nome_formulario: str):
        """Seleciona o formulário exato e confirma."""
        logger.info(f"Localizando rádio para: {nome_formulario}")
        
        # Localiza o botão de rádio que contém o texto da label correta
        # Estrutura: <button role="radio">...<div class="alert-radio-label">TEXTO</div>...</button>
        radio_button = self.page.locator("button.alert-radio").filter(has=self.page.locator(".alert-radio-label", has_text=nome_formulario))
        
        await radio_button.wait_for(state="visible", timeout=10000)
        await radio_button.click()
        
        # Delay de segurança para garantir a seleção (padrão Ionic)
        await asyncio.sleep(1)
        
        logger.info("Clicando em OK...")
        await self.btn_ok.click()
        
        # Aguarda o pop-up sumir e a página carregar
        await self.dialog_wrapper.wait_for(state="hidden", timeout=15000)
        await asyncio.sleep(2) # POST_CLICK_DELAY
        await self.wait_for_loader()
        await self.page.wait_for_load_state('networkidle')

    def _limpar_prefixo(self, texto: str, prefixo: str) -> str:
        """Remove o prefixo (ex: 'CNPJ:') do valor extraído."""
        if texto.lower().startswith(prefixo.lower()):
            idx = texto.lower().find(prefixo.lower()) + len(prefixo)
            return texto[idx:].strip(': ').strip()
        return texto.strip()

    async def extrair_detalhes(self) -> Dict[str, str]:
        """Extrai detalhes do formulário usando a estrutura HTML real fornecida."""
        logger.info("Iniciando extração robusta de detalhes...")
        
        # Box pergunta principal
        box = self.page.locator(".box-pergunta").first
        await box.wait_for(state="visible", timeout=20000)

        # Tenta expandir "Ver mais"
        try:
            ver_mais = self.page.locator("a").filter(has_text="Ver mais")
            if await ver_mais.count() > 0:
                await ver_mais.first.click()
                await asyncio.sleep(1)
        except: pass

        info = {}
        
        # Local Visitado (H2 com data-cy)
        local_el = box.locator('[data-cy="abrirQuestionarioJob"]')
        info['Local visitado'] = (await local_el.text_content()).strip() if await local_el.count() > 0 else 'N/E'

        # Nome da Loja (Dentro de readmore-component)
        loja_el = box.locator('[data-cy="abrirQuestionarioLoja"] div')
        info['Loja'] = (await loja_el.text_content()).strip() if await loja_el.count() > 0 else 'N/E'

        # Mapeamento de campos baseados em <span><strong>Campo:</strong> Valor</span>
        campos_mapeamento = {
            'CNPJ': 'CNPJ:',
            'Endereço': 'Endereço:',
            'Período': 'Período:',
            'Número do QT': 'Número do QT:',
            'Número da Loja': 'Número da Loja:',
            'Data da Visita': 'Data da Visita:',
            'Situação': 'Situação:'
        }
        
        for rotulo, prefixo in campos_mapeamento.items():
            try:
                # Seletor baseado na estrutura <span><strong>Campo:</strong> Valor</span>
                elemento = box.locator(f"span:has(strong:text-is('{prefixo}'))")
                if await elemento.count() > 0:
                    texto_completo = await elemento.first.text_content()
                    info[rotulo] = self._limpar_prefixo(texto_completo, prefixo)
                else:
                    # Tenta sem os dois pontos caso o HTML varie
                    prefixo_simples = prefixo.replace(':', '')
                    elemento_simples = box.locator(f"span:has(strong:text-is('{prefixo_simples}'))")
                    if await elemento_simples.count() > 0:
                        texto_completo = await elemento_simples.first.text_content()
                        info[rotulo] = self._limpar_prefixo(texto_completo, prefixo_simples)
                    else:
                        info[rotulo] = 'N/E'
            except Exception as e:
                logger.debug(f"Falha ao extrair {rotulo}: {e}")
                info[rotulo] = 'N/E'

        logger.info("Extração finalizada com sucesso!")
        return info
