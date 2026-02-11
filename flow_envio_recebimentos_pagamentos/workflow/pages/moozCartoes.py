import asyncio
from workflow.components.wide_logger import WideLogger

class MoozCartoesPage:
    """Page Object for Mooz Cartões navigation and filtering."""

    # Updated URL
    LOGIN_URL = "https://portal.portalmoozcartoes.com.br/autenticacao"

    def __init__(self, page, logger: WideLogger):
        self.page = page
        self.logger = logger

    async def login(self, username, password):
        """Perform login to Mooz Cartões."""
        self.logger.info("Navigating to Login URL...")
        await self.page.goto(self.LOGIN_URL, wait_until="networkidle")
        
        
        # Fill credentials
        self.logger.info("Filling credentials...")
        await self.page.fill("#username", username)
        await self.page.fill("#password", password)
        await asyncio.sleep(0.5)

        # Click Entrar
        self.logger.info("Clicking Entrar...")
        await self.page.get_by_role("button", name="Entrar", exact=True).click()
        
        # Wait for login to complete
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(5) # Wait for SPA transition
        self.logger.info(f"Post-login URL: {self.page.url}")

    async def open_merchant_list(self):
        """Open the establishments dropdown."""
        self.logger.info("Opening merchant list...")
        try:
            # Locate button by text "Estabelecimentos" as per instructions
            btn = self.page.locator("button").filter(has_text="Estabelecimentos").first
            await btn.click()
            # Wait for list items to appear
            await self.page.locator("div[data-testid='merchant-item']").first.wait_for(state="visible", timeout=5000)
        except Exception as e:
            self.logger.warning(f"Could not open merchant list: {e}")
            raise e

    async def get_merchant_ids(self) -> list[str]:
        """Scrape all available merchant select button IDs."""
        current_url = self.page.url
        await self.open_merchant_list()
        
        # Find all select buttons logic
        buttons = self.page.locator("div[data-testid='merchant-item'] button[data-testid^='select-button-']")
        count = await buttons.count()
        
        ids = []
        for i in range(count):
            testid = await buttons.nth(i).get_attribute("data-testid")
            if testid and "select-button-" in testid:
                mid = testid.replace("select-button-", "")
                ids.append(mid)
        
        self.logger.info(f"Found {len(ids)} merchants: {ids}")
        
        # Close list if needed or just proceed? 
        # Clicking outside or re-clicking button might close it, 
        # but proceeding to selection immediately is fine.
        return ids

    async def select_merchant(self, merchant_id: str):
        """Select a merchant by ID."""
        self.logger.info(f"Selecting merchant {merchant_id}...")
        
        target_btn = self.page.locator(f"button[data-testid='select-button-{merchant_id}']")
        
        # Check if button is visible. If not, we assume list is closed (or needs refresh)
        if not await target_btn.is_visible():
            self.logger.info(f"Button for {merchant_id} not visible. Opening merchant list...")
            await self.open_merchant_list()
        
        # Give a small moment for animation/rendering
        await asyncio.sleep(0.5)

        if await target_btn.is_visible():
            await target_btn.scroll_into_view_if_needed()
            await target_btn.click()
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(2) 
        else:
            # If still not visible, it's a hard error
            raise ValueError(f"Merchant ID {merchant_id} button not found even after opening list")

    async def navigate_to_payments(self):
        """Navigate to the payments URL."""
        payments_url = "https://portal.portalmoozcartoes.com.br/payments"
        self.logger.info(f"Navigating to {payments_url}")
        await self.page.goto(payments_url, wait_until="networkidle")

    async def navigate_to_select_merchant(self):
        """Navigate back to the merchant selection page."""
        url = "https://portal.portalmoozcartoes.com.br/selecionar-estabelecimento"
        self.logger.info(f"Navigating back to {url}")
        await self.page.goto(url, wait_until="networkidle")
        # Ensure page is loaded by waiting for the main button
        await self.page.locator("button").filter(has_text="Estabelecimentos").first.wait_for(state="visible", timeout=10000)


    async def select_filters(self, start_date: str, end_date: str):
        """
        Apply filters to the page. 
        Adjust arguments and implementation based on specific filter requirements.
        """
        self.logger.info(f"Applying filters: {start_date} to {end_date}")
        # Placeholder implementation
        await asyncio.sleep(1)

    async def extract_calendar_data(self) -> dict:
        """
        Extract data from the calendar/grid.
        Iterates over the calendar days and strictly filters for days belonging to the current header month
        to avoid duplicates from previous/next month overflow.
        """
        self.logger.info("Extracting calendar data...")
        
        # Wait for calendar content
        await self.page.locator("div._monthDaysContent_hcl7j_55").wait_for(state="visible", timeout=10000)
        
        # 1. Parse Header Month/Year
        try:
             month_year_el = self.page.locator("div._currentMonth_hcl7j_6 span").first
             month_year_text = (await month_year_el.text_content()).strip().lower()
             # Example: "fevereiro 2026"
             parts = month_year_text.split()
             if len(parts) >= 2:
                 pt_month = parts[0]
                 year = int(parts[1])
             else:
                 raise ValueError(f"Invalid header format: {month_year_text}")
                 
             # Map PT month to int
             pt_months = {
                 "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5, "junho": 6,
                 "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
             }
             month_num = pt_months.get(pt_month)
             if not month_num:
                 raise ValueError(f"Unknown month: {pt_month}")
                 
             self.logger.info(f"Target Month: {month_num}/{year} ({month_year_text})")
             
        except Exception as e:
             self.logger.error(f"Failed to parse calendar header: {e}")
             return {}

        # 2. Scrape Raw Data from DOM
        # We grab all cells first, then process the logic in Python for better debugging/control
        raw_days = await self.page.evaluate("""() => {
            const items = [];
            const buttons = document.querySelectorAll('button._monthDayItem_hcl7j_61');
            
            buttons.forEach(btn => {
                const dayNumberEl = btn.querySelector('p._numberDay_hcl7j_81');
                if (!dayNumberEl) return;
                
                const dayNumber = parseInt(dayNumberEl.textContent.trim(), 10);
                const titleEl = btn.querySelector('p._Title_slpts_32');
                const valueEl = btn.querySelector('span._Value_slpts_36');
                
                items.push({
                    day: dayNumber,
                    status: titleEl ? titleEl.textContent.trim() : null,
                    value: valueEl ? valueEl.textContent.trim() : null,
                    has_data: !!(titleEl && valueEl)
                });
            });
            return items;
        }""")
        
        # 3. Apply Month Logic (Prevent Duplicates/Overflow)
        processed_data = []
        
        if not raw_days:
            return {"period": month_year_text, "days": []}

        # Logic: 
        # - Starts in PREV or CURR. 
        # - Transitions when day number drops (e.g. 31 -> 1).
        
        # If the first day is 1, we start in CURRENT.
        # If the first day is > 1 (like 25, 28), we start in PREVIOUS.
        
        current_stage = "PREV" if raw_days[0]['day'] > 1 else "CURR"
        previous_day_val = raw_days[0]['day']
        
        self.logger.info(f"Starting date sequence logic. First day: {previous_day_val}. Initial Stage: {current_stage}")

        for item in raw_days:
            day_val = item['day']
            
            # Detect transition (drop in value)
            if day_val < previous_day_val:
                if current_stage == "PREV":
                    current_stage = "CURR"
                elif current_stage == "CURR":
                    current_stage = "NEXT"
            
            # Filter: Only keep data if we are in CURR stage
            if current_stage == "CURR":
                if item['has_data']:
                    # Build ISO date YYYY-MM-DD
                    # Note: We need to handle leap years logic if validation needed, but constructing string is fine
                    full_date = f"{year}-{month_num:02d}-{day_val:02d}"
                    
                    processed_data.append({
                        "date": full_date,
                        "day": day_val,
                        "status": item['status'],
                        "value": item['value'],
                        "original_period": month_year_text
                    })
            
            previous_day_val = day_val

        self.logger.info(f"Processed {len(processed_data)} items belonging strictly to {month_year_text}")
        
        return {
            "period": month_year_text,
            "days": processed_data
        }

    async def navigate_to_next_month(self):
        """Click the next month pagination button."""
        self.logger.info("Navigating to next month...")
        # Locate the button with the specific SVG path d="m9 18 6-6-6-6" which corresponds to the right arrow
        # Alternatively, use the class and index if reliable.
        # Based on the user provided HTML, it's the second pagination button.
        
        # Strategy: Find button containing the specific SVG path
        # Or simply select the second button with class "_pagination_hcl7j_37"
        
        # We'll use the SVG path to be robust
        next_btn = self.page.locator("button._pagination_hcl7j_37").filter(has=self.page.locator("path[d='m9 18 6-6-6-6']"))
        
        if await next_btn.is_visible():
            await next_btn.click()
            # Wait for calendar content to update/reload
            # A simple way is to wait for the old content to detach or new content to appear
            # But since it's an SPA, we might just sleep or wait for a specific element change.
            # Let's wait for network idle and a small sleep
            await self.page.wait_for_load_state("networkidle")
            await asyncio.sleep(1) # Ensure UI update
        else:
            self.logger.warning("Next month button not found!")

