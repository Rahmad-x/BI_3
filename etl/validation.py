from sqlalchemy import text
from etl.config import create_connection
from etl.etl_logger import logger

source_engine = create_connection("SOURCE")
target_engine = create_connection("TARGET")

tables = {
    "RIDE_TRANSACTION": "FACT_RIDE_REQUEST",
    "DRIVER_LOCATION_HISTORY": "FACT_DRIVER_AVAILABILITY"
}

logger.info("=== VALIDATION START ===")

for source_table, target_table in tables.items():

    source_query = f"SELECT COUNT(*) FROM `{source_table}`"
    target_query = f"SELECT COUNT(*) FROM `{target_table}`"

    with source_engine.connect() as conn:
        source_count = conn.execute(
            text(source_query)
        ).scalar()

    with target_engine.connect() as conn:
        target_count = conn.execute(
            text(target_query)
        ).scalar()

    logger.info(
        f"{source_table} -> {target_table} | "
        f"Source: {source_count} | DW: {target_count}"
    )

    if source_count == target_count:
        logger.info(f"{target_table}: VALID")
    else:
        logger.warning(f"{target_table}: COUNT MISMATCH")

logger.info("=== VALIDATION FINISHED ===")