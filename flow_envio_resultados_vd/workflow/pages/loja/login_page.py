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
        Realiza o login no Google com os passos definidos.
        Detecta automaticamente se o Google está pedindo:
        - Email + senha (login completo)
        - Seleção de conta (múltiplas contas ou "Sem sessão iniciada")
        - Apenas senha (sessão parcialmente ativa)
        """
        logger.info("Iniciando autenticação Google...")

        # Verifica os elementos visíveis na tela
        campo_email_visivel = False
        campo_senha_visivel = False
        tela_selecao_conta = False
        
        try:
            campo_email_visivel = await self.page.locator("#identifierId").is_visible(timeout=3000)
        except:
            pass
        
        try:
            campo_senha_visivel = await self.page.locator('input[name="Passwd"]').is_visible(timeout=1000)
        except:
            pass
        
        # Verifica se é a tela de seleção de conta (conta com "Sem sessão iniciada")
        try:
            # Procura pelo elemento com data-identifier do email e texto "Sem sessão iniciada"
            conta_sem_sessao = self.page.locator(f'div[data-identifier="{email}"]')
            tela_selecao_conta = await conta_sem_sessao.is_visible(timeout=2000)
        except:
            pass
        
        logger.info(f"Campo email visível: {campo_email_visivel}, Campo senha visível: {campo_senha_visivel}, Tela seleção conta: {tela_selecao_conta}")

        # CASO 1: Tela de seleção de conta (precisa clicar na conta com "Sem sessão iniciada")
        if tela_selecao_conta:
            logger.info(f"Tela de seleção de conta detectada. Clicando na conta: {email}...")
            conta_element = self.page.locator(f'div[data-identifier="{email}"]')
            await conta_element.click()
            logger.info("Conta selecionada. Aguardando campo de senha...")
            
            # Aguarda o campo de senha aparecer após selecionar a conta
            await self.page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=10000)
        
        # CASO 2: Campo de email está visível (login completo)
        elif campo_email_visivel:
            logger.info("Preenchendo Email...")
            await self.preencher("#identifierId", email)

            # Clicar em Avançar
            logger.info("Clicando em Avançar...")
            await self.page.get_by_role('button', name='Avançar').click()

            # Aguardar campo de senha aparecer (há animação do Google)
            logger.info("Aguardando campo de senha...")
            await self.page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=10000)
        
        # CASO 3: Campo de senha já está visível (sessão parcial)
        elif campo_senha_visivel:
            logger.info("Sessão parcial do Google detectada - pulando para preenchimento de senha...")
        
        # CASO 4: Nenhum campo visível - aguarda e tenta novamente
        else:
            logger.info("Nenhum campo visível ainda. Aguardando...")
            await self.page.wait_for_timeout(3000)
            
            # Tenta novamente verificar seleção de conta
            try:
                conta_sem_sessao = self.page.locator(f'div[data-identifier="{email}"]')
                if await conta_sem_sessao.is_visible(timeout=2000):
                    logger.info(f"Tela de seleção de conta detectada (retry). Clicando na conta: {email}...")
                    await conta_sem_sessao.click()
                    await self.page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=10000)
            except:
                pass
            
            # Tenta novamente verificar o campo de senha
            try:
                await self.page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=10000)
                logger.info("Campo de senha encontrado após aguardar.")
            except:
                # Pode ser que precise do email
                try:
                    if await self.page.locator("#identifierId").is_visible(timeout=3000):
                        logger.info("Campo de email apareceu. Preenchendo...")
                        await self.preencher("#identifierId", email)
                        await self.page.get_by_role('button', name='Avançar').click()
                        await self.page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=10000)
                except Exception as e:
                    logger.error(f"Não foi possível encontrar campo de login: {e}")
                    raise
        
        # Preencher Senha
        logger.info("Preenchendo Senha...")
        await self.page.locator('input[name="Passwd"]').fill(senha)

        # Clicar em Avançar novamente
        logger.info("Clicando em Avançar (Login)...")
        await self.page.get_by_role('button', name='Avançar').click()
        
        # Aguarda um momento para o login processar
        await self.page.wait_for_timeout(3000)

    async def is_login_button_visible(self):
        """
        Verifica se o botão de Login Externo está visível na página.
        """
        try:
            return await self.page.locator("#btnLoginExterno").is_visible(timeout=3000)
        except:
            return False
