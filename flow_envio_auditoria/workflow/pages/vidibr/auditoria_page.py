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
        
        # Elementos do Pop-up de Jobs / Diálogos
        self.dialog_wrapper = page.locator(".alert-radio-group")
        self.radio_labels = page.locator(".alert-radio-label")
        self.btn_ok = page.locator("button.alert-button").filter(has_text="OK")
        
        # Filtro de local (ion-select com data-cy específico)
        self.filtro_local = page.locator("ion-select[data-cy='filtro-job-local-avaliacao']")

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
        
        # Aguarda o diálogo fechar antes de prosseguir
        try:
            await self.dialog_wrapper.wait_for(state="hidden", timeout=10000)
            logger.info("Diálogo de seleção fechado.")
        except Exception:
            logger.warning("Diálogo pode não ter fechado completamente, continuando...")
        
        # Aguarda a página carregar o conteúdo do formulário selecionado
        logger.info("Aguardando carregamento da página do formulário...")
        try:
            await self.page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            logger.warning("Timeout em networkidle, tentando continuar...")
        
        # POST_CLICK_DELAY adicional para garantir renderização
        await asyncio.sleep(3)

    async def selecionar_local_mais_recente(self) -> str:
        """Clica no filtro de local (data-cy) e seleciona o primeiro espaço."""
        logger.info("Abrindo filtro de local...")
        
        # Aguarda o filtro de local aparecer na página
        await self.filtro_local.wait_for(state="visible", timeout=15000)
        logger.info("Filtro de local encontrado (data-cy='filtro-job-local-avaliacao').")
        await self.filtro_local.click()
        logger.info("Filtro de local clicado.")
        
        # Aguarda o dropdown de rádios aparecer
        await asyncio.sleep(1)
        radio_group = self.page.locator(".alert-radio-group")
        await radio_group.wait_for(state="visible", timeout=10000)
        logger.info("Dropdown de local aberto!")
        
        # Itera sobre os botões de rádio para encontrar o primeiro que não seja 'Todos'
        radios = self.page.locator("button.alert-radio")
        count = await radios.count()
        logger.info(f"Opções no dropdown: {count}")
        
        local_selecionado = ""
        radio_alvo = None
        
        for i in range(count):
            r = radios.nth(i)
            label_text = await r.locator(".alert-radio-label").text_content()
            label_clean = label_text.strip() if label_text else ""
            logger.info(f"  Radio {i}: '{label_clean[:70]}'")
            if label_clean and label_clean.lower() != 'todos':
                local_selecionado = label_clean
                radio_alvo = r
                break
        
        if not radio_alvo:
            logger.warning("Nenhum local encontrado no filtro.")
            await self.btn_ok.click()
            await asyncio.sleep(1)
            return ''
        
        logger.info(f"Selecionando local: {local_selecionado[:70]}...")
        
        # Clica no radio do local
        await radio_alvo.click()
        await asyncio.sleep(0.5)
        
        # Confirma seleção (OK)
        logger.info("Confirmando seleção do local (OK)...")
        await self.btn_ok.click()
        
        # Aguarda o diálogo fechar
        try:
            await radio_group.wait_for(state="hidden", timeout=10000)
            logger.info("Diálogo de local fechado.")
        except Exception:
            logger.warning("Diálogo de local pode não ter fechado completamente.")
        
        # Aguarda carregamento do conteúdo do local selecionado
        try:
            await self.page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            logger.warning("Timeout em networkidle após seleção de local.")
        
        await asyncio.sleep(3)
        
        logger.info(f"Local selecionado com sucesso: {local_selecionado[:70]}")
        return local_selecionado

    def _limpar_prefixo(self, texto: str, prefixo: str) -> str:
        """Remove o prefixo do valor extraído."""
        if texto.lower().startswith(prefixo.lower()):
            return texto[len(prefixo):].strip(': ').strip()
        return texto.strip()

    async def extrair_detalhes(self) -> Dict[str, str]:
        """Extrai detalhes do formulário usando seletores do modelo."""
        logger.info("Iniciando extração de detalhes...")
        logger.info(f"URL atual: {self.page.url}")
        
        # === PASSO 1: Selecionar o local mais recente no filtro ===
        local_nome = await self.selecionar_local_mais_recente()
        
        # === PASSO 2: Expandir "Ver mais" se disponível ===
        try:
            ver_mais = self.page.locator("a").filter(has_text="Ver mais")
            if await ver_mais.count() > 0:
                logger.info("Clicando em 'Ver mais' para expandir detalhes...")
                await ver_mais.first.click()
                await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"'Ver mais' não encontrado ou já expandido: {e}")

        # === PASSO 3: Tentar extrair detalhes do .box-pergunta ===
        info = {}
        info['Local visitado'] = local_nome
        
        box = self.page.locator(".box-pergunta").first
        
        try:
            await box.wait_for(timeout=30000)
            logger.info(".box-pergunta encontrado!")
        except Exception:
            # .box-pergunta não encontrado — retorna apenas o local do filtro
            logger.warning(f".box-pergunta não encontrado, retornando apenas local do filtro.")
            logger.info(f"Detalhes parciais extraídos: Local = {local_nome}")
            return info

        # === PASSO 4: Extrair informações completas ===
        
        # Local visitado (prefere o elemento da página se existir)
        local_el = self.page.locator('[data-cy="abrirQuestionarioJob"]')
        if await local_el.count() > 0:
            info['Local visitado'] = (await local_el.text_content()).strip()

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

