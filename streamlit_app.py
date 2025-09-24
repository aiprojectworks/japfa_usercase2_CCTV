import streamlit as st
import pandas as pd
from data import DataParser, ViolationRecord
import main as main_mod
import threading
import uuid
import zoneinfo
from datetime import datetime
from zoneinfo import available_timezones, ZoneInfo


# Configure Streamlit page
st.set_page_config(
    page_title="CCTV Violation Management System",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

TZS = sorted(available_timezones())
current = st.session_state.get("user_tz", "Asia/Singapore")
if current not in TZS: current = "UTC"

def pick_user_timezone(
    label="Preferred timezone",
    user_key="user_tz",            # where we store the value in session_state
    widget_key="user_tz_widget",   # unique widget key to avoid collisions
    default="Asia/Singapore",
):
    
    tzs = sorted(zoneinfo.available_timezones())
    start = st.session_state.get(user_key, default if default in tzs else "UTC")
    tz = st.selectbox(label, tzs, index=tzs.index(start), key=widget_key)
    st.session_state[user_key] = tz
    return tz

user_tz = st.session_state.get("user_tz", "Asia/Singapore")




def format_violation_time_with_creation_tz(timestamp_str: str, creation_tz: str = "Asia/Singapore") -> str:
    """
    Format violation timestamp showing the original creation timezone.
    """
    try:
        tz_name = creation_tz.split("/")[-1] if "/" in creation_tz else creation_tz
        return f"{timestamp_str} ({tz_name})"
    except:
        return f"{timestamp_str} (SGT)"
    
class ViolationManager:
    """Enhanced DataParser with additional CRUD operations for Streamlit"""

    def __init__(self):
        self.parser = DataParser()

    def load_data(self, timezone_filter=None):
        """Load violation data from Snowflake and return as DataFrame"""
        if timezone_filter and timezone_filter != "All Timezones":
            records = self.parser.get_records_by_timezone(timezone_filter)
        else:
            records = self.parser.parse()
        if not records:
            return pd.DataFrame(columns=['timestamp', 'factory_area', 'inspection_section', 'violation_type', 'image_url', 'resolved', 'id', 'row_index', 'creation_tz'])
        
        data = []
        for record in records:
            # record.timestamp is a string, keep as is
            data.append({
                'timestamp': record.timestamp,
                'factory_area': record.factory_area,
                'inspection_section': record.inspection_section,
                'violation_type': record.violation_type,
                'image_url': record.image_url,
                'resolved': record.resolved,
                'id': record.id,
                
                'row_index': record.row_index,
                'creation_tz': getattr(record, 'creation_tz', 'Asia/Singapore')  # Include creation timezone
 

            })

        return pd.DataFrame(data)
    
    def get_available_timezones(self):
        """Get list of timezones that have violations"""
        return self.parser.get_available_timezones()

    def add_violation(self, timestamp_str, factory_area, inspection_section, violation_type, image_url, resolved=False):
        """Add a new violation record to Snowflake"""
        try:
            new_id = str(uuid.uuid4())
            # Validate timestamp format
            # Parse timestamp and convert to UTC for storage
            local_dt = datetime.strptime(timestamp_str, "%m/%d/%y %I:%M %p")
            # Assume input is in user's selected timezone
            user_tz = st.session_state.get("user_tz", "Asia/Singapore")
            localized_dt = local_dt.replace(tzinfo=ZoneInfo(user_tz))
            utc_dt = localized_dt.astimezone(ZoneInfo("UTC"))
        
            # Insert into Snowflake
            from snowflake.connector import connect
            conn = self.parser.__class__.__dict__['__init__'].__globals__['get_snowflake_connection']()
            cs = conn.cursor()
            try:
                cs.execute(
                    """INSERT INTO SWINE_NEW_ALERT
                    (TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY, ID, EVENT_TIME_UTC, CREATION_TZ)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        timestamp_str,
                        factory_area,
                        inspection_section,
                        violation_type,
                        image_url,
                        str(resolved).lower(),
                        new_id,
                        utc_dt.isoformat(),
                        user_tz
                    )
                )
                
                conn.commit()
            finally:
                cs.close()
                conn.close()
            return True
        except Exception as e:
            st.error(f"Error adding violation: {e}")
            return False

   
    def delete_violation(self, row_index: int) -> bool:
        """Delete a violation record by stable ID (row_index only selects the row)."""
        try:
            records = self.parser.parse()
            if not (1 <= row_index <= len(records)):
                return False
            record = records[row_index - 1]
            case_id = record.id  # <-- use the ID, not timestamp/etc.

            # If you already import the helper: from data import get_snowflake_connection
            conn = self.parser.__class__.__dict__['__init__'].__globals__['get_snowflake_connection']()


            cs = conn.cursor()
            try:
                cs.execute("DELETE FROM SWINE_NEW_ALERT WHERE ID = %s", (case_id,))
                conn.commit()
                rc = getattr(cs, "rowcount", 0) or 0
                return rc > 0   # only report success if a row was actually deleted
            finally:
                cs.close()
                conn.close()
        except Exception as e:
            st.error(f"Error deleting violation: {e}")
            return False

    def update_violation(self, row_index, timestamp_str, factory_area, inspection_section, violation_type, image_url, resolved):
        """Update an existing violation record in Snowflake by row index (1-based)"""
        try:
            # Validate timestamp format
            datetime.strptime(timestamp_str, "%m/%d/%y %I:%M %p")
            # Fetch all records to get identifying fields for the original row
            records = self.parser.parse()
            if not (1 <= row_index <= len(records)):
                return False
            old_record = records[row_index - 1]
            case_id = old_record.id  # <-- use the stable ID

            conn = self.parser.__class__.__dict__['__init__'].__globals__['get_snowflake_connection']()
            cs = conn.cursor()
            try:
                cs.execute(
                    f"""UPDATE SWINE_NEW_ALERT
                    SET TIMESTAMP = %s, FARM_LOCATION = %s, INSPECTION_AREA = %s, VIOLATION_TYPE = %s, IMAGE_URL = %s, REPLY = %s
                    WHERE ID = %s""",
                    (
                        timestamp_str,
                        factory_area,
                        inspection_section,
                        violation_type,
                        image_url,
                        str(resolved).lower(),
                        # old_record.timestamp,
                        # old_record.factory_area,
                        # old_record.inspection_section,
                        # old_record.violation_type,
                        # old_record.image_url
                        case_id

                    )
                )
                conn.commit()  # <-- don't forget this
                rc = getattr(cs, "rowcount", 0) or 0
                if rc > 0:
                    # update in-memory copy so UI reflects the change immediately
                    old_record.timestamp = timestamp_str
                    old_record.factory_area = factory_area
                    old_record.inspection_section = inspection_section
                    old_record.violation_type = violation_type
                    old_record.image_url = image_url
                    old_record.resolved = resolved
                return rc > 0
            finally:
                cs.close()
                conn.close()
        except Exception as e:
                st.error(f"Error updating violation: {e}")
                return False
        #         conn.commit()
        #         return True
        #     finally:
        #         cs.close()
        #         conn.close()
        # except Exception as e:
        #     st.error(f"Error updating violation: {e}")
        #     return False

        

def start_bot_once():
    if not hasattr(start_bot_once, "started"):
        threading.Thread(target=main_mod.main, daemon=True).start()
        start_bot_once.started = True

# Initialize the violation manager
def get_violation_manager():
    return ViolationManager()

manager = get_violation_manager()

# Handle URL parameters for direct case linking
query_params = st.query_params
case_id = query_params.get("case_id", None)

# Sidebar navigation
st.sidebar.title("🚨 CCTV Violation Management")

# --- Add Example Violation Button ---
if st.sidebar.button("➕ Insert Example Violation", help="Add a demo violation row to Snowflake"):
    example_record = manager.parser.add_random_violation_from_db()
    if example_record:
        st.sidebar.success("✅ Example violation inserted into Snowflake!")
    else:
        st.sidebar.error("❌ Failed to insert example violation.")


    
# --- Add WhatsApp Phone Number for Notifications ---
st.sidebar.markdown("---")
st.sidebar.subheader("Add WhatsApp Number for Alerts")
with st.sidebar.form("add_phone_form"):
    phone_input = st.text_input(
        "Phone Number (with country code, no +, e.g. 6581899220)",
        max_chars=20,
        help="Enter number as countrycode+number, e.g. 6581899220"
    )
    submit_phone = st.form_submit_button("Add Phone Number")
    if submit_phone:
        phone = phone_input.strip()
        if phone.isdigit() and 8 <= len(phone) <= 15:
            chat_id = phone
            # Use the DataParser method directly for Snowflake integration
            added = manager.parser.add_chat_id(chat_id)
            if added:
                st.sidebar.success(f"✅ {chat_id} added for WhatsApp alerts!")
            else:
                st.sidebar.warning(f"ℹ️ {chat_id} is already subscribed or invalid.")
        else:
            st.sidebar.error("❌ Please enter a valid phone number (digits only, include country code).")


# --- Timezone/Regional Filtering ---
st.sidebar.markdown("---")
st.sidebar.subheader("🌍 Regional Filtering")

try:
    available_timezones = manager.get_available_timezones()
    if available_timezones:
        timezone_options = ["All Timezones"] + available_timezones
        
        # Create readable labels
        timezone_labels = {}
        for tz in timezone_options:
            if tz == "All Timezones":
                timezone_labels[tz] = "🌍 All Regions"
            else:
                region = tz.split("/")[-1] if "/" in tz else tz
                timezone_labels[tz] = f"🏙️ {region}"
        
        selected_timezone = st.sidebar.selectbox(
            "Filter by Region:",
            timezone_options,
            format_func=lambda x: timezone_labels[x],
            key="timezone_filter"
        )
        
        # Show violation counts per timezone
        with st.sidebar.expander("📊 Violations by Region"):
            for tz in available_timezones:
                tz_records = manager.parser.get_records_by_timezone(tz)
                unresolved_count = len([r for r in tz_records if not r.resolved])
                total_count = len(tz_records)
                region = tz.split("/")[-1] if "/" in tz else tz
                st.sidebar.write(f"**{region}**: {unresolved_count}/{total_count}")
    else:
        selected_timezone = "All Timezones"
        st.sidebar.info("No violations found")
except Exception as e:
    selected_timezone = "All Timezones"
    st.sidebar.error(f"Error loading timezones: {e}")

# --- View and Manage Chat IDs ---
st.sidebar.markdown("---")
st.sidebar.subheader("📱 Active WhatsApp Numbers")
try:
    active_chat_ids = manager.parser.get_active_chat_ids()
    if active_chat_ids:
        st.sidebar.write(f"**{len(active_chat_ids)} numbers receiving alerts:**")
        for chat_id in active_chat_ids:
            col1, col2 = st.sidebar.columns([3, 1])
            with col1:
                phone_number = chat_id
                st.sidebar.write(f"• {phone_number}")
            with col2:
                if st.sidebar.button("🗑️", key=f"remove_{chat_id}", help="Remove this number"):
                    removed = manager.parser.remove_chat_id(chat_id)
                    if removed:
                        st.sidebar.success("✅ Number removed!")
                        st.rerun()
                    else:
                        st.sidebar.error("❌ Failed to remove number.")
    else:
        st.sidebar.info("No active numbers found.")
except Exception as e:
    st.sidebar.error(f"Error loading chat IDs: {e}")

# If case_id is provided in URL, automatically go to View Cases page
if case_id:
    default_page = "📋 View Cases"
    st.sidebar.info(f"📍 Viewing Case #{case_id}")
else:
    default_page = "📋 View Cases"

page = st.sidebar.selectbox(
    "Select Page",
    ["📋 View Cases", "➕ Add New Case", "✏️ Edit Case", "🗑️ Delete Case", "📊 Dashboard", "📱 Manage Notifications"],
    index=0 if not case_id else 0
)

# Main content area
if page == "📋 View Cases":
    st.title("📋 Violation Cases")

    # Load data
    # Load filtered data
    df = manager.load_data(selected_timezone)

   # Show current filter status
    # Show current filter status
    if selected_timezone != "All Timezones":
        region = selected_timezone.split("/")[-1] if "/" in selected_timezone else selected_timezone
        st.info(f"🌍 Showing violations from: **{region}**")
    
    if df.empty:
        if selected_timezone != "All Timezones":
            region = selected_timezone.split("/")[-1] if "/" in selected_timezone else selected_timezone
            st.info(f"No violation cases found for {region}.")
        else:
            st.info("No violation cases found.")
    else:
        unresolved_df = df[df['resolved'] == False]
    # if df.empty:
    #     st.info("No violation cases found.")
    # else:
    #     # Filter to show only unresolved cases
    #     unresolved_df = df[df['resolved'] == False]

        # If case_id is provided, filter to show only that specific unresolved case
        if case_id:
            try:
                specific_case_df = unresolved_df[unresolved_df['id'] == case_id]
                if not specific_case_df.empty:
                    unresolved_df = specific_case_df
                    # st.success(f"🎯 Showing Case #{case_id} from notification")
                    case_row_index = specific_case_df.iloc[0]['row_index']
                    st.success(f"🎯 Showing Case #{case_row_index} from notification")
                else:
                    st.warning(f"⚠️ Case #{case_id} not found or already resolved.")
            except ValueError:
                st.error("❌ Invalid case ID format")

        if not unresolved_df.empty:
            st.subheader("🚨 Unresolved Cases - Action Required")

            for idx, case in unresolved_df.iterrows():

                # Use the new function to format time with creation timezone
                creation_tz = case.get('creation_tz', 'Asia/Singapore')
                display_time = format_violation_time_with_creation_tz(case['timestamp'], creation_tz)

                # Ensure is_highlighted is always a bool
                is_highlighted = bool(case_id) and str(case['id']) == str(case_id)

                with st.expander(f"{'🔥' if is_highlighted else '🚨'} Case #{case['row_index']} - {case['violation_type']}", expanded=is_highlighted):
                    # if is_highlighted:
                    #     st.success("🎯 This is the case from your notification!")

                    col1, col2, col3 = st.columns([2, 2, 1])

                    with col1:
                        st.write("**Case Details:**")
                        st.write(f"**Case ID:** {case['row_index']}")
                        st.write(f"**Time:** {display_time}")
                        st.write(f"**Area:** {case['factory_area']}")
                        st.write(f"**Section:** {case['inspection_section']}")
                        st.write(f"**Violation:** {case['violation_type']}")
                        st.write(f"**Status:** {'✅ Resolved' if bool(case['resolved']) else '❌ Unresolved'}")

                    with col2:
                        image_url = case['image_url']
                        if isinstance(image_url, str) and image_url.strip():
                            try:
                                st.write("**Evidence Image:**")
                                if image_url.lower().endswith('.mp4'):
                                    st.video(image_url)
                                else:
                                    st.image(image_url, caption="Violation Evidence", width=300)
                            except Exception:
                                st.error("Failed to load image")
                        else:
                            st.info("No image available")

                    with col3:
                        st.write("**Actions:**")

                        # Mark as resolved button
                        if st.button(f"✅ Mark Resolved", key=f"resolve_{case['row_index']}"):
                            # Ensure row_index is int
                            row_index = int(case['row_index'])
                            success = manager.parser.update_resolved_status(row_index, True)
                            if success:
                                st.success("✅ Case marked as resolved!")
                                # Clear URL parameter after resolution
                                if case_id:
                                    st.query_params.clear()
                                st.rerun()
                            else:
                                st.error("❌ Failed to mark as resolved")

                        # Delete case button
                        if st.button(f"🗑️ Delete Case", key=f"delete_{case['row_index']}"):
                            row_index = int(case['row_index'])
                            success = manager.delete_violation(row_index)
                            if success:
                                st.success("✅ Case deleted!")
                                # Clear URL parameter after deletion
                                if case_id:
                                    st.query_params.clear()
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete case")
        else:
            st.info("🎉 No unresolved cases! All violations have been addressed.")

elif page == "➕ Add New Case":
    st.title("➕ Add New Violation Case")

    with st.form("add_case_form"):
        col1, col2 = st.columns(2)

        with col1:
            timestamp_input = st.text_input("Timestamp", value=datetime.now().strftime("%m/%d/%y %I:%M %p"), help="Format: MM/DD/YY HH:MM AM/PM")
            st.caption(f"⏰ Time will be recorded in: {user_tz}")
            factory_area = st.text_input("Factory Area", placeholder="e.g., KP1, Production Line A")
            inspection_section = st.text_input("Inspection Section", placeholder="e.g., Assembly Station 3")

        with col2:
            violation_type = st.text_input("Violation Type", placeholder="e.g., 员工未佩戴安全帽")
            image_url = st.text_input("Image URL", placeholder="https://ohiomagazine.imgix.net/sitefinity/images/default-source/articles/2021/july-august-2021/farms-slate-run-farm-sheep-credit-megan-leigh-barnard.jpg?sfvrsn=59d8a238_8&w=960&auto=compress%2Cformat")
            resolved = st.checkbox("Mark as Resolved")

        submitted = st.form_submit_button("Add Case")

        if submitted:
            if timestamp_input and factory_area and inspection_section and violation_type:
                success = manager.add_violation(timestamp_input, factory_area, inspection_section, violation_type, image_url, resolved)
                if success:
                    st.success("✅ Case added successfully!")
                    # st.balloons()
                else:
                    st.error("❌ Failed to add case. Please check the format.")
            else:
                st.error("Please fill in all required fields.")

elif page == "✏️ Edit Case":
    st.title("✏️ Edit Violation Case")

    # Load filtered data
    df = manager.load_data(selected_timezone)

    # Show current filter status
    if selected_timezone != "All Timezones":
        region = selected_timezone.split("/")[-1] if "/" in selected_timezone else selected_timezone
        st.info(f"🌍 Showing violations from: **{region}**")

    if df.empty:
        st.info("No cases available to edit.")
    else:
        case_options = []
        # Select case to edit
        # case_options = [f"Row {row['row_index']} - {row['violation_type']} ({row['timestamp']})" for _, row in df.iterrows()]
        # selected_case_idx = st.selectbox("Select case to edit", range(len(case_options)), format_func=lambda x: case_options[x])
        for _, row in df.iterrows():
            creation_tz = row.get('creation_tz', 'Asia/Singapore')
            display_time = format_violation_time_with_creation_tz(row['timestamp'], creation_tz)
            case_options.append(f"Row {row['row_index']} - {row['violation_type']} ({display_time})")
        selected_case_idx = st.selectbox("Select case to edit", range(len(case_options)), format_func=lambda x: case_options[x])

        if selected_case_idx is not None:
            selected_case = df.iloc[selected_case_idx]

            with st.form("edit_case_form"):
                col1, col2 = st.columns(2)

                with col1:
                    timestamp_input = st.text_input("Timestamp", value=selected_case['timestamp'], help="Format: MM/DD/YY HH:MM AM/PM")
                    factory_area = st.text_input("Factory Area", value=selected_case['factory_area'])
                    inspection_section = st.text_input("Inspection Section", value=selected_case['inspection_section'])

                with col2:
                    violation_type = st.text_input("Violation Type", value=selected_case['violation_type'])
                    image_url = st.text_input("Image URL", value=selected_case['image_url'])
                    resolved = st.checkbox("Mark as Resolved", value=selected_case['resolved'])

                submitted = st.form_submit_button("Update Case")

                if submitted:
                    success = manager.update_violation(
                        selected_case['row_index'],
                        timestamp_input,
                        factory_area,
                        inspection_section,
                        violation_type,
                        image_url,
                        resolved
                    )
                    if success:
                        st.success("✅ Case updated successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update case.")

elif page == "🗑️ Delete Case":
    st.title("🗑️ Delete Violation Case")

    # Load data to select case to delete
    df = manager.load_data(selected_timezone)

    # Show current filter status
    if selected_timezone != "All Timezones":
        region = selected_timezone.split("/")[-1] if "/" in selected_timezone else selected_timezone
        st.info(f"🌍 Showing violations from: **{region}**")
    if df.empty:
        st.info("No cases available to delete.")
    else:
        st.warning("⚠️ Warning: This action cannot be undone!")

        # # Select case to delete
        # case_options = [f"Row {row['row_index']} - {row['violation_type']} ({row['timestamp']})" for _, row in df.iterrows()]
        # selected_case_idx = st.selectbox("Select case to delete", range(len(case_options)), format_func=lambda x: case_options[x])
        case_options = []
        for _, row in df.iterrows():
            try:
                creation_tz = row.get('creation_tz', 'Asia/Singapore')
                display_time = format_violation_time_with_creation_tz(row['timestamp'], creation_tz)
                case_options.append(f"Row {row['row_index']} - {row['violation_type']} ({display_time})")
            except:
                time_with_tz = f"{row['timestamp']} (SGT)"
                case_options.append(f"Row {row['row_index']} - {row['violation_type']} ({time_with_tz})")
        selected_case_idx = st.selectbox("Select case to delete", range(len(case_options)), format_func=lambda x: case_options[x])

        if selected_case_idx is not None:
            selected_case = df.iloc[selected_case_idx]
                # C  # Use the new format function for consistency
            creation_tz = selected_case.get('creation_tz', 'Asia/Singapore')
            display_time = format_violation_time_with_creation_tz(selected_case['timestamp'], creation_tz)


            # Show case details
            st.subheader("Case Details")
            col1, col2 = st.columns([1, 2])

            with col1:
                st.write(f"**Time:** {display_time}")
                st.write(f"**Area:** {selected_case['factory_area']}")
                st.write(f"**Section:** {selected_case['inspection_section']}")
                st.write(f"**Violation:** {selected_case['violation_type']}")
                st.write(f"**Status:** {'✅ Resolved' if selected_case['resolved'] else '❌ Unresolved'}")

            with col2:
                if selected_case['image_url']:
                    try:
                        st.image(selected_case['image_url'], caption="Evidence Image", width=300)
                    except:
                        st.error("Failed to load image")

            # Confirmation
            confirm = st.checkbox("I confirm that I want to delete this case")

            if st.button("🗑️ Delete Case", type="primary", disabled=not confirm):
                success = manager.delete_violation(selected_case['row_index'])
                if success:
                    st.success("✅ Case deleted successfully!")
                    st.rerun()
                else:
                    st.error("❌ Failed to delete case.")

elif page == "📊 Dashboard":
    st.title("📊 Violation Dashboard")

    # Load data
    # Load filtered data
    df = manager.load_data(selected_timezone)

     # Show current filter status
    if selected_timezone != "All Timezones":
        region = selected_timezone.split("/")[-1] if "/" in selected_timezone else selected_timezone
        st.info(f"🌍 Showing violations from: **{region}**")
    
    if df.empty:
        st.info("No data available for dashboard.")
    else:
        # Add timezone breakdown chart if showing all regions
        if selected_timezone == "All Timezones":
            st.subheader("🌍 Cases by Region") 
            timezone_counts = df['creation_tz'].value_counts()
            timezone_chart_data = pd.DataFrame({
                'Region': [tz.split("/")[-1] if "/" in tz else tz for tz in timezone_counts.index],
                'Count': timezone_counts.values
            })
            st.bar_chart(timezone_chart_data.set_index('Region'))

    # Show current filter status
    if selected_timezone != "All Timezones":
        region = selected_timezone.split("/")[-1] if "/" in selected_timezone else selected_timezone
        st.info(f"🌍 Showing violations from: **{region}**")

        if df.empty:
            st.info("No data available for dashboard.")
        else:
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)

            total_cases = len(df)
            resolved_cases = len(df[df['resolved'] == True])
            unresolved_cases = total_cases - resolved_cases
            resolution_rate = (resolved_cases / total_cases * 100) if total_cases > 0 else 0

            with col1:
                st.metric("Total Cases", total_cases)

            with col2:
                st.metric("Resolved Cases", resolved_cases)

            with col3:
                st.metric("Unresolved Cases", unresolved_cases)

            with col4:
                st.metric("Resolution Rate", f"{resolution_rate:.1f}%")

            # Charts
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Cases by Status")
                status_counts = df['resolved'].value_counts()
                status_labels = ['Unresolved', 'Resolved']
                status_data = [status_counts.get(False, 0), status_counts.get(True, 0)]

                chart_data = pd.DataFrame({
                    'Status': status_labels,
                    'Count': status_data
                })
                st.bar_chart(chart_data.set_index('Status'))

            with col2:
                st.subheader("Cases by Factory Area")
                area_counts = df['factory_area'].value_counts()
                st.bar_chart(area_counts)

            # Recent cases
            st.subheader("Recent Cases")
            recent_df = df.head(10).copy()

            converted_times = []
            # Convert timestamps
            for idx, row in recent_df.iterrows():
                creation_tz = row.get('creation_tz', 'Asia/Singapore')
                display_time = format_violation_time_with_creation_tz(row['timestamp'], creation_tz)
                converted_times.append(display_time)
                
            recent_df['Time'] = converted_times
            recent_df['Status'] = recent_df['resolved'].apply(lambda x: "✅ Resolved" if x else "❌ Unresolved")
            recent_df = recent_df[['Time', 'factory_area', 'violation_type', 'Status']]
            recent_df = recent_df.rename(columns={
                'factory_area': 'Factory Area',
                'violation_type': 'Violation Type'
            })

        # recent_df['Status'] = recent_df['resolved'].apply(lambda x: "✅ Resolved" if x else "❌ Unresolved")
        # recent_df = recent_df[['timestamp', 'factory_area', 'violation_type', 'Status']]
        # recent_df = recent_df.rename(columns={
        #     'timestamp': 'Time',
        #     'factory_area': 'Factory Area',
        #     'violation_type': 'Violation Type'
        # })
        st.dataframe(recent_df, use_container_width=True)

elif page == "📱 Manage Notifications":
    st.title("📱 WhatsApp Notification Management")

    # Create chat IDs table if it doesn't exist
    with st.expander("🔧 Setup Database Table", expanded=False):
        if st.button("Create Chat IDs Table"):
            try:
                manager.parser.create_chat_ids_table()
                st.success("✅ Chat IDs table created successfully!")
            except Exception as e:
                st.error(f"❌ Error creating table: {e}")

    st.subheader("📋 Active WhatsApp Numbers")

    # Load and display active chat IDs
    try:
        active_chat_ids = manager.parser.get_active_chat_ids()

        if active_chat_ids:
            st.success(f"📱 {len(active_chat_ids)} numbers are receiving violation alerts")

            # Display in a nice table format
            chat_data = []
            for chat_id in active_chat_ids:
                phone_number = chat_id
                chat_data.append({
                    "Phone Number": phone_number,
                    "Chat ID": chat_id,
                    "Status": "🟢 Active"
                })

            if chat_data:
                df_chats = pd.DataFrame(chat_data)
                st.dataframe(df_chats, use_container_width=True)

                # Bulk actions
                st.subheader("🛠️ Bulk Actions")
                col1, col2 = st.columns(2)

                with col1:
                    if st.button("📤 Export Chat IDs", help="Download list of active chat IDs"):
                        csv = df_chats.to_csv(index=False)
                        st.download_button(
                            label="💾 Download CSV",
                            data=csv,
                            file_name=f"whatsapp_chat_ids_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )

                with col2:
                    selected_chat_id = st.selectbox(
                        "Select number to remove:",
                        options=[""] + [f"{chat_id} ({chat_id})" for chat_id in active_chat_ids],
                        format_func=lambda x: "Choose a number..." if x == "" else x.split(" (")[0]
                    )

                    if selected_chat_id and st.button("🗑️ Remove Selected Number"):
                        # Extract chat_id from the selected option
                        actual_chat_id = selected_chat_id.split(" (")[1].replace(")", "")
                        removed = manager.parser.remove_chat_id(actual_chat_id)
                        if removed:
                            st.success(f"✅ Removed {actual_chat_id}")
                            st.rerun()
                        else:
                            st.error("❌ Failed to remove number")
        else:
            st.info("📭 No active WhatsApp numbers found. Add numbers using the sidebar form.")

    except Exception as e:
        st.error(f"❌ Error loading chat IDs: {e}")

    # Add multiple numbers at once
    st.subheader("➕ Bulk Add Numbers")
    with st.form("bulk_add_form"):
        bulk_numbers = st.text_area(
            "Enter phone numbers (one per line, with country code):",
            placeholder="6581899220\n6597607916\n65123456789",
            help="Enter each phone number on a new line, including country code (no + symbol)"
        )

        if st.form_submit_button("📱 Add All Numbers"):
            if bulk_numbers.strip():
                lines = [line.strip() for line in bulk_numbers.split('\n') if line.strip()]
                added_count = 0
                failed_count = 0

                for phone in lines:
                    if phone.isdigit() and 8 <= len(phone) <= 15:
                        chat_id = phone
                        added = manager.parser.add_chat_id(chat_id)
                        if added:
                            added_count += 1
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1

                if added_count > 0:
                    st.success(f"✅ Added {added_count} new numbers!")
                if failed_count > 0:
                    st.warning(f"⚠️ {failed_count} numbers were invalid or already exist")

                if added_count > 0:
                    st.rerun()

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**CCTV Violation Management System**")
st.sidebar.markdown("Built with Streamlit")

if __name__ == "__main__":
    pass
    # start_bot_once()
