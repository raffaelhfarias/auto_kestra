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
        """Seleciona um formulário e confirma, aguardando a transição."""
        logger.info(f"Selecionando: {nome_formulario}")
        # Localiza o rádio pelo nome exato
        radio = self.radiogroup_jobs.get_by_role("radio", name=nome_formulario)
        await radio.wait_for(state="visible", timeout=10000)
        await radio.click()
        
        # Pequeno delay para garantir que o rádio marcou como selecionado (comum em Ionic)
        await asyncio.sleep(1)
        
        logger.info("Clicando em OK e aguardando transição...")
        await self.btn_dialog_ok.click()
        
        # ESPERA CRÍTICA: O dialog precisa sumir para sabermos que a ação foi processada
        await self.dialog_jobs.wait_for(state="hidden", timeout=15000)
        
        # Aguarda loaders globais do site
        await self.wait_for_loader()
        await self.page.wait_for_load_state('networkidle')

    async def extrair_detalhes(self) -> Dict[str, str]:
        """Extrai detalhes do formulário aberto com espera robusta."""
        logger.info("Iniciando extração de detalhes...")
        
        # Elemento principal que indica que os detalhes carregaram
        box = self.page.locator(".box-pergunta").first
        
        try:
            # Aumentado para 30s pois esta página de detalhes costuma ser pesada
            await box.wait_for(state="visible", timeout=30000)
        except Exception as e:
            logger.error("Timeout: O elemento '.box-pergunta' não carregou a tempo.")
            # Opcional: tirar um print apenas para debug local se necessário
            raise e

        # Tenta expandir o "Ver mais" se existir
        try:
            ver_mais = self.page.get_by_role("link", name="Ver mais")
            if await ver_mais.count() > 0:
                await ver_mais.first.click()
                await asyncio.sleep(1)
        except: pass

        info = {}
        try:
            # Local visitado
            local = self.page.locator('[data-cy="abrirQuestionarioJob"]')
            info['Local visitado'] = (await local.text_content()).strip() if await local.count() > 0 else 'N/E'

            # Campos padrões
            campos = ['CNPJ', 'Endereço', 'Período', 'Número do QT', 'Número da Loja', 'Data da Visita', 'Situação']
            for campo in campos:
                divisor = f"{campo}:"
                el = box.locator(f"span:has(strong:text-is('{divisor}'))")
                if await el.count() > 0:
                    texto = await el.first.text_content()
                    idx = texto.lower().find(divisor.lower()) + len(divisor)
                    info[campo] = texto[idx:].strip()
                else:
                    info[campo] = 'N/E'

            # Nome da Loja
            loja_el = box.locator("readmore-component > div")
            if await loja_el.count() > 0:
                info['Loja'] = (await loja_el.text_content()).strip()
            else:
                info['Loja'] = 'N/E'
                
        except Exception as e:
            logger.error(f"Erro ao ler campos do formulário: {e}")
            raise e

        return info
