import asyncio
import threading
import schedule
import time
import logging
from bot import main as bot_main
from scheduler import run_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_scheduler_job():
    """Run scheduler in a separate thread"""
    def job():
        logger.info("Running scheduler...")
        asyncio.run(run_scheduler())

    # Run every day at 09:00
    schedule.every().day.at("09:00").do(job)

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler_job, daemon=True)
    scheduler_thread.start()
    logger.info("Scheduler started in background")

    # Start bot in main thread
    bot_main()
