import os
from dotenv import load_dotenv
import snowflake.connector

# Load environment variables
load_dotenv()

# Snowflake connection parameters
username = os.getenv("JAPFA_user")
password = os.getenv("JAPFA_password")
account = os.getenv("JAPFA_account")
database = os.getenv("JAPFA_database")
schema = os.getenv("JAPFA_schema")
warehouse = os.getenv("JAPFA_warehouse")
role = os.getenv("JAPFA_role")

CHAT_IDS_TABLE = "WHATSAPP_CHAT_IDS"

def create_chat_ids_table():
    """Create the WhatsApp chat IDs table in Snowflake."""
    conn = snowflake.connector.connect(
        user=username,
        password=password,
        account=account,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
    )
    cs = conn.cursor()
    try:
        # Create the table
        cs.execute(f"""
            CREATE TABLE IF NOT EXISTS {CHAT_IDS_TABLE} (
                CHAT_ID VARCHAR(255) PRIMARY KEY,
                CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
                ACTIVE BOOLEAN DEFAULT TRUE
            )
        """)
        conn.commit()
        print(f"✅ Table {CHAT_IDS_TABLE} created successfully.")

        # Insert default chat IDs (the ones currently hardcoded in main.py)
        default_chat_ids = [
            "6581899220",
            "6597607916"
        ]

        for chat_id in default_chat_ids:
            try:
                cs.execute(
                    f"INSERT INTO {CHAT_IDS_TABLE} (CHAT_ID, ACTIVE) VALUES (%s, %s)",
                    (chat_id, True)
                )
                print(f"✅ Added default chat ID: {chat_id}")
            except Exception as e:
                if "Duplicate key" in str(e) or "already exists" in str(e).lower():
                    print(f"ℹ️ Chat ID {chat_id} already exists, skipping.")
                else:
                    print(f"❌ Error adding {chat_id}: {e}")

        conn.commit()

        # Verify the table and data
        cs.execute(f"SELECT * FROM {CHAT_IDS_TABLE}")
        rows = cs.fetchall()
        print(f"\n📊 Current chat IDs in database:")
        for row in rows:
            status = "Active" if row[2] else "Inactive"
            print(f"  - {row[0]} | Created: {row[1]} | Status: {status}")

    except Exception as e:
        print(f"❌ Error creating table: {e}")
    finally:
        cs.close()
        conn.close()

def describe_table():
    """Describe the chat IDs table structure."""
    conn = snowflake.connector.connect(
        user=username,
        password=password,
        account=account,
        warehouse=warehouse,
        database=database,
        schema=schema,
        role=role,
    )
    cs = conn.cursor()
    try:
        print(f"📋 Describing table {CHAT_IDS_TABLE}:")
        cs.execute(f"DESC TABLE {CHAT_IDS_TABLE}")
        for row in cs.fetchall():
            print(f"  Column: {row[0]} | Type: {row[1]} | Nullable: {row[2]} | Default: {row[3]}")
    except Exception as e:
        print(f"❌ Error describing table: {e}")
    finally:
        cs.close()
        conn.close()

if __name__ == "__main__":
    print("🚀 Setting up WhatsApp chat IDs table in Snowflake...")
    create_chat_ids_table()
    print("\n📋 Table structure:")
    describe_table()
    print("\n✅ Setup complete!")
