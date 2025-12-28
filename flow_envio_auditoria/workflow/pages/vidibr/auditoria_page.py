import logging
import asyncio
from typing import List, Dict
from playwright.async_api import Page
from ..base_page import BasePage

logger = logging.getLogger(__name__)

class VidibrAuditoriaPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        # Botão principal da Home usando data-cy
        self.btn_avaliacoes = page.locator("button[data-cy='avaliacoes-realizadas']")
        
        # Elementos do Pop-up de Jobs
        self.dialog_wrapper = page.locator(".alert-wrapper")
        self.radio_labels = page.locator(".alert-radio-label")
        self.btn_ok = page.locator("button.alert-button").filter(has_text="OK")

    async def abrir_selecao_jobs(self):
        logger.info("Abrindo seleção de Avaliações Realizadas...")
        await self.btn_avaliacoes.wait_for(state="visible", timeout=15000)
        await self.btn_avaliacoes.click()
        # Hard wait como no modelo (POST_CLICK_DELAY)
        await asyncio.sleep(2)

    async def listar_formularios(self) -> List[str]:
        """Lista os nomes dos formulários disponíveis."""
        logger.info("Listando formulários...")
        await self.dialog_wrapper.wait_for(state="visible", timeout=15000)
        
        labels = await self.radio_labels.all_text_contents()
        formularios = [t.strip() for t in labels if t and t.strip().lower() != 'todos']
        
        logger.info(f"Formulários encontrados: {len(formularios)}")
        return formularios

    async def selecionar_formulario_e_entrar(self, nome_formulario: str):
        """Seleciona o formulário e confirma, seguindo exatamente o modelo."""
        logger.info(f"Selecionando: {nome_formulario[:50]}...")
        
        # Localiza o botão de rádio pela label
        radio = self.page.locator("button.alert-radio").filter(
            has=self.page.locator(".alert-radio-label", has_text=nome_formulario)
        )
        await radio.click()
        
        # Delay de 500ms como no modelo
        await asyncio.sleep(0.5)
        
        logger.info("Confirmando seleção (OK)...")
        await self.btn_ok.click()
        
        # POST_CLICK_DELAY de 2 segundos (CRÍTICO - seguindo modelo)
        await asyncio.sleep(2)

    def _limpar_prefixo(self, texto: str, prefixo: str) -> str:
        """Remove o prefixo do valor extraído."""
        if texto.lower().startswith(prefixo.lower()):
            return texto[len(prefixo):].strip(': ').strip()
        return texto.strip()

    async def extrair_detalhes(self) -> Dict[str, str]:
        """Extrai detalhes do formulário usando seletores do modelo."""
        logger.info("Iniciando extração de detalhes...")
        
        # Tenta expandir "Ver mais" antes de buscar o box
        try:
            ver_mais = self.page.get_by_role("link", name="Ver mais")
            if await ver_mais.count() > 0:
                await ver_mais.first.click()
                await asyncio.sleep(1)
        except: pass

        # Aguarda o box carregar (WAIT_TIMEOUT = 15s como no modelo)
        box = self.page.locator(".box-pergunta").first
        await box.wait_for(timeout=15000)

        info = {}
        
        # Local visitado
        local_el = self.page.locator('[data-cy="abrirQuestionarioJob"]')
        info['Local visitado'] = (await local_el.text_content()).strip() if await local_el.count() > 0 else ''

        # Campos com strong labels (lista do modelo)
        campos_strong = ['CNPJ', 'Endereço', 'Período', 'Número do QT', 
                         'Número da Loja', 'Data da Visita', 'Situação']
        
        for campo in campos_strong:
            try:
                elemento = box.locator(f"span:has(strong:text-is('{campo}:'))")
                if await elemento.count() > 0:
                    texto = await elemento.first.text_content()
                    info[campo] = self._limpar_prefixo(texto.strip(), f'{campo}:')
                else:
                    info[campo] = ''
            except:
                info[campo] = ''

        # Loja - dentro de readmore-component
        try:
            loja = box.locator("readmore-component > div")
            info['Loja'] = (await loja.text_content()).strip() if await loja.count() > 0 else ''
        except:
            info['Loja'] = ''

        logger.info("Detalhes extraídos com sucesso!")
        return info
