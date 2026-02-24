import asyncio
import os
import sys
from datetime import datetime

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

        # Export to JSON (overwrites single file for Power BI compatibility)
        boletos_dir = os.path.join(EXTRACOES_DIR, 'boletos')
        os.makedirs(boletos_dir, exist_ok=True)

        # export_to_json currently saves as portalBoletos.json in the target dir
        temp_filepath = await portal.export_to_json(boletos_dir)

        dest_filepath = os.path.join(boletos_dir, "boletos.json")

        # Rename to fixed name (overwrites previous)
        if os.path.exists(temp_filepath):
            if os.path.exists(dest_filepath):
                os.remove(dest_filepath)
            os.rename(temp_filepath, dest_filepath)
            logger.info("Extraction complete: boletos/boletos.json (overwritten)")
        else:
            logger.error(f"Failed to find exported file at {temp_filepath}")

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
