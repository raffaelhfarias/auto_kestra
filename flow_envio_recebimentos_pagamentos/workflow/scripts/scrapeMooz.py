import asyncio
import json
import os
import sys
from datetime import datetime

# Adjust path to find sibling modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from dotenv import load_dotenv
from workflow.components.navegador import Navegador
from workflow.components.wide_logger import WideLogger
from workflow.components.data_cleaners import parse_brl
from workflow.pages.moozCartoes import MoozCartoesPage

load_dotenv()

EXTRACOES_DIR = os.path.join(os.path.dirname(__file__), '../../extracoes')

async def main():
    logger = WideLogger("ScrapeMoozService")
    logger.info("Starting Mooz extraction...")

    navegador = Navegador()
    browser_active = False
    success = False

    try:
        # User credentials
        user_login = os.getenv("LOGIN_MOOZCARTOES")
        user_pass = os.getenv("PASS_MOOZCARTOES")
        
        if not user_login or not user_pass:
            raise ValueError("Mooz credentials not found in .env (LOGIN_MOOZCARTOES, PASS_MOOZCARTOES)")

        # Setup browser
        logger.info("Setting up browser...")
        page = await navegador.setup_browser()
        browser_active = True

        mooz_page = MoozCartoesPage(page, logger)

        # Login
        await mooz_page.login(user_login, user_pass)

        # Get Merchants
        ids = await mooz_page.get_merchant_ids()
        
        all_data = []

        for mid in ids:
            logger.info(f"Processing Merchant ID: {mid}")
            
            # Select Merchant & Navigate
            await mooz_page.select_merchant(mid)
            await mooz_page.navigate_to_payments()
            
            # Extract Current Month
            data_current = await mooz_page.extract_calendar_data()
            if data_current:
                data_current['merchant_id'] = mid
                data_current['scraped_at'] = datetime.now().isoformat()
                all_data.append(data_current)
            
            # Navigate to Next Month & Extract
            await mooz_page.navigate_to_next_month()
            
            data_next = await mooz_page.extract_calendar_data()
            if data_next:
                data_next['merchant_id'] = mid
                data_next['scraped_at'] = datetime.now().isoformat()
                all_data.append(data_next)
                
            # Navigate back to selection for next iteration
            await mooz_page.navigate_to_select_merchant()
            
        # Clean financial data: add numeric 'value_num' field
        for entry in all_data:
            for day in entry.get('days', []):
                day['value_num'] = parse_brl(day.get('value', ''))

        # Save results with partitioning and timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        mooz_dir = os.path.join(EXTRACOES_DIR, 'mooz')
        os.makedirs(mooz_dir, exist_ok=True)
        
        filename = f"mooz_{timestamp}.json"
        filepath = os.path.join(mooz_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Saved data to mooz/{filename}")
        success = True

    except Exception as e:
        logger.error(f"Error in Mooz extraction: {e}")
        raise e

    finally:
        if browser_active:
            logger.info("Closing browser...")
            await navegador.stop_browser()
        logger.finish(success=success)

if __name__ == "__main__":
    asyncio.run(main())
