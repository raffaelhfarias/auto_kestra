import asyncio
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from dotenv import load_dotenv
from workflow.components.navegador import Navegador
from workflow.components.wide_logger import WideLogger
from workflow.pages.portalBoletos import PortalBoletosPage

load_dotenv()

EXTRACOES_DIR = os.path.join(os.path.dirname(__file__), '../../extracoes')


async def main():
    logger = WideLogger("ScrapeBoletosService")
    logger.info("Starting Boletos extraction...")

    navegador = Navegador()
    browser_active = False
    success = False

    try:
        user_login = os.getenv("LOGIN_EXTRANET")
        user_pass = os.getenv("PASS_EXTRANET")
        if not user_login or not user_pass:
            raise ValueError("Credentials not found in .env")

        # Setup
        logger.info("Setting up browser...")
        page = await navegador.setup_browser()
        browser_active = True

        portal = PortalBoletosPage(page, logger)

        # Login & navigate
        await portal.login(user_login, user_pass)
        await portal.dismiss_popups()
        await portal.navigate_to_portal()
        await portal.navigate_to_cns()

        # Date range: 1st of current month → last day of next month
        start_date, end_date = PortalBoletosPage.get_date_range()
        logger.info(f"Date range: {start_date} → {end_date}")
        logger.add_context("start_date", start_date)
        logger.add_context("end_date", end_date)

        # Fill dates and filter
        await portal.fill_dates(start_date, end_date)
        await portal.click_filtrar()

        # Export to Excel
        os.makedirs(EXTRACOES_DIR, exist_ok=True)
        filepath = await portal.export_to_excel(EXTRACOES_DIR)
        logger.info(f"Extraction complete: {filepath}")

        success = True

    except Exception as e:
        logger.error(f"Error: {e}", error=e)
        raise e

    finally:
        if browser_active:
            logger.info("Closing browser...")
            await navegador.stop_browser()
        logger.finish(success=success)


if __name__ == "__main__":
    asyncio.run(main())
