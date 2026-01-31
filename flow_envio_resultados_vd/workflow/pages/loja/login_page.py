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



