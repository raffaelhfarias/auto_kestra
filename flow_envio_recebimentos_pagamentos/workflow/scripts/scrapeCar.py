import asyncio
import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from dotenv import load_dotenv
from workflow.components.navegador import Navegador
from workflow.components.wide_logger import WideLogger
from workflow.pages.calendarioCar import CalendarioCarPage, CS_CODES, MESES

load_dotenv()

EXTRACOES_DIR = os.path.join(os.path.dirname(__file__), '../../extracoes')


async def main():
    logger = WideLogger("ScrapeCarService")
    logger.info("Starting CAR extraction...")

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

        calendario = CalendarioCarPage(page, logger)

        # Login & navigate
        await calendario.login(user_login, user_pass)
        await calendario.navigate_to_calendar()
        await calendario.dismiss_popups()

        # Determine periods
        periods = CalendarioCarPage.get_extraction_periods()
        logger.info(f"Periods to extract: {periods}")
        logger.add_context("periods", [f"{MESES[m]}/{y}" for m, y in periods])

        os.makedirs(EXTRACOES_DIR, exist_ok=True)
        all_results = []

        for cs_code in CS_CODES:
            for month, year in periods:
                label = f"CS={cs_code} | {MESES[month]}/{year}"
                logger.info(f"─── Extracting {label} ───")

                try:
                    await calendario.select_filters(cs_code, month, year)
                except Exception as e:
                    logger.error(f"Filter selection failed for {label}: {e}")
                    continue

                loaded = await calendario.click_buscar()
                if not loaded:
                    logger.error(f"Calendar did not load for {label}")
                    continue

                data = await calendario.extract_calendar_data()
                data["cs_code"] = cs_code
                data["month"] = MESES[month]
                data["month_number"] = month
                data["year"] = year
                data["extraction_date"] = datetime.now().isoformat()

                all_results.append(data)

                all_results.append(data)
                # Individual file saving removed as requested

        # Save combined file
        combined_path = os.path.join(EXTRACOES_DIR, "calendarioCar.json")
        with open(combined_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved combined file with {len(all_results)} extractions to calendarioCar.json")

        logger.add_context("total_extractions", len(all_results))
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
