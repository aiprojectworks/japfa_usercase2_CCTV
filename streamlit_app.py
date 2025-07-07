import streamlit as st
import pandas as pd
import csv
from datetime import datetime
from data import DataParser, ViolationRecord
import tempfile
import shutil
import os

# Configure Streamlit page
st.set_page_config(
    page_title="CCTV Violation Management System",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

class ViolationManager:
    """Enhanced DataParser with additional CRUD operations for Streamlit"""
    
    def __init__(self):
        self.parser = DataParser()
        
    def load_data(self):
        """Load violation data and return as DataFrame"""
        records = self.parser.parse()
        if not records:
            return pd.DataFrame(columns=['timestamp', 'factory_area', 'inspection_section', 'violation_type', 'image_url', 'resolved', 'confirmed', 'row_index'])
        
        data = []
        for record in records:
            data.append({
                'timestamp': record.timestamp.strftime("%m/%d/%y %I:%M %p"),
                'factory_area': record.factory_area,
                'inspection_section': record.inspection_section,
                'violation_type': record.violation_type,
                'image_url': record.image_url,
                'resolved': record.resolved,
                'confirmed': record.confirmed,
                'row_index': record.row_index
            })
        
        return pd.DataFrame(data)
    
    def add_violation(self, timestamp_str, factory_area, inspection_section, violation_type, image_url, resolved=False, confirmed=False):
        """Add a new violation record"""
        try:
            # Validate timestamp format
            datetime.strptime(timestamp_str, "%m/%d/%y %I:%M %p")
            
            # Prepare CSV row
            new_row = [
                timestamp_str,
                factory_area,
                inspection_section,
                violation_type,
                image_url,
                str(resolved).lower(),
                str(confirmed).lower()
            ]
            
            # Append to CSV file
            with open(self.parser.file_path, 'a', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(new_row)
            
            return True
        except Exception as e:
            st.error(f"Error adding violation: {e}")
            return False
    
    def delete_violation(self, row_index):
        """Delete a violation record by row index"""
        try:
            # Read all lines
            with open(self.parser.file_path, 'r', encoding='utf-8') as file:
                lines = list(csv.reader(file))
            
            # Remove the specific row (row_index is 1-based, list is 0-based)
            if 0 < row_index <= len(lines):
                lines.pop(row_index - 1)
                
                # Write back to file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', newline='') as temp_file:
                    writer = csv.writer(temp_file)
                    writer.writerows(lines)
                    temp_file_path = temp_file.name
                
                shutil.move(temp_file_path, self.parser.file_path)
                return True
        except Exception as e:
            st.error(f"Error deleting violation: {e}")
            return False
        
        return False
    
    def update_violation(self, row_index, timestamp_str, factory_area, inspection_section, violation_type, image_url, resolved, confirmed):
        """Update an existing violation record"""
        try:
            # Validate timestamp format
            datetime.strptime(timestamp_str, "%m/%d/%y %I:%M %p")
            
            # Read all lines
            with open(self.parser.file_path, 'r', encoding='utf-8') as file:
                lines = list(csv.reader(file))
            
            # Update the specific row
            if 0 < row_index <= len(lines):
                lines[row_index - 1] = [
                    timestamp_str,
                    factory_area,
                    inspection_section,
                    violation_type,
                    image_url,
                    str(resolved).lower(),
                    str(confirmed).lower()
                ]
                
                # Write back to file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', newline='') as temp_file:
                    writer = csv.writer(temp_file)
                    writer.writerows(lines)
                    temp_file_path = temp_file.name
                
                shutil.move(temp_file_path, self.parser.file_path)
                return True
        except Exception as e:
            st.error(f"Error updating violation: {e}")
            return False
        
        return False

# Initialize the violation manager
@st.cache_resource
def get_violation_manager():
    return ViolationManager()

manager = get_violation_manager()

# Handle URL parameters for direct case linking
query_params = st.query_params
case_id = query_params.get("case_id", None)

# Sidebar navigation
st.sidebar.title("🚨 CCTV Violation Management")

# If case_id is provided in URL, automatically go to Confirm Cases page
if case_id:
    default_page = "🔍 Confirm Cases"
    st.sidebar.info(f"📍 Viewing Case #{case_id}")
else:
    default_page = "🔍 Confirm Cases"

page = st.sidebar.selectbox(
    "Select Page",
    ["🔍 Confirm Cases", "📋 View Cases", "➕ Add New Case", "✏️ Edit Case", "🗑️ Delete Case", "📊 Dashboard"],
    index=0 if not case_id else 0
)

# Main content area
if page == "🔍 Confirm Cases":
    st.title("🔍 Confirm Violation Cases")
    
    # Load data
    df = manager.load_data()
    
    if df.empty:
        st.info("No violation cases found.")
    else:
        # Filter for unconfirmed cases
        unconfirmed_df = df[df['confirmed'] == False]
        
        # If case_id is provided, filter to show only that specific case
        if case_id:
            try:
                case_id_int = int(case_id)
                specific_case_df = df[df['row_index'] == case_id_int]
                if not specific_case_df.empty:
                    unconfirmed_df = specific_case_df
                    st.success(f"🎯 Showing Case #{case_id} from Telegram notification")
                else:
                    st.warning(f"⚠️ Case #{case_id} not found. Showing all unconfirmed cases.")
            except ValueError:
                st.error("❌ Invalid case ID format")
        
        if unconfirmed_df.empty and not case_id:
            st.success("✅ All violations have been confirmed!")
            st.balloons()
        elif unconfirmed_df.empty and case_id:
            st.info(f"ℹ️ Case #{case_id} has already been confirmed or resolved.")
            # Show all unconfirmed cases as fallback
            unconfirmed_df = df[df['confirmed'] == False]
            if not unconfirmed_df.empty:
                st.write("**Other unconfirmed cases:**")
        else:
            if not case_id:
                st.warning(f"⚠️ {len(unconfirmed_df)} violation(s) require confirmation")
            
            # Display unconfirmed cases
            for idx, case in unconfirmed_df.iterrows():
                # Highlight the specific case if it matches the URL parameter
                is_highlighted = case_id and str(case['row_index']) == case_id
                
                with st.expander(f"{'🔥' if is_highlighted else '🚨'} {case['violation_type']} - {case['timestamp']}", expanded=is_highlighted or not case_id):
                    if is_highlighted:
                        st.success("🎯 This is the case from your Telegram notification!")
                    
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        st.write("**Case Details:**")
                        st.write(f"**Case ID:** {case['row_index']}")
                        st.write(f"**Time:** {case['timestamp']}")
                        st.write(f"**Area:** {case['factory_area']}")
                        st.write(f"**Section:** {case['inspection_section']}")
                        st.write(f"**Violation:** {case['violation_type']}")
                        st.write(f"**Status:** {'✅ Resolved' if case['resolved'] else '❌ Unresolved'}")
                    
                    with col2:
                        if case['image_url']:
                            try:
                                st.write("**Evidence Image:**")
                                st.image(case['image_url'], caption="Violation Evidence", width=300)
                            except:
                                st.error("Failed to load image")
                        else:
                            st.info("No image available")
                    
                    with col3:
                        st.write("**Actions:**")
                        
                        # Confirm case button
                        if st.button(f"✅ Confirm Case", key=f"confirm_{case['row_index']}"):
                            success = manager.parser.update_confirmed_status(case['row_index'], True)
                            if success:
                                st.success("✅ Case confirmed!")
                                # Clear URL parameter after confirmation
                                if case_id:
                                    st.query_params.clear()
                                st.rerun()
                            else:
                                st.error("❌ Failed to confirm case")
                        
                        # Reject case button
                        if st.button(f"❌ Reject Case", key=f"reject_{case['row_index']}"):
                            success = manager.delete_violation(case['row_index'])
                            if success:
                                st.success("✅ Case rejected and deleted!")
                                # Clear URL parameter after rejection
                                if case_id:
                                    st.query_params.clear()
                                st.rerun()
                            else:
                                st.error("❌ Failed to reject case")
                        
                        # Mark as resolved if not already
                        if not case['resolved']:
                            if st.button(f"🔧 Mark Resolved", key=f"resolve_{case['row_index']}"):
                                success = manager.parser.update_resolved_status(case['row_index'], True)
                                if success:
                                    st.success("✅ Case marked as resolved!")
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to mark as resolved")

elif page == "📋 View Cases":
    st.title("📋 Violation Cases")
    
    # Load data
    df = manager.load_data()
    
    if df.empty:
        st.info("No violation cases found.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox("Filter by Status", ["All", "Resolved", "Unresolved"])
        
        with col2:
            confirmation_filter = st.selectbox("Filter by Confirmation", ["All", "Confirmed", "Unconfirmed"])
        
        with col3:
            area_filter = st.selectbox("Filter by Area", ["All"] + df['factory_area'].unique().tolist())
        
        # Apply filters
        filtered_df = df.copy()
        
        if status_filter == "Resolved":
            filtered_df = filtered_df[filtered_df['resolved'] == True]
        elif status_filter == "Unresolved":
            filtered_df = filtered_df[filtered_df['resolved'] == False]
        
        if confirmation_filter == "Confirmed":
            filtered_df = filtered_df[filtered_df['confirmed'] == True]
        elif confirmation_filter == "Unconfirmed":
            filtered_df = filtered_df[filtered_df['confirmed'] == False]
        
        if area_filter != "All":
            filtered_df = filtered_df[filtered_df['factory_area'] == area_filter]
        
        # Display data
        st.write(f"Showing {len(filtered_df)} of {len(df)} cases")
        
        # Format display
        display_df = filtered_df.copy()
        display_df['Status'] = display_df['resolved'].apply(lambda x: "✅ Resolved" if x else "❌ Unresolved")
        display_df['Confirmation'] = display_df['confirmed'].apply(lambda x: "✅ Confirmed" if x else "⚠️ Pending")
        display_df = display_df.drop(['resolved', 'confirmed', 'row_index'], axis=1)
        display_df = display_df.rename(columns={
            'timestamp': 'Time',
            'factory_area': 'Factory Area',
            'inspection_section': 'Section',
            'violation_type': 'Violation Type',
            'image_url': 'Image URL'
        })
        
        st.dataframe(display_df, use_container_width=True)
        
        # Show images for selected rows
        if not filtered_df.empty:
            st.subheader("Case Details")
            case_index = st.selectbox("Select case to view details", range(len(filtered_df)), format_func=lambda x: f"Row {filtered_df.iloc[x]['row_index']} - {filtered_df.iloc[x]['violation_type']}")
            
            if case_index is not None:
                selected_case = filtered_df.iloc[case_index]
                
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.write("**Case Details:**")
                    st.write(f"**Time:** {selected_case['timestamp']}")
                    st.write(f"**Area:** {selected_case['factory_area']}")
                    st.write(f"**Section:** {selected_case['inspection_section']}")
                    st.write(f"**Violation:** {selected_case['violation_type']}")
                st.write(f"**Status:** {'✅ Resolved' if selected_case['resolved'] else '❌ Unresolved'}")
                st.write(f"**Confirmation:** {'✅ Confirmed' if selected_case['confirmed'] else '⚠️ Pending'}")
                
                with col2:
                    if selected_case['image_url']:
                        try:
                            st.write("**Evidence Image:**")
                            st.image(selected_case['image_url'], caption="Violation Evidence", width=400)
                        except:
                            st.error("Failed to load image")
                    else:
                        st.info("No image available for this case")

elif page == "➕ Add New Case":
    st.title("➕ Add New Violation Case")
    
    with st.form("add_case_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            timestamp_input = st.text_input("Timestamp", value=datetime.now().strftime("%m/%d/%y %I:%M %p"), help="Format: MM/DD/YY HH:MM AM/PM")
            factory_area = st.text_input("Factory Area", placeholder="e.g., KP1, Production Line A")
            inspection_section = st.text_input("Inspection Section", placeholder="e.g., Assembly Station 3")
        
        with col2:
            violation_type = st.text_input("Violation Type", placeholder="e.g., 员工未佩戴安全帽")
            image_url = st.text_input("Image URL", placeholder="https://example.com/image.jpg")
            resolved = st.checkbox("Mark as Resolved")
            confirmed = st.checkbox("Mark as Confirmed")
        
        submitted = st.form_submit_button("Add Case")
        
        if submitted:
            if timestamp_input and factory_area and inspection_section and violation_type:
                success = manager.add_violation(timestamp_input, factory_area, inspection_section, violation_type, image_url, resolved, confirmed)
                if success:
                    st.success("✅ Case added successfully!")
                    st.balloons()
                else:
                    st.error("❌ Failed to add case. Please check the format.")
            else:
                st.error("Please fill in all required fields.")

elif page == "✏️ Edit Case":
    st.title("✏️ Edit Violation Case")
    
    # Load data to select case to edit
    df = manager.load_data()
    
    if df.empty:
        st.info("No cases available to edit.")
    else:
        # Select case to edit
        case_options = [f"Row {row['row_index']} - {row['violation_type']} ({row['timestamp']})" for _, row in df.iterrows()]
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
                    confirmed = st.checkbox("Mark as Confirmed", value=selected_case['confirmed'])
                
                submitted = st.form_submit_button("Update Case")
                
                if submitted:
                    success = manager.update_violation(
                        selected_case['row_index'],
                        timestamp_input,
                        factory_area,
                        inspection_section,
                        violation_type,
                        image_url,
                        resolved,
                        confirmed
                    )
                    if success:
                        st.success("✅ Case updated successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update case.")

elif page == "🗑️ Delete Case":
    st.title("🗑️ Delete Violation Case")
    
    # Load data to select case to delete
    df = manager.load_data()
    
    if df.empty:
        st.info("No cases available to delete.")
    else:
        st.warning("⚠️ Warning: This action cannot be undone!")
        
        # Select case to delete
        case_options = [f"Row {row['row_index']} - {row['violation_type']} ({row['timestamp']})" for _, row in df.iterrows()]
        selected_case_idx = st.selectbox("Select case to delete", range(len(case_options)), format_func=lambda x: case_options[x])
        
        if selected_case_idx is not None:
            selected_case = df.iloc[selected_case_idx]
            
            # Show case details
            st.subheader("Case Details")
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.write(f"**Time:** {selected_case['timestamp']}")
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
    df = manager.load_data()
    
    if df.empty:
        st.info("No data available for dashboard.")
    else:
        # Key metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        total_cases = len(df)
        resolved_cases = len(df[df['resolved'] == True])
        confirmed_cases = len(df[df['confirmed'] == True])
        unresolved_cases = total_cases - resolved_cases
        unconfirmed_cases = total_cases - confirmed_cases
        resolution_rate = (resolved_cases / total_cases * 100) if total_cases > 0 else 0
        
        with col1:
            st.metric("Total Cases", total_cases)
        
        with col2:
            st.metric("Resolved Cases", resolved_cases)
        
        with col3:
            st.metric("Unresolved Cases", unresolved_cases)
        
        with col4:
            st.metric("Confirmed Cases", confirmed_cases)
        
        with col5:
            st.metric("Unconfirmed Cases", unconfirmed_cases)
        
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
            st.subheader("Confirmation Status")
            confirmation_counts = df['confirmed'].value_counts()
            confirmation_labels = ['Unconfirmed', 'Confirmed']
            confirmation_data = [confirmation_counts.get(False, 0), confirmation_counts.get(True, 0)]
            
            chart_data = pd.DataFrame({
                'Status': confirmation_labels,
                'Count': confirmation_data
            })
            st.bar_chart(chart_data.set_index('Status'))
        
        # Recent cases
        st.subheader("Recent Cases")
        recent_df = df.head(10).copy()
        recent_df['Status'] = recent_df['resolved'].apply(lambda x: "✅ Resolved" if x else "❌ Unresolved")
        recent_df['Confirmation'] = recent_df['confirmed'].apply(lambda x: "✅ Confirmed" if x else "⚠️ Pending")
        recent_df = recent_df[['timestamp', 'factory_area', 'violation_type', 'Status', 'Confirmation']]
        recent_df = recent_df.rename(columns={
            'timestamp': 'Time',
            'factory_area': 'Factory Area',
            'violation_type': 'Violation Type'
        })
        st.dataframe(recent_df, use_container_width=True)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**CCTV Violation Management System**")
st.sidebar.markdown("Built with Streamlit")

if __name__ == "__main__":
    pass