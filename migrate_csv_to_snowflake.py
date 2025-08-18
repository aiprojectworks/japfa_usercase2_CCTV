import csv
import os
from datetime import datetime
from dotenv import load_dotenv
import snowflake.connector

# Load environment variables (for local development)
load_dotenv()

# Snowflake connection parameters
username = os.getenv("JAPFA_user")
password = os.getenv("JAPFA_password")
account = os.getenv("JAPFA_account")
database = os.getenv("JAPFA_database")
schema = os.getenv("JAPFA_schema")
warehouse = os.getenv("JAPFA_warehouse")
role = os.getenv("JAPFA_role")

# Path to the CSV file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(SCRIPT_DIR, "data", "data.csv")

# Table and column mapping
TABLE_NAME = "SWINE_NEW_ALERT"
CSV_COLUMNS = [
    "时间",           # timestamp
    "厂区",           # factory_area
    "受检环节",       # inspection_section
    "违规与异常类型", # violation_type
    "问题点图片",     # image_url
    "resolved"        # resolved
]
SNOWFLAKE_COLUMNS = [
    "TIMESTAMP",
    "FARM_LOCATION",
    "INSPECTION_AREA",
    "VIOLATION_TYPE",
    "IMAGE_URL",
    "REPLY"
]

def parse_csv_row(row):
    """Convert CSV row to Snowflake-ready tuple, handling types and correct mapping."""
    # Parse timestamp
    timestamp = row[0].strip()
    farm_location = row[1].strip()
    inspection_area = row[2].strip()
    violation_type = row[3].strip()
    image_url = row[4].strip()
    reply = row[5].strip().lower()  # Store as 'true'/'false' string
    return (timestamp, farm_location, inspection_area, violation_type, image_url, reply)

def migrate():
    # Connect to Snowflake
    ctx = snowflake.connector.connect(
        user=username,
        password=password,
        account=account,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
    )
    cs = ctx.cursor()
    inserted = 0
    try:
        # Read CSV
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            # Map header to expected columns
            header_map = {col: idx for idx, col in enumerate(header)}
            # Prepare insert statement
            placeholders = ", ".join(["%s"] * len(SNOWFLAKE_COLUMNS))
            columns = ", ".join(SNOWFLAKE_COLUMNS)
            insert_sql = f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})"
            for row in reader:
                if len(row) < 6 or not row[0].strip():
                    continue
                try:
                    values = parse_csv_row(row)
                    cs.execute(insert_sql, values)
                    inserted += 1
                except Exception as e:
                    print(f"Failed to insert row: {row}\nError: {e}")
        print(f"Migration complete. Inserted {inserted} rows.")
    finally:
        cs.close()
        ctx.close()

def verify():
    """Verify that the number of rows in Snowflake matches the CSV (excluding header and empty rows)."""
    ctx = snowflake.connector.connect(
        user=username,
        password=password,
        account=account,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
    )
    cs = ctx.cursor()
    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            csv_rows = [row for row in reader if len(row) >= 6 and row[0].strip()]
        cs.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        snowflake_count = cs.fetchone()[0]
        print(f"CSV rows: {len(csv_rows)}, Snowflake rows: {snowflake_count}")
        if len(csv_rows) == snowflake_count:
            print("Verification successful: Row counts match.")
        else:
            print("Verification failed: Row counts do not match.")
    finally:
        cs.close()
        ctx.close()

def describe_table():
    """Print the column names and types of the SWINE_NEW_ALERT table."""
    ctx = snowflake.connector.connect(
        user=username,
        password=password,
        account=account,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
    )
    cs = ctx.cursor()
    try:
        print(f"Describing table {TABLE_NAME}:")
        cs.execute(f"DESC TABLE {TABLE_NAME}")
        for row in cs.fetchall():
            print(f"Column: {row[0]}, Type: {row[1]}")
    finally:
        cs.close()
        ctx.close()

if __name__ == "__main__":
    print("Describing SWINE_NEW_ALERT table structure...")
    describe_table()
    print("Starting migration from CSV to Snowflake...")
    migrate()
    print("Verifying migration...")
    verify()
