import re
import logging
from workflow.pages.base_page import BasePage

logger = logging.getLogger(__name__)

class LoginPage(BasePage):
    async def realizar_login_externo(self):
        """
        Realiza o fluxo de clicar no Login Externo e selecionar Colaborador/Franqueado.
        """
        logger.info("Tentando clicar em 'Login Externo' (#btnLoginExterno)...")
        await self.clicar("#btnLoginExterno")
        
        logger.info("Tentando clicar em 'Entrar como colaborador franqueado'...")
        # Utilizando o locator composto conforme solicitado:
        # Pega link com texto 'entrar como colaborador' AND que tenha id #GoogleExchange
        await self.page.get_by_role(
            "link", 
            name=re.compile("entrar como colaborador", re.IGNORECASE)
        ).and_(self.page.locator("#GoogleExchange")).click()

    async def realizar_login_google(self, email, senha, token_2fa=None):
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

        if token_2fa:
            logger.info("Aguardando possível solicitação de 2FA...")
            try:
                # Tenta identificar o campo de TOTP. O seletor pode variar, mas geralmente é name="totpPin" ou id="totpPin"
                # ou input[type="tel"]. Vamos tentar alguns comuns.
                # Timeout curto pois pode não pedir 2FA
                totp_input = self.page.locator('input[name="totpPin"]')
                await totp_input.wait_for(state="visible", timeout=5000)
                
                logger.info(f"Campo 2FA detectado. Inserindo token: {token_2fa}")
                await totp_input.fill(token_2fa)
                
                # Clicar em Avançar no 2FA
                await self.page.get_by_role('button', name='Avançar').click()
            except Exception:
                logger.info("Campo 2FA direto não encontrado. Verificando tela de desafio...")
                
                # Verifica se estamos na tela de "Escolha como fazer login" ou "Confirme que é você"
                # O locator pode ser pelo texto de cabeçalho ou botões específicos
                try:
                    # Dá um tempo para a animação da tela de desafio carregar se for o caso
                    await self.page.wait_for_timeout(2000)
                    
                    # Tenta encontrar a opção de Google Authenticator diretamente na lista
                    # O texto pode variar: "Receber um código de verificação no app Google Authenticator"
                    # Vamos buscar por algo genérico primeiro
                    auth_option = self.page.get_by_text("Google Authenticator")
                    
                    if await auth_option.is_visible():
                        logger.info("Opção 'Google Authenticator' encontrada. Clicando...")
                        await auth_option.click()
                    else:
                        logger.info("Opção 'Google Authenticator' NÃO encontrada na lista inicial.")
                        
                        # Tenta clicar em "Tentar de outro jeito" se existir
                        try_another = self.page.get_by_text("Tentar de outro jeito")
                        if await try_another.is_visible():
                            logger.info("Clicando em 'Tentar de outro jeito'...")
                            await try_another.click()
                            
                            # Agora espera aparecer a opção
                            logger.info("Aguardando opção 'Google Authenticator' aparecer...")
                            await auth_option.wait_for(state="visible", timeout=5000)
                            await auth_option.click()
                        else:
                            logger.warning("Botão 'Tentar de outro jeito' não encontrado.")

                    # Após selecionar a opção, aguarda o campo aparecer novamente
                    totp_input = self.page.locator('input[name="totpPin"]')
                    await totp_input.wait_for(state="visible", timeout=10000)
                    
                    logger.info(f"Campo 2FA detectado após navegação. Inserindo token.")
                    await totp_input.fill(token_2fa)
                    
                    # Clicar em Avançar no 2FA
                    await self.page.get_by_role('button', name='Avançar').click()
                    
                except Exception as e_inner:
                    logger.error(f"Falha ao tentar navegar pelo desafio de 2FA: {e_inner}")
                    raise e_inner

