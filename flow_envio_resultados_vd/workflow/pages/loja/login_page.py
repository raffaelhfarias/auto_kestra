import re
import logging
from workflow.pages.base_page import BasePage

logger = logging.getLogger(__name__)

class LoginPage(BasePage):
    async def realizar_login_externo(self):
        """
        Realiza o fluxo de clicar no Login Externo e selecionar Colaborador/Franqueado.
        Retorna a nova página caso uma nova aba seja aberta, ou None caso contrário.
        """
        logger.info("Tentando clicar em 'Login Externo' (#btnLoginExterno)...")
        await self.clicar("#btnLoginExterno")
        
        # Aguarda um momento para ver se ocorre redirecionamento automático (SSO)
        try:
            # Aguarda um momento para ver se ocorre redirecionamento automático (SSO)
            # Timeout reduzido, pois se for SSO é rápido
            await self.page.wait_for_timeout(1000)
            current_url = self.page.url.lower()
            
            # Se já mudou para AguardarAcao ou dashboard, abortamos o segundo clique
            if "aguardaracao" in current_url or ("entrar.aspx" not in current_url and "account/login" not in current_url):
                 logger.info(f"Redirecionamento automático detectado após primeiro clique (URL: {current_url}).")
                 return
        except:
            pass

        logger.info("Tentando clicar em 'Entrar como colaborador franqueado'...")
        # Utilizando o locator composto conforme solicitado:
        # Pega link com texto 'entrar como colaborador' AND que tenha id #GoogleExchange
        
        # Verifica se o elemento existe antes de tentar clicar/esperar, ou usa um timeout menor
        botao_colaborador = self.page.get_by_role(
            "link", 
            name=re.compile("entrar como colaborador", re.IGNORECASE)
        ).and_(self.page.locator("#GoogleExchange"))

        if await botao_colaborador.is_visible(timeout=5000):
            # IMPORTANTE: O clique pode abrir uma nova aba. Precisamos capturá-la.
            context = self.page.context
            new_page = None
            
            # Handler para capturar nova página
            def on_page(page):
                nonlocal new_page
                new_page = page
                logger.info(f"Nova aba detectada: {page.url}")
            
            context.on("page", on_page)
            
            try:
                await botao_colaborador.click()
                # Aguarda um momento para possível nova aba aparecer
                await self.page.wait_for_timeout(3000)
            except Exception as e:
                logger.warning(f"Possível erro durante clique (pode ser normal se houve redirecionamento): {e}")
            finally:
                # Remove o handler para não interferir depois
                context.remove_listener("page", on_page)
            
            if new_page:
                logger.info("Alternando para a nova aba...")
                await new_page.wait_for_load_state("domcontentloaded")
                self.page = new_page
                logger.info(f"Agora trabalhando na nova aba: {new_page.url}")
                return new_page
            else:
                logger.info("Nenhuma nova aba foi aberta. Continuando na aba atual.")
                return None
        else:
             logger.info("Botão 'Entrar como colaborador' não encontrado ou não visível. Verificando se já navegou...")
             if "entrar.aspx" not in self.page.url.lower():
                 logger.info("Parece que já saímos da tela de login.")
             else:
                 logger.warning("Ainda estamos na tela de login, mas botão não apareceu.")
             return None

    async def realizar_login_google(self, email, senha):
        """
        Realiza o login no Google com os passos definidos e tira screenshots.
        """
        logger.info("Iniciando autenticação Google...")

        # 1. Preencher Email
        logger.info("Preenchendo Email...")
        await self.preencher("#identifierId", email)
        


        # Clicar em Avançar
        logger.info("Clicando em Avançar...")
        await self.page.get_by_role('button', name='Avançar').click()

        # 2. Preencher Senha (esperar aparecer)
        logger.info("Aguardando campo de senha...")
        # Usando locator direto conforme solicitado: input[name="Passwd"]
        # Precisamos esperar estar visivel pois há animação do Google
        await self.page.locator('input[name="Passwd"]').wait_for(state="visible")
        
        logger.info("Preenchendo Senha...")
        await self.page.locator('input[name="Passwd"]').fill(senha)

        # Clicar em Avançar novamente
        logger.info("Clicando em Avançar (Login)...")
        await self.page.get_by_role('button', name='Avançar').click()

        # Aguardar navegação ou erro
        # try:
        #     await self.page.wait_for_load_state("networkidle", timeout=10000)
        # except:
        #     pass

    async def is_login_button_visible(self):
        """
        Verifica se o botão de Login Externo está visível na página.
        """
        try:
            return await self.page.locator("#btnLoginExterno").is_visible(timeout=3000)
        except:
            return False
