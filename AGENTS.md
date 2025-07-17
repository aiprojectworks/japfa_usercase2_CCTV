# AGENTS.md - Development Guidelines

## Commands
- **Run Telegram Bot**: `python main.py`
- **Run Streamlit App**: `streamlit run streamlit_app.py`
- **Run Both**: `bash run.sh` (runs Streamlit & Telegram bot concurrently)
- **Test Syntax**: `python -m py_compile main.py data.py streamlit_app.py`
- **Run Single Test**: `python -m pytest path/to/test.py::test_function` (if pytest installed)

## Code Style
- **Language**: Python 3.x with async/await for Telegram bot
- **Imports**: Standard library first, third-party second, local last (blank line separated)
- **Types**: Use type hints (`from typing import List, Optional`) and `@dataclass` 
- **Naming**: snake_case (vars/functions), PascalCase (classes), UPPER_CASE (constants)
- **Strings**: f-strings preferred, double quotes for consistency
- **Error Handling**: Explicit try/except blocks, check `None` values explicitly
- **Environment**: Load from `../.env` using `python-dotenv`
- **CSV Operations**: Use atomic writes with temporary files for data integrity

## File Structure  
- `main.py`: Telegram bot with real-time CSV monitoring
- `streamlit_app.py`: Web interface for CRUD operations  
- `data.py`: ViolationRecord dataclass and CSV parsing logic
- `data/data.csv`: CSV with columns: timestamp, factory_area, inspection_section, violation_type, image_url, resolved, confirmed
- `run.sh`: Bash script to run both applications

## Key Patterns
- `ViolationRecord`: Dataclass with proper type hints and `from_csv_row` classmethod
- CSV format: "MM/DD/YY HH:MM AM/PM" timestamp format required
- Atomic CSV operations: Always use temporary files then move to preserve integrity
- Async handlers: All Telegram bot handlers must be async functions

# CCTV Violation Management System - Streamlit App

## Overview
A comprehensive web application for managing CCTV violation cases with full CRUD (Create, Read, Update, Delete) operations.

## Features

### 📋 View Cases
- Display all violation cases in a filterable table
- Filter by status (resolved/unresolved), factory area, and violation type
- View case details with evidence images
- Search and sort functionality

### ➕ Add New Case
- Create new violation records
- Form validation for timestamp format
- Optional image URL support
- Mark cases as resolved during creation

### ✏️ Edit Case
- Select existing cases to modify
- Update all case fields
- Real-time form validation
- Preserve data integrity

### 🗑️ Delete Case
- Safe case deletion with confirmation
- Preview case details before deletion
- Permanent removal from CSV file

### 📊 Dashboard
- Key metrics overview (total, resolved, unresolved cases)
- Resolution rate calculation
- Visual charts for case distribution
- Recent cases summary

## Installation

1. Install required packages:
```bash
pip install -r requirements_streamlit.txt
```

2. Run the application:
```bash
streamlit run streamlit_app.py
```

## Usage

The application will open in your browser at `http://localhost:8501`

Navigate through different pages using the sidebar:
- **View Cases**: Browse and filter existing violations
- **Add New Case**: Create new violation records
- **Edit Case**: Modify existing case details
- **Delete Case**: Remove cases with confirmation
- **Dashboard**: View analytics and statistics

## Data Structure

The application works with CSV files containing:
- **Timestamp**: MM/DD/YY HH:MM AM/PM format
- **Factory Area**: Location identifier
- **Inspection Section**: Specific area within factory
- **Violation Type**: Type of violation detected
- **Image URL**: Evidence image link
- **Resolved**: Boolean status

## Integration

The Streamlit app uses the same `data.py` module as the Telegram bot, ensuring data consistency across both interfaces.

## Features

- **Real-time Updates**: Changes reflect immediately
- **Data Validation**: Ensures proper timestamp formatting
- **Error Handling**: Graceful handling of invalid data
- **Responsive Design**: Works on desktop and mobile
- **Image Display**: Shows evidence images when available
