import asyncio
import re
from datetime import datetime
from workflow.components.wide_logger import WideLogger

MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

CS_CODES = ["13406", "13408", "14056", "23107"]


class CalendarioCarPage:
    """Page Object for Calendario CAR on Extranet Grupo Boticario."""

    LOGIN_URL = (
        "https://login.extranet.grupoboticario.com.br/1e6392bd-5377-48f0-9a8e-467f5b381b18"
        "/oauth2/v2.0/authorize?p=B2C_1A_JIT_SIGNUPORSIGNIN_FEDCORP_APIGEE_PRD"
        "&client_id=b3001e60-a8e0-4da8-82ba-c3a701405f08"
        "&redirect_uri=https%3A%2F%2Fextranet.grupoboticario.com.br%2Fauth%2Fcallback"
        "&response_type=code"
        "&scope=openid%20email%20https%3A%2F%2Fgboticariob2c.onmicrosoft.com%2Fa6cd4fe6-3d71-455a-b99d-f458a07cc0d1%2Fextranet.api%20offline_access"
        "&state=bbdcc905a11749b8a67f3f06ae03abbb"
        "&code_challenge=HS9vo6VqqoEMeY7-4Jya_4RylUsNKRnkaGbsMhjQmWE"
        "&code_challenge_method=S256&response_mode=query"
    )
    CALENDAR_URL = "https://extranet.grupoboticario.com.br/mfe/portais-de-credito/portal-do-franqueado/calendario-car"

    def __init__(self, page, logger: WideLogger):
        self.page = page
        self.logger = logger

    # ── Auth & Navigation ─────────────────────────────────────────────

    async def login(self, username, password):
        self.logger.info("Navigating to Login URL...")
        await self.page.goto(self.LOGIN_URL, wait_until="networkidle")
        await asyncio.sleep(2)

        if await self.page.locator("#signInName").is_visible():
            self.logger.info("Login page detected. Performing login...")
            await self.page.locator("#signInName").click()
            await asyncio.sleep(0.5)
            await self.page.fill("#signInName", username)

            await self.page.locator("#password").click()
            await asyncio.sleep(0.5)
            await self.page.fill("#password", password)

            self.logger.info("Clicking ENTRAR...")
            await self.page.click("#next")

            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(5)

            self.logger.info(f"Post-login URL: {self.page.url}")
            self.logger.add_context("post_login_url", self.page.url)
        else:
            self.logger.info("Already logged in. Proceeding...")

    async def navigate_to_calendar(self):
        self.logger.info("Navigating to Calendar CAR...")
        try:
            await self.page.goto(self.CALENDAR_URL, wait_until="domcontentloaded")
        except Exception as e:
            self.logger.warning(f"Navigation warning: {e}")

        # Wait for MFE to fully render (SPA loads microfrontend content async)
        self.logger.info("Waiting for MFE content to render...")
        await self.page.get_by_text("Código da CS").wait_for(state="visible", timeout=30000)
        self.logger.info(f"Calendar page loaded. URL: {self.page.url}")

    # ── Dismiss popups ────────────────────────────────────────────────

    async def dismiss_popups(self):
        """Dismiss cookie banner and notification popup if visible."""
        try:
            btn = self.page.get_by_text("Aceitar todos os cookies")
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await asyncio.sleep(1)
        except:
            pass
        try:
            btn = self.page.get_by_text("Agora não")
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await asyncio.sleep(1)
        except:
            pass

    async def _click_combobox_option(self, button_id: str, option_text: str):
        """Click a Flora combobox button and select an option from its listbox."""
        self.logger.info(f"Selecting '{option_text}' in #{button_id}")

        btn = self.page.locator(f"#{button_id}")
        await btn.click()
        await asyncio.sleep(0.5)

        # The listbox appears; select the matching option
        option = self.page.get_by_role("option", name=option_text, exact=True)
        await option.wait_for(state="visible", timeout=5000)
        await option.click()
        await asyncio.sleep(0.5)

    async def select_filters(self, cs_code: str, month: int, year: int):
        """Set the three filter dropdowns."""
        await self._click_combobox_option("MediatorCodeDropdown", cs_code)
        await self._click_combobox_option("month", MESES[month])
        await self._click_combobox_option("year", str(year))

    # ── Search with retry ─────────────────────────────────────────────

    async def click_buscar(self, max_retries: int = 3) -> bool:
        """Click Buscar, wait for loading, retry on error."""
        for attempt in range(1, max_retries + 1):
            self.logger.info(f"Clicking Buscar (attempt {attempt}/{max_retries})...")
            await self.page.locator("button:has-text('Buscar')").click()

            # Wait for the loading spinner to appear then disappear
            try:
                loading = self.page.locator("[data-testid='loading-icon']")
                await loading.wait_for(state="visible", timeout=5000)
                await loading.wait_for(state="hidden", timeout=30000)
            except Exception:
                # Spinner may have appeared and gone too fast, or not at all
                await asyncio.sleep(3)

            # Check for error message
            error_msg = self.page.get_by_text(
                "Não foi possível exibir o resultado da sua pesquisa"
            )
            if await error_msg.is_visible(timeout=2000):
                self.logger.warning(f"Error on attempt {attempt}, retrying...")
                await asyncio.sleep(2)
                continue

            # Check if calendar appeared
            calendar = self.page.locator("[data-testid='calendar']")
            if await calendar.is_visible(timeout=5000):
                self.logger.info("Calendar loaded successfully.")
                return True

        self.logger.error("Failed to load calendar after retries.")
        return False

    # ── Data extraction ───────────────────────────────────────────────

    async def extract_calendar_data(self) -> dict:
        """Extract totals and day-by-day data from the visible calendar."""
        data = await self.page.evaluate("""() => {
            const cal = document.querySelector('[data-testid="calendar"]');
            if (!cal) return { total_recebimentos: null, total_agendamentos: null, days: [] };

            // ── Totals (use stable data-testid icons as anchors) ──
            let totalReceb = null, totalAgend = null;
            const checkIcon = cal.querySelector('[data-testid="check-circle-icon"]');
            if (checkIcon) {
                const p = checkIcon.previousElementSibling;
                if (p) totalReceb = p.textContent.trim();
            }
            const calIcon = cal.querySelector('[data-testid="calendar-icon"]');
            if (calIcon) {
                const p = calIcon.previousElementSibling;
                if (p) totalAgend = p.textContent.trim();
            }

            // ── Day cells (data-testid="DD-MM-YYYY") ──
            const dayRe = /^\\d{2}-\\d{2}-\\d{4}$/;
            const days = [];
            cal.querySelectorAll('[data-testid]').forEach(cell => {
                const tid = cell.getAttribute('data-testid');
                if (!dayRe.test(tid)) return;

                const valEl = cell.querySelector('[data-installment-status]');
                if (!valEl) return;                // skip days without data

                const status = valEl.getAttribute('data-installment-status');
                const value  = valEl.textContent.trim();
                const titEl  = valEl.nextElementSibling;
                const titulos = titEl ? titEl.textContent.trim() : '';

                days.push({ date: tid, value, status, titulos });
            });

            return { total_recebimentos: totalReceb, total_agendamentos: totalAgend, days };
        }""")

        self.logger.info(
            f"Extracted {len(data.get('days', []))} days | "
            f"Receb={data.get('total_recebimentos')} | "
            f"Agend={data.get('total_agendamentos')}"
        )
        return data

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def get_extraction_periods() -> list[tuple[int, int]]:
        """Return [(month, year), ...] for current + next month."""
        now = datetime.now()
        m, y = now.month, now.year
        periods = [(m, y)]
        if m == 12:
            periods.append((1, y + 1))
        else:
            periods.append((m + 1, y))
        return periods
