
import os
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()


# ==========================================
# 1. KONEKSI DATABASE
# ==========================================

def create_connection(prefix):
    host = os.getenv(f"{prefix}_HOST")
    port = os.getenv(f"{prefix}_PORT")
    user = os.getenv(f"{prefix}_USER")
    password = os.getenv(f"{prefix}_PASSWORD", "")
    database = os.getenv(f"{prefix}_DATABASE")

    url = (
        f"mysql+pymysql://{user}:{password}"
        f"@{host}:{port}/{database}"
    )

    return create_engine(url)


source_engine = create_connection("SOURCE")


# ==========================================
# 2. EXTRACT
# ==========================================

source_tables = [
    "CUSTOMER",
    "DRIVER",
    "VEHICLE",
    "LOCATION",
    "PAYMENT_METHOD",
    "RIDE_TRANSACTION",
    "PAYMENT_TRANSACTION",
    "DRIVER_ACTIVITY",
    "RIDE_RATING",
    "DRIVER_LOCATION_HISTORY"
]

data = {}

print("\n=== EXTRACT DATA OLTP ===")

for table in source_tables:
    df = pd.read_sql_query(
        f"SELECT * FROM `{table}`",
        source_engine
    )

    data[table] = df

    print(f"{table}: {len(df)} baris")


# ==========================================
# 3. TRANSFORM - CLEANING
# ==========================================

def clean_text(df):
    df = df.copy()

    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].apply(
            lambda x: x.strip() if isinstance(x, str) else x
        )

        df[col] = df[col].replace("", pd.NA)

    return df


for table in data:
    data[table] = clean_text(data[table])


# Konversi kolom tanggal dan waktu

datetime_columns = {
    "CUSTOMER": ["birth_date", "registration_date"],
    "DRIVER": ["registration_date"],
    "RIDE_TRANSACTION": [
        "request_time",
        "pickup_time",
        "completed_time"
    ],
    "PAYMENT_TRANSACTION": ["payment_time"],
    "DRIVER_ACTIVITY": ["activity_time"],
    "RIDE_RATING": ["rating_time"],
    "DRIVER_LOCATION_HISTORY": ["recorded_time"]
}

for table, columns in datetime_columns.items():
    for col in columns:
        data[table][col] = pd.to_datetime(
            data[table][col],
            errors="coerce"
        )


# ==========================================
# 4. TRANSFORM - DIMENSION
# ==========================================

# DIM_CUSTOMER

dim_customer = (
    data["CUSTOMER"][
        ["customer_id", "customer_name", "gender"]
    ]
    .drop_duplicates(subset=["customer_id"])
    .copy()
)


# DIM_DRIVER

dim_driver = (
    data["DRIVER"][
        ["driver_id", "driver_name"]
    ]
    .drop_duplicates(subset=["driver_id"])
    .copy()
)


# DIM_VEHICLE

dim_vehicle = (
    data["VEHICLE"][
        [
            "vehicle_id",
            "driver_id",
            "vehicle_type",
            "brand",
            "vehicle_number"
        ]
    ]
    .drop_duplicates(subset=["vehicle_id"])
    .copy()
)


# DIM_LOCATION

dim_location = (
    data["LOCATION"][
        [
            "location_id",
            "location_name",
            "city",
            "latitude",
            "longitude",
            "geohash"
        ]
    ]
    .drop_duplicates(subset=["location_id"])
    .copy()
)


# DIM_RIDE_STATUS

dim_ride_status = pd.DataFrame({
    "status_code": (
        data["RIDE_TRANSACTION"]["status"]
        .dropna()
        .unique()
    )
})

dim_ride_status["status_description"] = (
    dim_ride_status["status_code"]
)


# DIM_DRIVER_STATUS

dim_driver_status = pd.DataFrame({
    "status_code": (
        data["DRIVER_LOCATION_HISTORY"]["driver_status"]
        .dropna()
        .unique()
    )
})

dim_driver_status["status_description"] = (
    dim_driver_status["status_code"]
)


# DIM_DATE

date_values = pd.concat([
    data["RIDE_TRANSACTION"]["request_time"].dt.date,
    data["DRIVER_LOCATION_HISTORY"]["recorded_time"].dt.date
]).dropna().drop_duplicates()

dim_date = pd.DataFrame({
    "full_date": pd.to_datetime(date_values)
})

dim_date["date_key"] = (
    dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
)

dim_date["day"] = dim_date["full_date"].dt.day
dim_date["month"] = dim_date["full_date"].dt.month
dim_date["month_name"] = dim_date["full_date"].dt.month_name()
dim_date["quarter"] = dim_date["full_date"].dt.quarter
dim_date["year"] = dim_date["full_date"].dt.year
dim_date["day_name"] = dim_date["full_date"].dt.day_name()


# DIM_TIME

time_values = pd.concat([
    data["RIDE_TRANSACTION"]["request_time"].dt.time,
    data["DRIVER_LOCATION_HISTORY"]["recorded_time"].dt.time
]).dropna().drop_duplicates()

dim_time = pd.DataFrame({
    "full_time": time_values.astype(str)
})

parsed_time = pd.to_datetime(
    dim_time["full_time"],
    format="%H:%M:%S",
    errors="coerce"
)

dim_time["time_key"] = (
    parsed_time.dt.strftime("%H%M%S").astype(int)
)

dim_time["hour"] = parsed_time.dt.hour
dim_time["minute"] = parsed_time.dt.minute

dim_time["time_period"] = pd.cut(
    dim_time["hour"],
    bins=[-1, 5, 10, 14, 17, 21, 23],
    labels=[
        "Dini Hari",
        "Pagi",
        "Siang",
        "Sore",
        "Malam",
        "Larut Malam"
    ]
)


# ==========================================
# 5. TRANSFORM - FACT TABLE
# ==========================================

# FACT_RIDE_REQUEST
# Grain: satu baris per ride request

ride = data["RIDE_TRANSACTION"].copy()

fact_ride_request = pd.DataFrame({
    "ride_id": ride["ride_id"],
    "customer_id": ride["customer_id"],
    "driver_id": ride["driver_id"],
    "pickup_location_id": ride["pickup_location_id"],
    "destination_location_id": ride["destination_location_id"],
    "request_date": ride["request_time"].dt.strftime("%Y-%m-%d"),
    "request_time": ride["request_time"].dt.strftime("%H:%M:%S"),
    "status_code": ride["status"],
    "request_count": 1,
    "distance_km": ride["distance_km"],
    "fare": ride["fare"]
})


# FACT_DRIVER_AVAILABILITY
# Grain: satu baris per observasi lokasi/status driver

history = data["DRIVER_LOCATION_HISTORY"].copy()

fact_driver_availability = pd.DataFrame({
    "location_history_id": history["location_history_id"],
    "driver_id": history["driver_id"],
    "location_id": history["location_id"],
    "observation_date": history["recorded_time"].dt.strftime("%Y-%m-%d"),
    "observation_time": history["recorded_time"].dt.strftime("%H:%M:%S"),
    "status_code": history["driver_status"],
    "driver_count": 1
})


# ==========================================
# 6. VALIDATION
# ==========================================

print("\n=== VALIDATION ===")

print("Ride source:", len(ride))
print("Fact ride:", len(fact_ride_request))

print(
    "Ride ID duplicate:",
    fact_ride_request["ride_id"].duplicated().sum()
)

print(
    "Availability ID duplicate:",
    fact_driver_availability["location_history_id"].duplicated().sum()
)

print(
    "Ride request time invalid:",
    ride["request_time"].isna().sum()
)

print(
    "Driver observation time invalid:",
    history["recorded_time"].isna().sum()
)


# ==========================================
# 7. PREVIEW TRANSFORM
# ==========================================

print("\n=== DIM CUSTOMER ===")
print(dim_customer.head())

print("\n=== DIM DATE ===")
print(dim_date.head())

print("\n=== FACT RIDE REQUEST ===")
print(fact_ride_request.head())

print("\n=== FACT DRIVER AVAILABILITY ===")
print(fact_driver_availability.head())


# ==========================================
# 8. RINGKASAN
# ==========================================

print("\n=== RINGKASAN TRANSFORM ===")

transformed = {
    "DIM_CUSTOMER": dim_customer,
    "DIM_DRIVER": dim_driver,
    "DIM_VEHICLE": dim_vehicle,
    "DIM_LOCATION": dim_location,
    "DIM_DATE": dim_date,
    "DIM_TIME": dim_time,
    "DIM_RIDE_STATUS": dim_ride_status,
    "DIM_DRIVER_STATUS": dim_driver_status,
    "FACT_RIDE_REQUEST": fact_ride_request,
    "FACT_DRIVER_AVAILABILITY": fact_driver_availability
}

for name, df in transformed.items():
    print(f"{name}: {len(df)} baris")

print("\nExtract dan Transform selesai. Belum ada data yang di-load ke DW.")