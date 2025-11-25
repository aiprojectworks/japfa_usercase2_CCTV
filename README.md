# CCTV Violation Monitoring System

A real-time monitoring system that detects safety violations from CCTV footage analysis and sends instant WhatsApp alerts to subscribed users.

## 📋 Table of Contents
- [Overview](#overview)
- [Main Functions](#main-functions)
- [Architecture](#architecture)
- [Technologies Used](#technologies-used)
- [APIs Used](#apis-used)
- [Setup & Configuration](#setup--configuration)
- [Deployment](#deployment)

---

## 🎯 Overview

This system monitors a Snowflake database for new safety violations detected by CCTV systems. When a new violation is detected, it automatically sends WhatsApp notifications to subscribed users with violation details and a link to review the case via a Streamlit web interface.

### Key Features
- ✅ Real-time violation monitoring (checks every 5 seconds)
- ✅ ID-based tracking to prevent duplicate alerts
- ✅ Multi-user WhatsApp notification system
- ✅ Timezone-aware violation timestamps
- ✅ Case management via web interface integration
- ✅ Health check endpoint for monitoring
- ✅ Flexible configuration via AWS SSM or environment variables

---

## 🔧 Main Functions

### 1. **Violation Monitoring** (`ViolationMonitor` class)
**Purpose**: Core system that continuously monitors the database for new violations

**Key Methods**:

#### `monitor_sql_db()`
- **What**: Main monitoring loop that tracks violations using ID-based detection
- **How**:
  - Maintains a set of seen record IDs
  - Queries database every 5 seconds
  - Compares current records against seen IDs
  - Sends alerts only for truly new violations
- **Why ID-based**: Prevents false positives from database reordering and handles record deletions gracefully

#### `send_new_violation_alert(record, chat_id)`
- **What**: Sends WhatsApp notifications for new violations
- **How**:
  1. Tries to send via approved WhatsApp template (structured message)
  2. Falls back to image + caption if template fails
  3. Falls back to text-only if image fails
- **Features**: Includes case ID, timestamp with timezone, location, violation type, and direct link to case

#### `sync_chat_ids()`
- **What**: Synchronizes active WhatsApp subscribers from Snowflake
- **How**: Refreshes subscriber list every 12 cycles (1 minute)
- **Why**: Allows dynamic subscriber management without system restart

---

### 2. **Data Management** (`DataParser` class)

#### `parse()` → List[ViolationRecord]
- **What**: Fetches all violation records from Snowflake
- **Returns**: List of ViolationRecord objects with full violation details

#### `get_unresolved_records()` → List[ViolationRecord]
- **What**: Retrieves only unresolved violations
- **Use Case**: Dashboard display, status reporting

#### `get_records_by_timezone(timezone_filter)` → List[ViolationRecord]
- **What**: Filters violations by creation timezone
- **Why**: Supports multi-location deployments with different time zones

#### `update_resolved_status(row_index, resolved)`
- **What**: Marks violations as resolved in the database
- **How**: Updates via unique case ID

#### `add_random_violation_from_db()`
- **What**: Creates demo violations for testing
- **How**: Clones an existing violation with new ID and current timestamp

#### `add_chat_id(chat_id)` / `remove_chat_id(chat_id)` / `get_active_chat_ids()`
- **What**: Manages WhatsApp subscriber list in Snowflake
- **Why**: Persistent storage allows subscriber list to survive system restarts

---

### 3. **WhatsApp Messaging Functions**

#### `wa_send_violation_template()`
- **What**: Sends structured violation alert using approved WhatsApp template
- **Parameters**: case_id, timestamp, area, section, violation_type
- **Features**: Includes dynamic URL button for direct case access

#### `wa_send_image_url(to, image_url, caption)`
- **What**: Sends violation image with caption
- **Fallback**: Used when template message fails

#### `wa_send_text(to, text)`
- **What**: Sends plain text WhatsApp message
- **Fallback**: Last resort if image fails

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AWS EC2 Instance                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    main.py                           │  │
│  │                                                      │  │
│  │  ┌────────────────────────────────────────────┐    │  │
│  │  │    ViolationMonitor (Main Thread)          │    │  │
│  │  │  - monitor_sql_db() [daemon thread]       │    │  │
│  │  │  - Checks DB every 5 seconds              │    │  │
│  │  │  - ID-based duplicate prevention          │    │  │
│  │  └────────────────────────────────────────────┘    │  │
│  │                       │                             │  │
│  │                       ↓                             │  │
│  │  ┌────────────────────────────────────────────┐    │  │
│  │  │         Flask Web Server (Port 5001)       │    │  │
│  │  │  - Health check endpoint: /health         │    │  │
│  │  │  - Status endpoint: /                     │    │  │
│  │  └────────────────────────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────┘  │
│                       │                │                    │
└───────────────────────┼────────────────┼────────────────────┘
                        │                │
                        ↓                ↓
            ┌───────────────────┐  ┌─────────────────┐
            │  AWS SSM Param    │  │   Snowflake DB  │
            │  Store (Secrets)  │  │   - Violations  │
            │  - DB credentials │  │   - Chat IDs    │
            │  - WA credentials │  │   - Timestamps  │
            └───────────────────┘  └─────────────────┘
                        │
                        ↓
            ┌───────────────────────────┐
            │ WhatsApp Business API     │
            │ (Meta Graph API v20.0)    │
            │ - Template messages       │
            │ - Media messages          │
            │ - Text messages           │
            └───────────────────────────┘
                        │
                        ↓
            ┌───────────────────────────┐
            │   Subscribed Users        │
            │   (WhatsApp)              │
            └───────────────────────────┘
```

### Data Flow
1. **Initialization**: System loads existing violation IDs on startup
2. **Monitoring Loop**: Every 5 seconds, queries Snowflake for all violations
3. **Detection**: Compares current IDs against seen IDs
4. **Notification**: For each new violation, sends WhatsApp message to all subscribers
5. **Cleanup**: Removes deleted violations from tracking set
6. **Sync**: Every minute, refreshes subscriber list from database

---

## 🛠️ Technologies Used

### **Python 3.9+**
**Why**:
- Excellent libraries for database, API, and async operations
- Type hints for better code quality
- Strong AWS SDK support

### **boto3** (AWS SDK for Python)
**Why**:
- Secure credential management via AWS SSM Parameter Store
- No hardcoded secrets in code
- Automatic credential rotation support
- IAM role-based authentication

### **snowflake-connector-python**
**Why**:
- Official Snowflake connector
- Efficient query execution
- Connection pooling
- Parameterized queries (SQL injection prevention)

### **Flask**
**Why**:
- Lightweight web framework
- Simple health check endpoints for monitoring
- Easy integration with production servers (Gunicorn)

### **requests**
**Why**:
- Reliable HTTP client for WhatsApp API
- Session management
- Automatic retry logic
- Comprehensive error handling

### **zoneinfo** (Python 3.9+)
**Why**:
- IANA timezone database support
- Accurate timezone conversions
- Built-in (no external dependencies)

---

## 🔌 APIs Used

### 1. **WhatsApp Business API (Meta Graph API v20.0)**

**Endpoint**: `https://graph.facebook.com/v20.0/{phone_id}/messages`

**Authentication**: Bearer token

**Message Types Supported**:
- **Template Messages**: Pre-approved message templates with dynamic parameters
- **Media Messages**: Images with captions
- **Text Messages**: Plain text fallback

**Why WhatsApp**:
- ✅ Instant delivery (push notifications)
- ✅ High open rates (98%+)
- ✅ Global reach
- ✅ Read receipts
- ✅ Rich media support (images, buttons)

**Features Used**:
- Dynamic URL buttons (case-specific links)
- Template messages with variables
- Image attachments with captions

**Rate Limits**:
- 1000 messages/hour (free tier)
- Scalable to higher tiers

---

### 2. **Snowflake SQL API**

**Connection**: Via `snowflake-connector-python`

**Authentication**: Username/password (stored in AWS SSM)

**Tables**:
- `SWINE_NEW_ALERT`: Main violations table
  - Fields: ID, TIMESTAMP, FARM_LOCATION, INSPECTION_AREA, VIOLATION_TYPE, IMAGE_URL, REPLY, CREATION_TZ
- `WHATSAPP_CHAT_IDS`: Subscriber management
  - Fields: CHAT_ID, CREATED_AT, ACTIVE

**Queries Supported**:
- SELECT with filters (timezone, violation type, location)
- UPDATE (mark resolved)
- INSERT (demo violations)
- ORDER BY with timestamp parsing

**Why Snowflake**:
- ✅ Cloud-native data warehouse
- ✅ Scalable storage
- ✅ SQL compatibility
- ✅ Concurrent query support
- ✅ ACID compliance

---

### 3. **AWS Systems Manager (SSM) Parameter Store API**

**Client**: `boto3.client("ssm")`

**Operations**: `get_parameters()` with `WithDecryption=True`

**Parameters Stored**:
```
/japfa_usercase2_cctv/
  ├── JAPFA_user
  ├── JAPFA_password
  ├── JAPFA_account
  ├── JAPFA_database
  ├── JAPFA_schema
  ├── JAPFA_warehouse
  ├── JAPFA_role
  ├── WA_PHONE_ID
  ├── WA_TOKEN
  ├── WA_TEMPLATE_NAME (optional)
  └── WA_TEMPLATE_LANG (optional)
```

**Why SSM Parameter Store**:
- ✅ Secure secret storage (encrypted at rest)
- ✅ IAM-based access control
- ✅ Audit logging via CloudTrail
- ✅ Version history
- ✅ No secrets in code or environment variables
- ✅ Batch retrieval (up to 10 parameters per call)

**Fallback Mechanism**:
- Tries SSM first
- Falls back to environment variables if SSM unavailable
- Validates all required parameters before startup

---

## ⚙️ Setup & Configuration

### Prerequisites
- Python 3.9+
- AWS account with IAM role configured
- Snowflake account with database access
- WhatsApp Business API account
- Approved WhatsApp message template

### Installation

```bash
# Clone repository
git clone <repository-url>
cd japfa_usercase2_CCTV

# Install dependencies
pip install -r requirements.txt
```

### Required Dependencies
```
boto3>=1.28.0
snowflake-connector-python>=3.0.0
Flask>=2.3.0
requests>=2.31.0
python-dotenv>=1.0.0
```

### AWS SSM Configuration

Set up parameters in AWS Systems Manager:

```bash
# Snowflake credentials
aws ssm put-parameter --name "/japfa_usercase2_cctv/JAPFA_user" --value "your_user" --type "SecureString"
aws ssm put-parameter --name "/japfa_usercase2_cctv/JAPFA_password" --value "your_password" --type "SecureString"
aws ssm put-parameter --name "/japfa_usercase2_cctv/JAPFA_account" --value "your_account" --type "String"
aws ssm put-parameter --name "/japfa_usercase2_cctv/JAPFA_database" --value "your_db" --type "String"
aws ssm put-parameter --name "/japfa_usercase2_cctv/JAPFA_schema" --value "your_schema" --type "String"
aws ssm put-parameter --name "/japfa_usercase2_cctv/JAPFA_warehouse" --value "your_warehouse" --type "String"
aws ssm put-parameter --name "/japfa_usercase2_cctv/JAPFA_role" --value "your_role" --type "String"

# WhatsApp credentials
aws ssm put-parameter --name "/japfa_usercase2_cctv/WA_PHONE_ID" --value "your_phone_id" --type "SecureString"
aws ssm put-parameter --name "/japfa_usercase2_cctv/WA_TOKEN" --value "your_token" --type "SecureString"

# Optional: WhatsApp template settings
aws ssm put-parameter --name "/japfa_usercase2_cctv/WA_TEMPLATE_NAME" --value "alert_template" --type "String"
aws ssm put-parameter --name "/japfa_usercase2_cctv/WA_TEMPLATE_LANG" --value "en" --type "String"
```

### IAM Role Policy

Attach this policy to your EC2 instance role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameters",
        "ssm:GetParameter"
      ],
      "Resource": "arn:aws:ssm:ap-southeast-1:*:parameter/japfa_usercase2_cctv/*"
    }
  ]
}
```

### Local Development Setup

For local development without AWS:

1. Create a `.env` file:
```env
JAPFA_user=your_user
JAPFA_password=your_password
JAPFA_account=your_account
JAPFA_database=your_database
JAPFA_schema=your_schema
JAPFA_warehouse=your_warehouse
JAPFA_role=your_role

WA_PHONE_ID=your_phone_id
WA_TOKEN=your_token
WA_TEMPLATE_NAME=alert_template
WA_TEMPLATE_LANG=en
```

2. The system will automatically fall back to environment variables if SSM is unavailable

---

## 🚀 Deployment

### Running the Application

```bash
# Development
python main.py

# Production (with Gunicorn)
gunicorn -w 4 -b 0.0.0.0:5001 main:create_web_app()
```

### Systemd Service (Linux)

Create `/etc/systemd/system/cctv-monitor.service`:

```ini
[Unit]
Description=CCTV Violation Monitoring System
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/japfa_usercase2_CCTV
ExecStart=/usr/bin/python3 /home/ubuntu/japfa_usercase2_CCTV/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable cctv-monitor
sudo systemctl start cctv-monitor
sudo systemctl status cctv-monitor
```

### Health Checks

Monitor system health:
```bash
# Basic health check
curl http://localhost:5001/health

# Expected response
{"status": "healthy", "service": "cctv-violation-monitor"}
```

### Monitoring Endpoints

- **Health Check**: `GET /health` - Returns system health status
- **Status Page**: `GET /` - Returns basic system info

---

## 📊 Database Schema

### SWINE_NEW_ALERT Table
```sql
CREATE TABLE SWINE_NEW_ALERT (
    ID VARCHAR(255) PRIMARY KEY,
    TIMESTAMP VARCHAR(50),
    FARM_LOCATION VARCHAR(255),
    INSPECTION_AREA VARCHAR(255),
    VIOLATION_TYPE VARCHAR(255),
    IMAGE_URL VARCHAR(1000),
    REPLY VARCHAR(50),
    CREATION_TZ VARCHAR(50)
);
```

### WHATSAPP_CHAT_IDS Table
```sql
CREATE TABLE WHATSAPP_CHAT_IDS (
    CHAT_ID VARCHAR(255) PRIMARY KEY,
    CREATED_AT TIMESTAMP,
    ACTIVE BOOLEAN DEFAULT TRUE
);
```

---

## 🔒 Security Features

1. **No Hardcoded Secrets**: All credentials stored in AWS SSM
2. **IAM Role Authentication**: Uses EC2 instance role
3. **Encrypted Parameters**: SSM SecureString for sensitive data
4. **SQL Injection Prevention**: Parameterized queries
5. **Rate Limiting**: Built-in WhatsApp API rate limiting
6. **Error Handling**: Comprehensive try-catch blocks
7. **Audit Trail**: All SSM access logged in CloudTrail

---

## 🐛 Troubleshooting

### Common Issues

**1. SSM Parameter Not Found**
```
RuntimeError: Missing SSM parameters: WA_PHONE_ID
```
**Solution**: Check parameter exists and IAM role has permission

**2. Snowflake Connection Failed**
```
Error: Failed to connect to Snowflake
```
**Solution**: Verify credentials, network access, and warehouse is running

**3. WhatsApp Send Failed**
```
WA send failed [403]: Permission denied
```
**Solution**: Check token validity and phone number verification

---

## 📝 Logging

Logs include:
- System initialization
- Violation detection events
- WhatsApp notification status
- Error traces
- Subscriber list changes

Log format:
```
2025-01-19 10:30:45 - __main__ - INFO - Detected 1 truly NEW violation(s)
2025-01-19 10:30:46 - __main__ - INFO - Sending alert to 6596370843 for case 123
```

---

## 🎯 Future Enhancements

- [ ] Web dashboard for violation management
- [ ] ML-based violation classification
- [ ] Multi-language WhatsApp templates
- [ ] Analytics and reporting
- [ ] Mobile app integration
- [ ] Voice alert support
- [ ] Automated resolution workflows

---
