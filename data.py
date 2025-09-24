from datetime import datetime
from dataclasses import dataclass
from typing import List
import os
import snowflake.connector
from dotenv import load_dotenv
import uuid
import random
from zoneinfo import ZoneInfo

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

def get_system_timezone():
    """Get the system's current timezone"""
    return str(datetime.now().astimezone().tzinfo)

@dataclass
class ViolationRecord:
    timestamp: str
    factory_area: str
    inspection_section: str
    violation_type: str
    image_url: str
    id: str

    resolved: bool = False
    row_index: int = -1
    creation_tz: str = "Asia/Singapore"  # Add this field



    @classmethod
    def from_snowflake_row(cls, row, row_index: int = -1):
        # row: (ID, TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY)
        timestamp_str = row[0]
        factory_area = row[1]
        inspection_section = row[2]
        violation_type = row[3]
        image_url = row[4]
        resolved = (row[5] or "").strip().lower() == "true"
        rec_id = row[6]
        creation_tz=row[7] if len(row) > 7 and row[7] else "Asia/Singapore"


        return cls(
            timestamp=timestamp_str,
            factory_area=factory_area,
            inspection_section=inspection_section,
            violation_type=violation_type,
            image_url=image_url,
            resolved=resolved,
            id=rec_id,
            creation_tz=creation_tz,
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
            cs.execute(f"SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY, ID, CREATION_TZ FROM {TABLE_NAME}")
            rows = cs.fetchall()
            for idx, row in enumerate(rows, start=1):
                record = ViolationRecord.from_snowflake_row(row, idx)
                self.records.append(record)
        finally:
            cs.close()
            conn.close()
        return self.records
    
    def get_available_timezones(self):
        """Get list of timezones that have violations in the database"""
        conn = get_snowflake_connection()
        cs = conn.cursor()
        timezones = []
        try:
            cs.execute(f"SELECT DISTINCT CREATION_TZ FROM {TABLE_NAME} WHERE CREATION_TZ IS NOT NULL ORDER BY CREATION_TZ")
            rows = cs.fetchall()
            timezones = [row[0] for row in rows if row[0]]
        except Exception as e:
            print(f"Error fetching timezones: {e}")
        finally:
            cs.close()
            conn.close()
        return timezones

    def get_records_by_timezone(self, timezone_filter: str = None) -> List[ViolationRecord]:
        """Get violation records filtered by timezone"""
        conn = get_snowflake_connection()
        cs = conn.cursor()
        records = []
        try:
            if timezone_filter and timezone_filter != "All Timezones":
                cs.execute(
                    f"""SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, 
                    IMAGE_URL, REPLY, ID, CREATION_TZ 
                    FROM {TABLE_NAME} 
                    WHERE CREATION_TZ = %s 
                    ORDER BY TRY_TO_TIMESTAMP_NTZ(TIMESTAMP) DESC, ID DESC""",
                    (timezone_filter,)
                )
            else:
                # Return all records if no filter or "All Timezones" selected
                cs.execute(
                    f"""SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, 
                    IMAGE_URL, REPLY, ID, CREATION_TZ 
                    FROM {TABLE_NAME} 
                    ORDER BY TRY_TO_TIMESTAMP_NTZ(TIMESTAMP) DESC, ID DESC"""
                )
            
            rows = cs.fetchall()
            for idx, row in enumerate(rows, start=1):
                records.append(ViolationRecord.from_snowflake_row(row, idx))
        except Exception as e:
            print(f"Error fetching records by timezone: {e}")
        finally:
            cs.close()
            conn.close()
        return records

    def get_unresolved_records_by_timezone(self, timezone_filter: str = None) -> List[ViolationRecord]:
        """Get unresolved violation records filtered by timezone"""
        conn = get_snowflake_connection()
        cs = conn.cursor()
        records = []
        try:
            if timezone_filter and timezone_filter != "All Timezones":
                cs.execute(
                    f"""
                    SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA,
                        VIOLATION_TYPE, IMAGE_URL, REPLY, ID, CREATION_TZ
                    FROM {TABLE_NAME}
                    WHERE (REPLY IS NULL OR LOWER(REPLY) != 'true')
                    AND CREATION_TZ = %s
                    ORDER BY TRY_TO_TIMESTAMP_NTZ(TIMESTAMP) DESC, ID DESC
                    """,
                    (timezone_filter,)
                )
            else:
                # Return all unresolved records if no filter or "All Timezones" selected
                cs.execute(
                    f"""
                    SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA,
                        VIOLATION_TYPE, IMAGE_URL, REPLY, ID, CREATION_TZ
                    FROM {TABLE_NAME}
                    WHERE REPLY IS NULL OR LOWER(REPLY) != 'true'
                    ORDER BY TRY_TO_TIMESTAMP_NTZ(TIMESTAMP) DESC, ID DESC
                    """
                )
            
            rows = cs.fetchall()
            for idx, row in enumerate(rows, start=1):
                records.append(ViolationRecord.from_snowflake_row(row, idx))
        except Exception as e:
            print(f"Error fetching unresolved records by timezone: {e}")
        finally:
            cs.close()
            conn.close()
        return records

        
    def get_records_by_violation_type(self, violation_type: str) -> List[ViolationRecord]:
        conn = get_snowflake_connection()
        cs = conn.cursor()
        records = []
        try:
            cs.execute(
                f"SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY, ID, CREATION_TZ FROM {TABLE_NAME} WHERE VIOLATION_TYPE = %s",
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
                f"SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY, ID, CREATION_TZ FROM {TABLE_NAME} WHERE FARM_LOCATION = %s",
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
        case_id = record.id 

        conn = get_snowflake_connection()
        cs = conn.cursor()
        # try:
        #     cs.execute(
        #         f"""UPDATE {TABLE_NAME}
        #         SET REPLY = %s
        #         WHERE ID  %s, TIMESTAMP = %s AND FARM_LOCATION = %s AND INSPECTION_AREA = %s AND VIOLATION_TYPE = %s AND IMAGE_URL = %s""",
        #         (str(resolved).lower(), record.id, record.timestamp, record.factory_area, record.inspection_section, record.violation_type, record.image_url)
        #     )
        #     conn.commit()
        #     # Update in-memory record
        #     record.resolved = resolved
        #     return True
        try:
            cs.execute(
                f"UPDATE {TABLE_NAME} SET REPLY = %s WHERE ID = %s",
                (str(resolved).lower(), case_id)
            )
            conn.commit()
            rc = getattr(cs, "rowcount", 0) or 0
            if rc > 0:
                record.resolved = resolved   # update in-memory copy
            return rc > 0
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
                f"""
                SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA,
                    VIOLATION_TYPE, IMAGE_URL, REPLY, ID, CREATION_TZ
                FROM {TABLE_NAME}
                WHERE REPLY IS NULL OR LOWER(REPLY) != 'true'
                ORDER BY TRY_TO_TIMESTAMP_NTZ(TIMESTAMP) DESC, ID DESC
                """
            )
            rows = cs.fetchall()
            for idx, row in enumerate(rows, start=1):
                records.append(ViolationRecord.from_snowflake_row(row, idx))
        finally:
            cs.close()
            conn.close()
        return records
    
    def add_random_violation_from_db(self, use_now_timestamp: bool = True, mark_unresolved: bool = True):
        """
        Pick one random row already in SWINE_NEW_ALERT and re-insert it.
        Returns a ViolationRecord (row_index = -1) or None on failure.
        """
        conn = get_snowflake_connection()  # <- Added connection
        cs = conn.cursor()    
        try:
            # 1) get one random source row
            cs.execute(
                f"""SELECT TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY, ID, CREATION_TZ
                    FROM {TABLE_NAME}
                    ORDER BY RANDOM()
                    LIMIT 1"""
            )
            row = cs.fetchone()
            if not row:
                return None

            src = ViolationRecord.from_snowflake_row(row)
            # 2) decide values for the clone
            # timestamp_str = (
            #     datetime.now().strftime("%m/%d/%y %I:%M %p") if use_now_timestamp else src.timestamp
            # )
            system_tz = get_system_timezone()
            # Create timestamp using system timezone
            if use_now_timestamp:
                # Create current time in system timezone
                now_local = datetime.now(ZoneInfo(system_tz))
                timestamp_str = now_local.strftime("%m/%d/%y %I:%M %p")
            else:
                timestamp_str = src.timestamp
                
            reply_val = "false" if mark_unresolved else ("true" if src.resolved else "false")
            new_id = str(uuid.uuid4())


            # 3) insert the clone
            cs.execute(
                f"""
                INSERT INTO {TABLE_NAME}
                (TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY, ID, CREATION_TZ)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (timestamp_str, src.factory_area, src.inspection_section,
                src.violation_type, src.image_url, reply_val, new_id, system_tz)
            )
            conn.commit()

            # 4) return the values we just wrote
            return ViolationRecord(
                timestamp=timestamp_str,
                factory_area=src.factory_area,
                inspection_section=src.inspection_section,
                violation_type=src.violation_type,
                image_url=src.image_url,
                resolved=(reply_val == "true"),
                id=new_id,
                creation_tz=system_tz,
                row_index=-1,
            )
        except Exception as e:
            print(f"Error cloning random violation: {e}")
            return None
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
