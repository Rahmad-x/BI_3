import subprocess
import sys
from datetime import datetime
from etl.etl_logger import logger

def run_script(script_name):
    logger.info(f"Memulai proses {script_name}")

    result = subprocess.run(
        [sys.executable, script_name],
        capture_output=True,
        text=True
    )

    if result.stdout:
        logger.info(result.stdout)

    if result.returncode != 0:
        logger.error(result.stderr)
        raise RuntimeError(
            f"Proses {script_name} gagal"
        )

    logger.info(f"Proses {script_name} berhasil")


try:
    start_time = datetime.now()

    logger.info("================================")
    logger.info("GRAB ETL PIPELINE STARTED")
    logger.info("================================")

    run_script("load.py")
    run_script("validation.py")

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info("ETL PIPELINE SUCCESS")
    logger.info(f"Total duration: {duration} seconds")

except Exception as e:
    logger.exception(f"ETL PIPELINE FAILED: {e}")
    sys.exit(1)