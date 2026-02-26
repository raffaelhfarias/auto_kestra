import asyncio
import json
import os
import sys
from datetime import datetime, date

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from dotenv import load_dotenv
from workflow.components.navegador import Navegador
from workflow.components.wide_logger import WideLogger
from workflow.components.data_cleaners import parse_brl, parse_titulos
from workflow.components.log_setup import setup_file_logging
from workflow.pages.calendarioCar import CalendarioCarPage, CS_CODES, MESES

load_dotenv()

EXTRACOES_DIR = os.path.join(os.path.dirname(__file__), '../../extracoes')


def fix_scheduled_status(entries: list[dict], logger: WideLogger) -> int:
    """
    Corrects dates that the CAR system incorrectly reports as SCHEDULED
    when the date has already passed (should be TRANSFERRED).

    The CAR calendar has a known bug where certain past dates remain
    with status 'SCHEDULED' instead of being updated to 'TRANSFERRED'.
    This function compares each day's date against today and fixes the status.

    Args:
        entries: List of extraction result dicts containing 'days' lists.
        logger: Logger instance for reporting corrections.

    Returns:
        Number of corrections applied.
    """
    today = date.today()
    corrections = 0

    for entry in entries:
        for day in entry.get("days", []):
            day_status = day.get("status", "")
            day_date_str = day.get("date", "")

            if day_status != "SCHEDULED" or not day_date_str:
                continue

            try:
                # Date format in the JSON: "dd-mm-yyyy"
                day_date = datetime.strptime(day_date_str, "%d-%m-%Y").date()
            except ValueError:
                logger.error(f"Could not parse date '{day_date_str}', skipping correction.")
                continue

            if day_date < today:
                day["status"] = "TRANSFERRED"
                day["status_corrected"] = True
                corrections += 1
                logger.info(
                    f"Corrected status for {day_date_str}: SCHEDULED → TRANSFERRED "
                    f"(value: {day.get('value', 'N/A')})"
                )

    return corrections


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

                except Exception as e:
                    logger.error(f"Failed to extract {label}: {e}")
                    # If browser/page is closed, break out of the entire loop
                    if "Target page, context or browser has been closed" in str(e):
                        logger.error("Browser closed unexpectedly. Saving data collected so far.")
                        break
                    continue
            else:
                # Only executed if inner loop did NOT break
                continue
            # Inner loop broke — break outer loop too
            break

        # Clean financial data: add numeric fields
        for entry in all_results:
            entry['total_recebimentos_num'] = parse_brl(entry.get('total_recebimentos', ''))
            entry['total_agendamentos_num'] = parse_brl(entry.get('total_agendamentos', ''))
            for day in entry.get('days', []):
                day['value_num'] = parse_brl(day.get('value', ''))
                day['titulos_num'] = parse_titulos(day.get('titulos', ''))

        # Fix CAR calendar bug: SCHEDULED on past dates → TRANSFERRED
        corrections = fix_scheduled_status(all_results, logger)
        if corrections > 0:
            logger.info(f"Applied {corrections} status correction(s) for past dates.")
        else:
            logger.info("No status corrections needed.")

        # Save results (overwrites single file for Power BI compatibility)
        car_dir = os.path.join(EXTRACOES_DIR, 'car')
        os.makedirs(car_dir, exist_ok=True)
        
        filepath = os.path.join(car_dir, "car.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(all_results)} extractions to car/car.json (overwritten)")

        logger.add_context("total_extractions", len(all_results))
        logger.add_context("status_corrections", corrections)
        success = len(all_results) > 0

    except Exception as e:
        logger.error(f"Error: {e}", error=e)
        raise e

    finally:
        if browser_active:
            logger.info("Closing browser...")
            await navegador.stop_browser()
        logger.finish(success=success)


if __name__ == "__main__":
    setup_file_logging("scrapeCar")
    asyncio.run(main())
