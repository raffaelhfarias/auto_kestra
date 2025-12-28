import logging
import asyncio
from typing import List, Dict
from playwright.async_api import Page
from ..base_page import BasePage

logger = logging.getLogger(__name__)

class VidibrAuditoriaPage(BasePage):
    def __init__(self, page: Page):
        super().__init__(page)
        self.btn_avaliacoes = page.get_by_role("button", name="Avaliações Realizadas")
        self.dialog_jobs = page.get_by_role("dialog", name="Selecione o Job:")
        self.radiogroup_jobs = self.dialog_jobs.get_by_role("radiogroup", name="Selecione o Job:")
        self.btn_dialog_ok = self.dialog_jobs.get_by_role("button", name="OK")

    async def abrir_selecao_jobs(self):
        logger.info("Abrindo seleção de Avaliações Realizadas...")
        await self.btn_avaliacoes.wait_for(state="visible", timeout=15000)
        await self.btn_avaliacoes.click()
        await self.dialog_jobs.wait_for(state="visible", timeout=15000)

    async def listar_formularios(self) -> List[str]:
        """Lista os nomes dos formulários disponíveis."""
        logger.info("Listando formulários...")
        radios = self.radiogroup_jobs.get_by_role("radio")
        count = await radios.count()
        
        formularios = []
        for i in range(count):
            radio = radios.nth(i)
            texto = await radio.get_attribute("aria-label") or await radio.text_content()
            texto = texto.strip() if texto else ""
            if texto and texto.lower() != 'todos':
                formularios.append(texto)
        
        return formularios

    async def selecionar_formulario_e_entrar(self, nome_formulario: str):
        """Seleciona um formulário e confirma, seguindo os tempos de delay do modelo."""
        logger.info(f"Selecionando: {nome_formulario}")
        radio = self.radiogroup_jobs.get_by_role("radio", name=nome_formulario)
        await radio.wait_for(state="visible")
        await radio.click()
        
        # Delay de 500ms como no modelo
        await asyncio.sleep(0.5)
        
        logger.info("Confirmando seleção (OK)...")
        await self.btn_dialog_ok.click()
        
        # POST_CLICK_DELAY do modelo (2 segundos) para permitir que a SPA processe
        await asyncio.sleep(2)
        
        # Aguarda o carregamento técnico
        await self.wait_for_loader()
        await self.page.wait_for_load_state('networkidle')

    def _limpar_prefixo(self, texto: str, prefixo: str) -> str:
        """Remove o prefixo (ex: 'CNPJ:') do valor extraído."""
        if texto.lower().startswith(prefixo.lower()):
            return texto[len(prefixo):].strip(': ').strip()
        return texto.strip()

    async def extrair_detalhes(self) -> Dict[str, str]:
        """Extrai detalhes do formulário seguindo a robustez do script modelo."""
        logger.info("Iniciando extração de detalhes do formulário...")
        
        # Tenta clicar em "Ver mais"
        try:
            ver_mais = self.page.get_by_role("link", name="Ver mais")
            if await ver_mais.count() > 0:
                await ver_mais.first.click()
                await asyncio.sleep(1) # Delay após expansão
        except: pass

        box = self.page.locator(".box-pergunta").first
        # Timeout de 15s como no modelo
        await box.wait_for(state="visible", timeout=15000)

        info = {}
        
        # Local visitado via data-cy
        local_el = self.page.locator('[data-cy="abrirQuestionarioJob"]')
        info['Local visitado'] = (await local_el.text_content()).strip() if await local_el.count() > 0 else 'N/E'

        # Campos com strong labels (seguindo lista do modelo)
        campos_strong = ['CNPJ', 'Endereço', 'Período', 'Número do QT', 
                         'Número da Loja', 'Data da Visita', 'Situação']
        
        for campo in campos_strong:
            try:
                divisor = f"{campo}:"
                # Seletor exato do modelo: span que contém um strong com o texto do campo
                elemento = box.locator(f"span:has(strong:text-is('{divisor}'))")
                if await elemento.count() > 0:
                    texto_bruto = await elemento.first.text_content()
                    info[campo] = self._limpar_prefixo(texto_bruto, divisor)
                else:
                    info[campo] = 'N/E'
            except:
                info[campo] = 'Erro'

        # Loja via readmore-component
        try:
            loja_el = box.locator("readmore-component > div")
            info['Loja'] = (await loja_el.text_content()).strip() if await loja_el.count() > 0 else 'N/E'
        except:
            info['Loja'] = 'Erro'

        logger.info("Detalhes extraídos com sucesso!")
        return info
