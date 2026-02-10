import re
import os
import asyncio
import logging
from workflow.pages.base_page import BasePage
import pyotp

logger = logging.getLogger(__name__)

class LoginPage(BasePage):
    async def realizar_login_externo(self):
        """
        Realiza o fluxo de clicar no Login Externo e selecionar Colaborador/Franqueado.
        Retorna a nova pagina caso uma nova aba seja aberta, ou None caso contrario.
        """
        logger.info("Tentando clicar em 'Login Externo' (#btnLoginExterno)...")
        await self.clicar("#btnLoginExterno")
        
        # Aguarda um momento para ver se ocorre redirecionamento automatico (SSO)
        try:
            await self.page.wait_for_timeout(2000)
            current_url = self.page.url.lower()
            
            # Se ja mudou para AguardarAcao ou dashboard, abortamos o segundo clique
            if "aguardaracao" in current_url or ("entrar.aspx" not in current_url and "account/login" not in current_url and "sgi.e-boticario.com.br" in current_url):
                 logger.info(f"Redirecionamento automatico detectado apos primeiro clique (URL: {current_url}).")
                 return
        except:
            pass

        logger.info("Tentando clicar em 'Entrar como colaborador franqueado'...")
        # Pega link com texto 'entrar como colaborador' AND que tenha id #GoogleExchange
        botao_colaborador = self.page.get_by_role(
            "link", 
            name=re.compile("entrar como colaborador", re.IGNORECASE)
        ).and_(self.page.locator("#GoogleExchange"))

        try:
            is_visible = await botao_colaborador.is_visible(timeout=5000)
        except:
            is_visible = False

        if not is_visible:
            logger.info("Botao 'Entrar como colaborador' nao encontrado ou nao visivel. Verificando se ja navegou...")
            if "entrar.aspx" not in self.page.url.lower():
                logger.info("Parece que ja saimos da tela de login.")
            else:
                logger.warning("Ainda estamos na tela de login, mas botao nao apareceu.")
            return None

        # IMPORTANTE: O clique pode abrir uma nova aba. Precisamos captura-la.
        context = self.page.context
        new_page = None
        
        # Handler para capturar nova pagina
        def on_page(page):
            nonlocal new_page
            new_page = page
            logger.info(f"Nova aba detectada: {page.url}")
        
        context.on("page", on_page)
        
        try:
            await botao_colaborador.click()
            # Aguarda um momento para possivel nova aba aparecer
            await self.page.wait_for_timeout(3000)
        except Exception as e:
            logger.warning(f"Possivel erro durante clique (pode ser normal se houve redirecionamento): {e}")
        finally:
            # Remove o handler para nao interferir depois
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

    async def realizar_login_google(self, email, senha):
        """
        Realiza o login no Google com os passos definidos.
        Detecta automaticamente se o Google esta pedindo:
        - Email + senha (login completo)
        - Selecao de conta (multiplas contas ou "Sem sessao iniciada")
        - Apenas senha (sessao parcialmente ativa)
        
        Apos email+senha, realiza 2FA via TOTP se solicitado.
        """
        logger.info("Iniciando autenticacao Google...")

        # Se estiver na pagina do Azure B2C, aguarda redirecionamento para Google
        current_url = self.page.url.lower()
        if "login-vdmais.grupoboticario.com.br" in current_url:
            logger.info("Na pagina Azure B2C. Aguardando redirecionamento para Google...")
            try:
                await self.page.wait_for_url("**/accounts.google.com/**", timeout=15000)
            except:
                logger.info("Timeout esperando Google. Verificando URL atual...")
                current_url = self.page.url.lower()
                if "sgi.e-boticario.com.br" in current_url:
                    logger.info("Ja redirecionou para SGI! SSO automatico funcionou.")
                    return

        # Verifica os elementos visiveis na tela
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
        
        # Verifica se e a tela de selecao de conta
        try:
            conta_sem_sessao = self.page.locator(f'div[data-identifier="{email}"]')
            tela_selecao_conta = await conta_sem_sessao.is_visible(timeout=2000)
        except:
            pass
        
        logger.info(f"Campo email visivel: {campo_email_visivel}, Campo senha visivel: {campo_senha_visivel}, Tela selecao conta: {tela_selecao_conta}")

        # CASO 1: Tela de selecao de conta (precisa clicar na conta com "Sem sessao iniciada")
        if tela_selecao_conta:
            logger.info(f"Tela de selecao de conta detectada. Clicando na conta: {email}...")
            conta_element = self.page.locator(f'div[data-identifier="{email}"]')
            await conta_element.click()
            logger.info("Conta selecionada. Aguardando campo de senha...")
            await self.page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=10000)
        
        # CASO 2: Campo de email esta visivel (login completo)
        elif campo_email_visivel:
            logger.info("Preenchendo Email...")
            await self.preencher("#identifierId", email)

            # Clicar em Avancar
            logger.info("Clicando em Avancar...")
            await self.page.locator("#identifierNext").click()

            # Aguardar campo de senha aparecer (ha animacao do Google)
            logger.info("Aguardando campo de senha...")
            await self.page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=15000)
        
        # CASO 3: Campo de senha ja esta visivel (sessao parcial)
        elif campo_senha_visivel:
            logger.info("Sessao parcial do Google detectada - pulando para preenchimento de senha...")
        
        # CASO 4: Nenhum campo visivel - aguarda e tenta novamente
        else:
            logger.info("Nenhum campo visivel ainda. Aguardando...")
            await self.page.wait_for_timeout(3000)
            
            # Tenta novamente verificar selecao de conta
            try:
                conta_sem_sessao = self.page.locator(f'div[data-identifier="{email}"]')
                if await conta_sem_sessao.is_visible(timeout=2000):
                    logger.info(f"Tela de selecao de conta detectada (retry). Clicando na conta: {email}...")
                    await conta_sem_sessao.click()
                    await self.page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=10000)
            except:
                pass
            
            # Tenta novamente verificar o campo de senha
            try:
                await self.page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=10000)
                logger.info("Campo de senha encontrado apos aguardar.")
            except:
                # Pode ser que precise do email
                try:
                    if await self.page.locator("#identifierId").is_visible(timeout=3000):
                        logger.info("Campo de email apareceu. Preenchendo...")
                        await self.preencher("#identifierId", email)
                        await self.page.locator("#identifierNext").click()
                        await self.page.locator('input[name="Passwd"]').wait_for(state="visible", timeout=15000)
                except Exception as e:
                    logger.error(f"Nao foi possivel encontrar campo de login: {e}")
                    raise
        
        # Preencher Senha
        logger.info("Preenchendo Senha...")
        await self.page.locator('input[name="Passwd"]').fill(senha)
        await asyncio.sleep(1)

        # Clicar em Avancar novamente
        logger.info("Clicando em Avancar (Login)...")
        await self.page.locator("#passwordNext").click()
        
        # --- 2FA (TOTP) ---
        logger.info("Aguardando possivel 2FA...")
        await asyncio.sleep(3)

        totp_secret = os.environ.get("GOOGLE_TOTP_SECRET", "").replace(" ", "")

        if totp_secret:
            try:
                await self.page.wait_for_selector('input[type="tel"]', state="visible", timeout=15000)

                totp = pyotp.TOTP(totp_secret)
                code = totp.now()
                logger.info(f"Codigo TOTP gerado: {code}")

                await self.page.fill('input[type="tel"]', code)
                await asyncio.sleep(1)

                # Clicar no botao de avancar do TOTP
                next_btn = self.page.locator('#totpNext button, button:has-text("Next"), button:has-text("Avançar")')
                if await next_btn.count() > 0:
                    await next_btn.first.click()
                else:
                    await self.page.keyboard.press("Enter")

                await asyncio.sleep(3)
                logger.info("TOTP enviado com sucesso!")

            except Exception as e:
                logger.info(f"2FA nao solicitado ou metodo diferente: {e}")
        else:
            logger.info("GOOGLE_TOTP_SECRET nao configurado. Pulando 2FA.")
            # Aguarda login processar sem 2FA
            await self.page.wait_for_timeout(3000)

        # Aguarda login completar
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        current_url = self.page.url
        logger.info(f"URL apos login Google: {current_url}")

        # Verifica tela de confirmacao do Google
        try:
            titulo = await self.page.title()
            if "Confirme que é você" in titulo or "Confirm it's you" in titulo:
                logger.warning("Tela de confirmacao do Google detectada!")
                await self.page.screenshot(path="debug_google_confirmation.png")
        except:
            pass

    async def is_login_button_visible(self):
        """
        Verifica se o botao de Login Externo esta visivel na pagina.
        """
        try:
            return await self.page.locator("#btnLoginExterno").is_visible(timeout=3000)
        except:
            return False
