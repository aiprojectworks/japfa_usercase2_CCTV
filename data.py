from datetime import datetime
from dataclasses import dataclass
from typing import List
import os
import snowflake.connector
from dotenv import load_dotenv

# Load environment variables (for local development or production)
load_dotenv()
username = os.getenv("JAPFA_user")
password = os.getenv("JAPFA_password")
snowflake_account = os.getenv("JAPFA_account")
database = os.getenv("JAPFA_database")
schema = os.getenv("JAPFA_schema")
warehouse = os.getenv("JAPFA_warehouse")
role = os.getenv("JAPFA_role")

TABLE_NAME = "SWINE_NEW_ALERT"
CHAT_IDS_TABLE = "WHATSAPP_CHAT_IDS"

def get_snowflake_connection():
    return snowflake.connector.connect(
        user=username,
        password=password,
        account=snowflake_account,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
    )

@dataclass
class ViolationRecord:
    timestamp: str
    factory_area: str
    inspection_section: str
    violation_type: str
    image_url: str
    resolved: bool = False
    row_index: int = -1

    @classmethod
    def from_snowflake_row(cls, row, row_index: int = -1):
        # row: (TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY)
        timestamp_str = row[0]
        factory_area = row[1]
        inspection_section = row[2]
        violation_type = row[3]
        image_url = row[4]
        resolved = (row[5] or "").strip().lower() == "true"
        return cls(
            timestamp=timestamp_str,
            factory_area=factory_area,
            inspection_section=inspection_section,
            violation_type=violation_type,
            image_url=image_url,
            resolved=resolved,
            row_index=row_index
        )

class DataParser:
    def __init__(self):
        self.records: List[ViolationRecord] = []

    def parse(self) -> List[ViolationRecord]:
        """Fetch all violation records from Snowflake."""
        self.records = []
        conn = get_snowflake_connection()
        cs = conn.cursor()
        try:
            cs.execute(f"SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY FROM {TABLE_NAME}")
            rows = cs.fetchall()
            for idx, row in enumerate(rows, start=1):
                record = ViolationRecord.from_snowflake_row(row, idx)
                self.records.append(record)
        finally:
            cs.close()
            conn.close()
        return self.records

    def get_records_by_violation_type(self, violation_type: str) -> List[ViolationRecord]:
        conn = get_snowflake_connection()
        cs = conn.cursor()
        records = []
        try:
            cs.execute(
                f"SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY FROM {TABLE_NAME} WHERE VIOLATION_TYPE = %s",
                (violation_type,)
            )
            rows = cs.fetchall()
            for idx, row in enumerate(rows, start=1):
                records.append(ViolationRecord.from_snowflake_row(row, idx))
        finally:
            cs.close()
            conn.close()
        return records

    def get_records_by_factory_area(self, factory_area: str) -> List[ViolationRecord]:
        conn = get_snowflake_connection()
        cs = conn.cursor()
        records = []
        try:
            cs.execute(
                f"SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY FROM {TABLE_NAME} WHERE FARM_LOCATION = %s",
                (factory_area,)
            )
            rows = cs.fetchall()
            for idx, row in enumerate(rows, start=1):
                records.append(ViolationRecord.from_snowflake_row(row, idx))
        finally:
            cs.close()
            conn.close()
        return records

    def update_resolved_status(self, row_index: int, resolved: bool = True) -> bool:
        """Update the resolved status of a record in Snowflake by row index (1-based)."""
        # Fetch all records to get the timestamp and factory_area for the given row_index
        records = self.parse()
        if not (1 <= row_index <= len(records)):
            return False
        record = records[row_index - 1]
        conn = get_snowflake_connection()
        cs = conn.cursor()
        try:
            cs.execute(
                f"""UPDATE {TABLE_NAME}
                SET REPLY = %s
                WHERE TIMESTAMP = %s AND FARM_LOCATION = %s AND INSPECTION_AREA = %s AND VIOLATION_TYPE = %s AND IMAGE_URL = %s""",
                (str(resolved).lower(), record.timestamp, record.factory_area, record.inspection_section, record.violation_type, record.image_url)
            )
            conn.commit()
            # Update in-memory record
            record.resolved = resolved
            return True
        except Exception as e:
            print(f"Error updating Snowflake: {e}")
            return False
        finally:
            cs.close()
            conn.close()

    def get_unresolved_records(self) -> List[ViolationRecord]:
        """Get all unresolved violation records from Snowflake."""
        conn = get_snowflake_connection()
        cs = conn.cursor()
        records = []
        try:
            cs.execute(
                f"SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY FROM {TABLE_NAME} WHERE REPLY IS NULL OR LOWER(REPLY) != 'true'"
            )
            rows = cs.fetchall()
            for idx, row in enumerate(rows, start=1):
                records.append(ViolationRecord.from_snowflake_row(row, idx))
        finally:
            cs.close()
            conn.close()
        return records

    def add_example_violation(self) -> ViolationRecord:
        """Add an example violation to Snowflake for testing."""
        import random
        # Example violation data
        example_violations = [
            {
                "area": "KP2,Jabar,Indonesia",
                "section": "Fumigasi Barang Shower Kandang",
                "violation": "Shoes are not on the shoe rack​ (ENG) / Sepatu tidak diletakkan di rak sepatu(BAHASA INDO)",
                "image": "https://files.catbox.moe/vvx882.mp4"
            },
            # {
            #     "area": "KP2, Warehouse B",
            #     "section": "Loading Dock",
            #     "violation": "叉车违规操作",
            #     "image": "https://files.catbox.moe/2hf0ji.mp4"
            # },
            # {
            #     "area": "KP3, Quality Control",
            #     "section": "Inspection Area",
            #     "violation": "工作区域未清洁",
            #     "image": "https://ohiomagazine.imgix.net/sitefinity/images/default-source/articles/2021/july-august-2021/farms-slate-run-farm-sheep-credit-megan-leigh-barnard.jpg?sfvrsn=59d8a238_8&w=960&auto=compress%2Cformat"
            # }
        ]
        violation_data = random.choice(example_violations)
        now = datetime.now()
        timestamp_str = now.strftime("%m/%d/%y %I:%M %p")
        conn = get_snowflake_connection()
        cs = conn.cursor()
        try:
            cs.execute(
                f"""INSERT INTO {TABLE_NAME}
                (TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    timestamp_str,
                    violation_data["area"],
                    violation_data["section"],
                    violation_data["violation"],
                    violation_data["image"],
                    "false"
                )
            )
            conn.commit()
            return ViolationRecord(
                timestamp=timestamp_str,
                factory_area=violation_data["area"],
                inspection_section=violation_data["section"],
                violation_type=violation_data["violation"],
                image_url=violation_data["image"],
                resolved=False,
                row_index=-1
            )
        except Exception as e:
            print(f"Error adding example violation to Snowflake: {e}")
            return ViolationRecord(
                timestamp=timestamp_str,
                factory_area="Error",
                inspection_section="Error",
                violation_type="Failed to add violation",
                image_url="",
                resolved=False,
                row_index=-1
            )
        finally:
            cs.close()
            conn.close()

    def add_chat_id(self, chat_id: str) -> bool:
        """Add a WhatsApp chat ID (numeric phone) to Snowflake for notifications."""
        if not isinstance(chat_id, str) or not chat_id.isdigit() or not (8 <= len(chat_id) <= 15):
            return False

        conn = get_snowflake_connection()
        cs = conn.cursor()
        try:
            # Check if chat_id already exists
            cs.execute(f"SELECT COUNT(*) FROM {CHAT_IDS_TABLE} WHERE CHAT_ID = %s", (chat_id,))
            row = cs.fetchone()
            if row and row[0] > 0:
                return False  # Already exists

            # Insert new chat_id
            cs.execute(
                f"INSERT INTO {CHAT_IDS_TABLE} (CHAT_ID, CREATED_AT, ACTIVE) VALUES (%s, %s, %s)",
                (chat_id, datetime.now().isoformat(), True)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding chat ID to Snowflake: {e}")
            return False
        finally:
            cs.close()
            conn.close()

    def get_active_chat_ids(self) -> List[str]:
        """Get all active chat IDs from Snowflake."""
        conn = get_snowflake_connection()
        cs = conn.cursor()
        chat_ids = []
        try:
            cs.execute(f"SELECT CHAT_ID FROM {CHAT_IDS_TABLE} WHERE ACTIVE = true")
            rows = cs.fetchall()
            chat_ids = [row[0] for row in rows]
        except Exception as e:
            print(f"Error fetching chat IDs from Snowflake: {e}")
        finally:
            cs.close()
            conn.close()
        return chat_ids

    def remove_chat_id(self, chat_id: str) -> bool:
        """Remove a WhatsApp chat ID from Snowflake (set as inactive)."""
        conn = get_snowflake_connection()
        cs = conn.cursor()
        try:
            cs.execute(
                f"UPDATE {CHAT_IDS_TABLE} SET ACTIVE = false WHERE CHAT_ID = %s",
                (chat_id,)
            )
            conn.commit()
            rc = getattr(cs, 'rowcount', 0) or 0
            return rc > 0
        except Exception as e:
            print(f"Error removing chat ID from Snowflake: {e}")
            return False
        finally:
            cs.close()
            conn.close()

    def create_chat_ids_table(self):
        """Create the WhatsApp chat IDs table if it doesn't exist."""
        conn = get_snowflake_connection()
        cs = conn.cursor()
        try:
            cs.execute(f"""
                CREATE TABLE IF NOT EXISTS {CHAT_IDS_TABLE} (
                    CHAT_ID VARCHAR(255) PRIMARY KEY,
                    CREATED_AT TIMESTAMP,
                    ACTIVE BOOLEAN DEFAULT TRUE
                )
            """)
            conn.commit()
            print(f"Table {CHAT_IDS_TABLE} created or already exists.")
        except Exception as e:
            print(f"Error creating chat IDs table: {e}")
        finally:
            cs.close()
            conn.close()
