# CCTV Violation Management System

A Streamlit web app and WhatsApp notification service for managing CCTV violation cases stored in Snowflake. The Stack includes Snowflake for data, Streamlit for CRUD and dashboards, and a WhatsApp worker (Flask health check) that pushes alerts for new violations.

## Setup
- Python 3.10+ recommended. Create a virtual env if desired: `python -m venv .venv` then `./.venv/Scripts/Activate` (Windows).
- Install dependencies: `pip install -r requirements.txt` (use `pip install -r requirements_streamlit.txt` if you only need the UI deps).
- Configuration is loaded from AWS SSM Parameter Store with prefix `/japfa_usercase2_CCTV`; each parameter falls back to matching environment variables (or `.env` when using `python-dotenv`).
- Optional health-check port override via env `PORT` (default 5001).

### Example .env (values omitted)
# Snowflake (all required)
JAPFA_user=
JAPFA_password=
JAPFA_account=
JAPFA_database=
JAPFA_schema=
JAPFA_warehouse=
JAPFA_role=

# WhatsApp / Meta Cloud API
WA_PHONE_ID=
WA_TOKEN=
WA_TEMPLATE_NAME=alert_template
WA_TEMPLATE_LANG=en
# Alternate keys also accepted: WHATSAPP_PHONE_ID, WHATSAPP_TOKEN

# Optional
PORT=5001

## Running
- Streamlit UI: `streamlit run streamlit_app.py` (browser at http://localhost:8501).
- WhatsApp monitor + Flask health check: `python main.py` (starts SQL monitor thread).
- Run both together: `bash run.sh` (starts Streamlit and `uv run main.py` concurrently).
- Syntax check: `python -m py_compile main.py data.py streamlit_app.py`.
- Single test (if pytest installed): `python -m pytest path/to/test.py::test_function`.

## Key Parameters Used in Code
- AWS SSM prefix `/japfa_usercase2_CCTV` (data.py, main.py) for secrets.
- Snowflake connection (data.py, streamlit_app.py): `JAPFA_user`, `JAPFA_password`, `JAPFA_account`, `JAPFA_database`, `JAPFA_schema`, `JAPFA_warehouse`, `JAPFA_role`.
- Snowflake tables: violations table `SWINE_NEW_ALERT`; chat ID table `WHATSAPP_CHAT_IDS`.
- WhatsApp Cloud API (main.py, send_message.py): `WA_PHONE_ID`/`WHATSAPP_PHONE_ID`, `WA_TOKEN`/`WHATSAPP_TOKEN`, `WA_TEMPLATE_NAME` (default `alert_template`), `WA_TEMPLATE_LANG` (default `en`).
- Streamlit link used in WhatsApp copy: constant `STREAMLIT_URL` in `main.py` (update to match deployment).
- Flask health check port: env `PORT` (default 5001).
- Timezone handling: Streamlit stores creation timezone per case (`CREATION_TZ` column) and allows UI filtering; defaults to `Asia/Singapore` with user preference held in `st.session_state['user_tz']`.
- Notification recipients: WhatsApp chat IDs are stored in Snowflake; utility scripts `setup_chat_ids_table.py` and Streamlit "Manage Notifications" page manage them.

## Data Flow Notes
- Violations are read/written to Snowflake; CRUD paths use the stable `ID` column for updates/deletes.
- Adding a violation in Streamlit converts the submitted timestamp from the user-selected timezone to UTC (`EVENT_TIME_UTC`) and saves the original timezone in `CREATION_TZ`.
- The WhatsApp worker polls Snowflake for new rows and sends template messages with case links; unresolved/resolved status is updated via `REPLY` field.
