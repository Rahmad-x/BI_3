import logging
import os
from datetime import datetime

os.makedirs("logs", exist_ok=True)

log_filename = (
    f"logs/etl_{datetime.now().strftime('%Y%m%d')}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("GRAB_ETL")