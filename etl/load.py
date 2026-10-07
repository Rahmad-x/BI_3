
import pandas as pd
from sqlalchemy import text

from etl.extract_transform import transformed
from etl.config import create_connection

target_engine = create_connection("TARGET")
# ==========================================
# 1. HELPER UNTUK INSERT / UPSERT
# ==========================================

def load_dimension(table_name, df, key_column):
    """
    Memasukkan data dimensi.
    Jika natural key sudah ada, data diperbarui.
    """

    if df.empty:
        print(f"{table_name}: tidak ada data")
        return

    columns = list(df.columns)

    insert_columns = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(f":{c}" for c in columns)

    update_columns = [
        c for c in columns if c != key_column
    ]

    update_clause = ", ".join(
        f"`{c}` = VALUES(`{c}`)"
        for c in update_columns
    )

    sql = f"""
        INSERT INTO `{table_name}` ({insert_columns})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """

    records = df.astype(object).where(
        pd.notna(df), None
    ).to_dict(orient="records")

    with target_engine.begin() as conn:
        conn.execute(text(sql), records)

    print(f"{table_name}: {len(records)} data diproses")


# ==========================================
# 2. LOAD DIMENSION
# ==========================================

print("\n=== LOAD DIMENSION ===")

# Natural key masing-masing dimensi
dimension_config = [
    ("DIM_CUSTOMER", "customer_id"),
    ("DIM_DRIVER", "driver_id"),
    ("DIM_VEHICLE", "vehicle_id"),
    ("DIM_LOCATION", "location_id"),
    ("DIM_DATE", "date_key"),
    ("DIM_TIME", "time_key"),
    ("DIM_RIDE_STATUS", "status_code"),
    ("DIM_DRIVER_STATUS", "status_code")
]

for table_name, key_column in dimension_config:
    load_dimension(
        table_name,
        transformed[table_name],
        key_column
    )


# ==========================================
# 3. AMBIL MAPPING SURROGATE KEY
# ==========================================

def get_mapping(table, natural_key, surrogate_key):
    query = f"""
        SELECT `{natural_key}`, `{surrogate_key}`
        FROM `{table}`
    """

    df = pd.read_sql_query(query, target_engine)

    return dict(zip(
        df[natural_key],
        df[surrogate_key]
    ))


customer_map = get_mapping(
    "DIM_CUSTOMER", "customer_id", "customer_key"
)

driver_map = get_mapping(
    "DIM_DRIVER", "driver_id", "driver_key"
)

vehicle_map = get_mapping(
    "DIM_VEHICLE", "vehicle_id", "vehicle_key"
)

location_map = get_mapping(
    "DIM_LOCATION", "location_id", "location_key"
)

date_map = get_mapping(
    "DIM_DATE", "date_key", "date_key"
)

time_map = get_mapping(
    "DIM_TIME", "time_key", "time_key"
)

ride_status_map = get_mapping(
    "DIM_RIDE_STATUS", "status_code", "ride_status_key"
)

driver_status_map = get_mapping(
    "DIM_DRIVER_STATUS", "status_code", "driver_status_key"
)


# ==========================================
# 4. LOAD FACT RIDE REQUEST
# ==========================================

print("\n=== LOAD FACT RIDE REQUEST ===")

fact_ride = transformed["FACT_RIDE_REQUEST"].copy()

fact_ride["customer_key"] = fact_ride["customer_id"].map(customer_map)
fact_ride["driver_key"] = fact_ride["driver_id"].map(driver_map)

fact_ride["pickup_location_key"] = (
    fact_ride["pickup_location_id"].map(location_map)
)

fact_ride["destination_location_key"] = (
    fact_ride["destination_location_id"].map(location_map)
)

fact_ride["date_key"] = (
    pd.to_datetime(fact_ride["request_date"])
    .dt.strftime("%Y%m%d")
    .astype(int)
)

fact_ride["time_key"] = (
    fact_ride["request_time"]
    .str.replace(":", "", regex=False)
    .astype(int)
)

fact_ride["ride_status_key"] = (
    fact_ride["status_code"].map(ride_status_map)
)

fact_ride = fact_ride.rename(
    columns={"ride_id": "ride_id"}
)

fact_ride = fact_ride[
    [
        "ride_id",
        "customer_key",
        "driver_key",
        "pickup_location_key",
        "destination_location_key",
        "date_key",
        "time_key",
        "ride_status_key",
        "request_count",
        "distance_km",
        "fare"
    ]
]

print("Ride fact rows:", len(fact_ride))


# ==========================================
# 5. LOAD FACT DRIVER AVAILABILITY
# ==========================================

print("\n=== LOAD FACT DRIVER AVAILABILITY ===")

fact_availability = transformed[
    "FACT_DRIVER_AVAILABILITY"
].copy()

fact_availability["driver_key"] = (
    fact_availability["driver_id"].map(driver_map)
)

fact_availability["location_key"] = (
    fact_availability["location_id"].map(location_map)
)

fact_availability["date_key"] = (
    pd.to_datetime(fact_availability["observation_date"])
    .dt.strftime("%Y%m%d")
    .astype(int)
)

fact_availability["time_key"] = (
    fact_availability["observation_time"]
    .str.replace(":", "", regex=False)
    .astype(int)
)

fact_availability["driver_status_key"] = (
    fact_availability["status_code"].map(driver_status_map)
)

fact_availability = fact_availability[
    [
        "location_history_id",
        "driver_key",
        "location_key",
        "date_key",
        "time_key",
        "driver_status_key",
        "driver_count"
    ]
]

print("Availability fact rows:", len(fact_availability))


# ==========================================
# 6. VALIDASI MAPPING
# ==========================================

for name, df in [
    ("FACT_RIDE_REQUEST", fact_ride),
    ("FACT_DRIVER_AVAILABILITY", fact_availability)
]:
    null_count = df.isna().sum().sum()

    print(f"{name} - NULL hasil mapping: {null_count}")

    if null_count > 0:
        raise ValueError(
            f"Mapping {name} belum lengkap. Load dihentikan."
        )


# ==========================================
# 7. LOAD FACT TABLES
# ==========================================

def load_fact(table_name, df, key_column):
    columns = list(df.columns)

    insert_columns = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(f":{c}" for c in columns)

    update_columns = [
        c for c in columns if c != key_column
    ]

    update_clause = ", ".join(
        f"`{c}` = VALUES(`{c}`)"
        for c in update_columns
    )

    sql = f"""
        INSERT INTO `{table_name}` ({insert_columns})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_clause}
    """

    records = df.astype(object).where(
        pd.notna(df), None
    ).to_dict(orient="records")

    with target_engine.begin() as conn:
        conn.execute(text(sql), records)

    print(f"{table_name}: {len(records)} data diproses")


load_fact(
    "FACT_RIDE_REQUEST",
    fact_ride,
    "ride_id"
)

load_fact(
    "FACT_DRIVER_AVAILABILITY",
    fact_availability,
    "location_history_id"
)

print("\n=== LOAD SELESAI ===")