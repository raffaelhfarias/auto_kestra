import asyncio
import calendar
import glob
import os
import shutil
from datetime import datetime
from workflow.components.wide_logger import WideLogger


class PortalBoletosPage:
    """
    Page Object for Portal Boletos on Extranet Grupo Boticario.
    Handles login, navigation to JP Morgan/Guasti, filters, and Excel export.
    """

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
    PORTAL_URL = "https://extranet.grupoboticario.com.br/mfe/portal-boletos-franqueado"
    CNS_URL = "https://jpmorgan.guastitecnologia.com.br/OBoticario/CNS/CNS001_BRW.aspx"

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

    async def navigate_to_portal(self):
        """Navigate to Portal Boletos and wait for redirect to JP Morgan/Guasti."""
        self.logger.info("Navigating to Portal Boletos...")
        try:
            await self.page.goto(self.PORTAL_URL, wait_until="domcontentloaded")
        except Exception as e:
            self.logger.warning(f"Navigation warning: {e}")

        # Wait for redirect to JP Morgan/Guasti
        self.logger.info("Waiting for redirect to JP Morgan/Guasti...")
        try:
            await self.page.wait_for_url("**/jpmorgan.guastitecnologia.com.br/**", timeout=30000)
        except Exception:
            pass

        await self.page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)
        self.logger.info(f"Portal Boletos loaded. URL: {self.page.url}")

    async def navigate_to_cns(self):
        """Navigate to the CNS consultation page."""
        self.logger.info("Navigating to CNS page...")
        await self.page.goto(self.CNS_URL, wait_until="networkidle")

        # Wait for the filter form to be ready (handles ASP.NET cookie redirects)
        await self.page.locator("#ctl00_ContentBody_txtVenctoInicial").wait_for(
            state="visible", timeout=15000
        )
        self.logger.info(f"CNS page loaded. URL: {self.page.url}")

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

    # ── Filters ───────────────────────────────────────────────────────

    async def fill_dates(self, start_date: str, end_date: str):
        """
        Fill the Vencimento Inicial and Final date inputs.
        Dates in DD/MM/YYYY format.
        Uses type() with delay to trigger ASP.NET JS events properly.
        """
        self.logger.info(f"Filling dates: {start_date} → {end_date}")

        start_input = self.page.locator("#ctl00_ContentBody_txtVenctoInicial")
        await start_input.click(click_count=3)  # select all
        await start_input.type(start_date, delay=50)

        end_input = self.page.locator("#ctl00_ContentBody_txtVenctoFinal")
        await end_input.click(click_count=3)  # select all
        await end_input.type(end_date, delay=50)

        await asyncio.sleep(0.5)

    async def click_filtrar(self):
        """Click the 'Filtrar' button and wait for results."""
        self.logger.info("Clicking Filtrar...")
        await self.page.click("#ctl00_ContentBody_btnPesquisar")
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        # Verify results appeared
        row_count = await self.page.evaluate("""() => {
            const grid = document.querySelector('#ctl00_ContentBody_gvBRW');
            return grid ? grid.querySelectorAll('tr').length : 0;
        }""")
        self.logger.info(f"Filter applied. Grid rows: {row_count}")

    async def _extract_grid_page(self) -> dict:
        """Extract headers and data rows from the current grid page."""
        return await self.page.evaluate("""() => {
            const grid = document.querySelector('#ctl00_ContentBody_gvBRW');
            if (!grid) return { headers: [], rows: [], page_count: 0 };

            const result = { headers: [], rows: [], page_count: 0 };
            const allRows = grid.querySelectorAll(':scope > tbody > tr');

            allRows.forEach(tr => {
                // Header row
                if (tr.classList.contains('GridHeader')) {
                    const ths = tr.querySelectorAll('th');
                    // Skip first column (Funções = icon only)
                    result.headers = [...ths].slice(1).map(th => th.textContent.trim());
                    return;
                }

                // Pager row — count pages
                if (tr.classList.contains('GridPager')) {
                    const links = tr.querySelectorAll('a, span');
                    result.page_count = links.length;
                    return;
                }

                // Data row — extract cells, skip first (Funções)
                const tds = tr.querySelectorAll('td');
                if (tds.length < 2) return;

                const row = [...tds].slice(1).map(td => {
                    // Prefer text from nested <span> if present
                    const span = td.querySelector('span');
                    let text = span ? span.textContent.trim() : td.textContent.trim();
                    // Convert non-breaking space to empty
                    if (text === '\u00a0' || text === '') text = '';
                    return text;
                });

                // Only add if not entirely empty
                if (row.some(c => c !== '')) {
                    result.rows.push(row);
                }
            });

            return result;
        }""")

    async def _get_pager_info(self) -> dict:
        """Get current page number and total pages from the grid pager."""
        return await self.page.evaluate("""() => {
            const grid = document.querySelector('#ctl00_ContentBody_gvBRW');
            if (!grid) return { current: 0, total: 0 };

            const pager = grid.querySelector('tr.GridPager');
            if (!pager) return { current: 1, total: 1 };

            const cells = pager.querySelectorAll('td > table td');
            let current = 1, total = cells.length;

            cells.forEach(td => {
                // Current page is a <span>, others are <a>
                const span = td.querySelector('span');
                if (span) current = parseInt(span.textContent.trim(), 10);
            });

            return { current, total };
        }""")

    async def _go_to_grid_page(self, page_num: int):
        """Navigate to a specific grid page via ASP.NET postback."""
        self.logger.info(f"Navigating to grid page {page_num}...")
        await self.page.evaluate(
            f"__doPostBack('ctl00$ContentBody$gvBRW', 'Page${page_num}')"
        )
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

    async def export_to_json(self, dest_dir: str) -> str:
        """
        Extract all grid data (all pages) manually from the DOM and save as JSON.
        Navigates through each pagination page, skips the icon column,
        and properly reads nested span elements.
        """
        self.logger.info("Extracting grid data from all pages...")

        all_rows = []
        headers = []

        # Function to clean and normalize headers
        def clean_header(h):
            return h.lower().replace(" ", "_").replace("/", "_").replace(".", "")

        # Extract first page
        page_data = await self._extract_grid_page()
        raw_headers = page_data.get("headers", [])
        headers = [clean_header(h) for h in raw_headers]
        
        # Helper to convert row list to dict
        def row_to_dict(row_values):
            return dict(zip(headers, row_values))

        first_page_rows = page_data.get("rows", [])
        all_rows.extend([row_to_dict(r) for r in first_page_rows])

        pager = await self._get_pager_info()
        total_pages = pager.get("total", 1)
        # Fix: sometimes total is returned as node count, verify logic if needed.
        # But assuming _get_pager_info is correct for now.
        
        self.logger.info(f"Page 1: {len(first_page_rows)} rows. Total pages detected: {total_pages}")

        # Navigate through remaining pages
        # Only if we have pagination
        if total_pages > 1:
             for pg in range(2, total_pages + 1):
                # Trigger postback
                # Note: ASP.NET GridView pagination usually builds postbacks like 'Page$2', 'Page$3'
                # We need to be careful if the pager isn't numeric 1,2,3...
                # Using the _go_to_grid_page helper which does __doPostBack
                try:
                    await self._go_to_grid_page(pg)
                    page_data = await self._extract_grid_page()
                    current_rows = page_data.get("rows", [])
                    all_rows.extend([row_to_dict(r) for r in current_rows])
                    self.logger.info(f"Page {pg}/{total_pages}: {len(current_rows)} rows")
                except Exception as e:
                    self.logger.error(f"Failed to navigate to page {pg}: {e}")
                    break

        if not all_rows:
            self.logger.warning("No data found in grid to export.")
            # We can return empty list or raise error. 
            # In automation often better to produce empty file than fail or fail depending on reqs.
            # Let's produce empty file but log warning.

        self.logger.info(f"Total extracted: {len(all_rows)} rows")

        # Write JSON
        import json

        filename = "portalBoletos.json"
        dest_path = os.path.join(dest_dir, filename)

        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(all_rows, f, ensure_ascii=False, indent=2)

        file_size = os.path.getsize(dest_path)
        self.logger.info(f"Export saved: {dest_path} ({file_size} bytes)")
        self.logger.add_context("downloaded_file", dest_path)
        return dest_path

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def get_date_range() -> tuple[str, str]:
        """
        Calculate date range: first day of current month → last day of next month.
        Handles December → January rollover.
        Returns (start_date, end_date) in DD/MM/YYYY format.
        """
        now = datetime.now()
        m, y = now.month, now.year

        start_date = f"01/{m:02d}/{y}"

        if m == 12:
            next_m, next_y = 1, y + 1
        else:
            next_m, next_y = m + 1, y

        last_day = calendar.monthrange(next_y, next_m)[1]
        end_date = f"{last_day:02d}/{next_m:02d}/{next_y}"

        return start_date, end_date
