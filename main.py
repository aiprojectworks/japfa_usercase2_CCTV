from data import DataParser
import logging
import os

from dotenv import load_dotenv
import threading
import time
from typing import Any, Optional
from flask import Flask

# WhatsApp via pywa (Cloud API)
try:
    from pywa import WhatsApp  # type: ignore
except Exception:  # pywa might not be installed in all environments
    WhatsApp = None  # type: ignore

load_dotenv()

WA_PHONE_ID = os.getenv("WA_PHONE_ID") or os.getenv("WHATSAPP_PHONE_ID") or "775233089000345"
WA_TOKEN = os.getenv("WA_TOKEN") or os.getenv("WHATSAPP_TOKEN") or "EAAKlsRsZCkqgBPPP7iU5NebzJIJGydLAoBEUH3e0CY27sZB2k1atuMC9eIeVMDbj7fDKXF4NTfkA6DcWGZAasDkfsRzF5LkkRFkuU2CKRnSeR4v4Dfi9KkGnI5PYDpwifbpO9wGv1YuinGyGvVMdbVMHcpGAisncsZCnXkZBHOqLZCI77jtVKZCZATsPQ1CZAtH9E2wZDZD"

STREAMLIT_URL = "https://hrtowii-fyp-proj-japfa-cctvstreamlit-app-nt7gbx.streamlit.app/"

wa = None
if WhatsApp is not None and WA_PHONE_ID and WA_TOKEN:
    wa = WhatsApp(
        phone_id=WA_PHONE_ID,
        token=WA_TOKEN,
    )

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class ViolationMonitor:
    """Global monitoring system for CCTV violations using WhatsApp"""

    # Thread handle (set in __init__)
    monitoring_thread: Optional[threading.Thread]

    def __init__(self):
        self.parser = DataParser()
        self.last_record_count = 0
        self.monitoring_active = False
        self.monitoring_thread = None
        self.active_chat_ids = set()
        # Load chat IDs from Snowflake on initialization
        self._load_chat_ids_from_snowflake()
        # pywa WhatsApp client instance
        self.bot = None
        self.sync_cycle_counter = 0  # Counter for periodic chat ID sync

    def initialize(self, bot_instance):
        """Initialize the monitor with the WhatsApp bot"""
        self.bot = bot_instance
        records = self.parser.parse()
        self.last_record_count = len(records)
        logger.info(
            f"Monitor initialized with {self.last_record_count} existing records"
        )

    def _load_chat_ids_from_snowflake(self):
        """Load active chat IDs from Snowflake database"""
        try:
            chat_ids = self.parser.get_active_chat_ids()
            self.active_chat_ids = set(chat_ids)
            logger.info(f"Loaded {len(chat_ids)} active chat IDs from Snowflake")
        except Exception as e:
            logger.error(f"Failed to load chat IDs from Snowflake: {e}")
            # Fallback to default chat IDs if Snowflake fails
            self.active_chat_ids = {"6581899220", "6597607916"}
            logger.info("Using fallback default chat IDs")

    def sync_chat_ids(self):
        """Synchronize chat IDs with Snowflake database"""
        try:
            fresh_chat_ids = set(self.parser.get_active_chat_ids())
            if fresh_chat_ids != self.active_chat_ids:
                old_count = len(self.active_chat_ids)
                self.active_chat_ids = fresh_chat_ids
                new_count = len(self.active_chat_ids)
                logger.info(f"Synchronized chat IDs: {old_count} -> {new_count} active subscribers")
        except Exception as e:
            logger.error(f"Failed to sync chat IDs from Snowflake: {e}")

    def send_new_violation_alert(self, record, chat_id):
        """Send alert for new violation to specific WhatsApp chat"""
        print(record)
        case_url = f"{STREAMLIT_URL}/?case_id={record.row_index}"

        violation_text = (
            f"🚨 NEW VIOLATION DETECTED\n\n"
            f"🆔 Case ID: {record.row_index}\n"
            f"⏰ Time: {record.timestamp}\n"
            f"🏭 Area: {record.factory_area}\n"
            f"🔍 Section: {record.inspection_section}\n"
            f"⚠️ Violation: {record.violation_type}\n\n"
            f"🔗 Review Case: {case_url}\n\n"
            # f"📋 Action Required: Reply with commands below:\n"
            # f"• Type 'resolve {record.row_index}' to mark as resolved\n"
            # f"• Type 'status' to view current statistics"
        )

        if self.bot is None:
            logger.error("WhatsApp client is not initialized")
            return

        # Ensure numeric phone number (E.164 without '+')
        to_number = str(chat_id)

        try:
            # Try sending image by URL with caption if available, otherwise send text message
            if hasattr(record, "image_url") and record.image_url:
                try:
                    # pywa supports send_image with a link
                    self.bot.send_image(
                        to=to_number,
                        image=record.image_url,
                        caption=violation_text,
                    )
                except AttributeError:
                    # Fallback if send_image is unavailable in installed pywa version
                    fallback_text = f"{violation_text}\n🖼️ Image: {record.image_url}"
                    self.bot.send_message(to=to_number, text=fallback_text)
            else:
                self.bot.send_message(to=to_number, text=violation_text)
        except Exception as e:
            print(f"Failed to send violation alert: {e}")
            # Fallback: try to send just the text message
            try:
                self.bot.send_message(to=to_number, text=violation_text)
            except Exception as fallback_error:
                print(f"Failed to send fallback message: {fallback_error}")
    def monitor_sql_db(self):
        while self.monitoring_active:
            try:
                # Periodic chat ID sync (every 12 cycles = 1 minute)
                self.sync_cycle_counter += 1
                if self.sync_cycle_counter >= 12:
                    self.sync_chat_ids()
                    self.sync_cycle_counter = 0

                temp_parser = DataParser()
                current_records = temp_parser.parse()
                current_count = len(current_records)

                logger.info(
                    f"Monitoring: Found {current_count} total records, last count was {self.last_record_count}"
                )

                if current_count > self.last_record_count:
                    new_records = current_records[self.last_record_count :]
                    logger.info(f"Detected {len(new_records)} new violation(s)")

                    # Send notifications to all active chat IDs
                    for record in new_records:
                        for chat_id in self.active_chat_ids:
                            try:
                                print("meow")
                                self.send_new_violation_alert(record, chat_id)
                            except Exception as e:
                                logger.error(
                                    f"Failed to send notification to chat {chat_id}: {e}"
                                )

                    self.last_record_count = current_count

                    self.parser.records = current_records

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error monitoring sql db: {e}")
                time.sleep(5)

    def start_monitoring(self, chat_id):
        """Register a chat for monitoring notifications. Only main() starts the monitoring thread."""
        # Add to Snowflake and local set
        if chat_id != "system":
            success = self.parser.add_chat_id(chat_id)
            if success:
                logger.info(f"Added chat ID {chat_id} to Snowflake")
            else:
                logger.info(f"Chat ID {chat_id} already exists in Snowflake")

        self.active_chat_ids.add(chat_id)

        if not self.monitoring_active:
            # Initialize record count with fresh parsing
            temp_parser = DataParser()
            records = temp_parser.parse()
            self.last_record_count = len(records)

            # Update global parser
            self.parser.records = records

            # Do NOT start a new thread here; only main() does that.
            self.monitoring_active = True
            logger.info("Global monitoring system marked active (thread started in main)")
            # Only send notification if chat_id is not 'system'
            if self.bot is not None and chat_id != "system":
                try:
                    to_number = str(chat_id)
                    self.bot.send_message(
                        to=to_number,
                        text="Now monitoring sql db for new violations."
                    )
                except Exception as e:
                    logger.error(f"Failed to send monitoring started message: {e}")
            return True
        else:
            logger.info(f"Chat {chat_id} added to existing monitoring system")
            return False

    def stop_monitoring(self, chat_id):
        """Stop monitoring for a specific chat, or globally if no more chats"""
        # Remove from Snowflake and local set
        if chat_id != "system":
            success = self.parser.remove_chat_id(chat_id)
            if success:
                logger.info(f"Removed chat ID {chat_id} from Snowflake")

        self.active_chat_ids.discard(chat_id)

        # If no more active chats, stop monitoring completely
        if not self.active_chat_ids:
            self.monitoring_active = False
            self.monitoring_thread = None
            logger.info("Global monitoring system stopped")
            return True  # Indicate global stop
        return False  # Indicate only chat-specific stop

    def get_status(self):
        """Get current monitoring status"""
        temp_parser = DataParser()
        records = temp_parser.parse()
        unresolved = [record for record in records if not record.resolved]

        return {
            "total_violations": len(records),
            "unresolved": len(unresolved),
            "resolved": len(records) - len(unresolved),
            "resolution_rate": ((len(records) - len(unresolved)) / len(records) * 100)
            if records
            else 0,
            "monitoring_active": self.monitoring_active,
            "active_subscribers": len(self.active_chat_ids),
        }

    def add_demo_violation(self):
        """Add demo violation and return the record"""
        return self.parser.add_example_violation()

    def get_unresolved_records(self):
        """Get all unresolved violation records"""
        return self.parser.get_unresolved_records()

    def update_resolved_status(self, row_index, resolved=True):
        """Update resolved status of a violation record"""
        return self.parser.update_resolved_status(row_index, resolved)

def add_chat_id(chat_id: str) -> bool:
    """
    Add a WhatsApp chat_id to Snowflake and active_chat_ids set for notifications.
    Returns True if added, False if already present.
    """
    # Accept only digits (country code + number), 8 to 15 digits
    if not isinstance(chat_id, str) or not chat_id.isdigit() or not (8 <= len(chat_id) <= 15):
        return False

    # Add to Snowflake first
    success = monitor.parser.add_chat_id(chat_id)
    if success:
        # Add to local set if successfully added to Snowflake
        monitor.active_chat_ids.add(chat_id)
        logger.info(f"Added new chat_id to notifications: {chat_id}")
        return True
    else:
        # Check if it already exists in local set
        if chat_id in monitor.active_chat_ids:
            return False
        else:
            # If not in local set but failed to add to Snowflake,
            # it might already exist in Snowflake, so add to local set
            monitor.active_chat_ids.add(chat_id)
            logger.info(f"Added existing chat_id to local notifications: {chat_id}")
            return False  # Return False to indicate it wasn't newly added


# Global monitor instance
monitor = ViolationMonitor()


# WhatsApp message handlers
# @bot.router.message(type_message=filters.TEXT_TYPES)
# def message_handler(notification: Notification) -> None:
#     """Handle all incoming WhatsApp messages"""
#     text = (notification.message_text.strip().lower() if notification.message_text else "")
#     chat_id = notification.chat

#     # Auto-subscribe every user who sends any message
#     if chat_id not in monitor.active_chat_ids:
#         monitor.active_chat_ids.add(chat_id)
#         # Optionally, send a message to notify user of auto-subscription
#         try:
#             notification.answer(
#                 "🔔 You have been automatically subscribed to CCTV violation monitoring notifications."
#             )
#         except Exception as e:
#             logger.error(f"Failed to send auto-subscribe message: {e}")

#     # Handle monitoring commands
#     if text == "/start" or text == "start":
#         start_command(notification)
#         return
#     elif text == "/status" or text == "status":
#         status_command(notification)
#         return
#     elif text == "/monitor" or text == "monitor":
#         start_monitoring_command(notification)
#         return
#     elif text == "/stop" or text == "stop":
#         stop_monitoring_command(notification)
#         return
#     elif text == "/demo" or text == "demo":
#         demo_command(notification)
#         return
#     elif text == "/help" or text == "help":
#         help_command(notification)
#         return
#     elif text.startswith("resolve "):
#         handle_resolve_command(notification)
#         return

#     else:
#         # Unknown command - show help
#         help_command(notification)


def start_command(notification: Any) -> None:
    """Handle /start command for WhatsApp"""
    chat_id = notification.chat

    # Check if monitoring is already active and if this chat is already subscribed
    if monitor.monitoring_active and chat_id in monitor.active_chat_ids:
        notification.answer(
            "Hi! 🚨 CCTV Violation Monitoring Bot is already active for this chat."
        )
    else:
        # Initialize monitoring system when /start is called
        monitoring_started = monitor.start_monitoring(chat_id)

        if monitoring_started:
            initialization_msg = "🔔 MONITORING SYSTEM INITIALIZED"
        else:
            initialization_msg = "📱 NOTIFICATIONS ENABLED FOR THIS CHAT"

        notification.answer(
            f"Hi! 🚨 CCTV Violation Monitoring Bot is active.\n\n{initialization_msg}"
        )

    # Show current unresolved violations
    records = monitor.get_unresolved_records()

    if records:
        notification.answer(f"📋 Current unresolved violations: {len(records)}")
        for record in records[:3]:  # Show max 3 records
            send_violation_message(notification, record)
    else:
        notification.answer("✅ No unresolved violations at the moment.")


def send_violation_message(notification, record):
    """Send a violation message with case-specific Streamlit link"""
    # Create case-specific Streamlit app link
    case_url = f"{STREAMLIT_URL}/?case_id={record.row_index}"
    status_text = "✅ Resolved" if record.resolved else "❌ Unresolved"

    violation_text = (
        f"🆔 Case ID: {record.row_index}\n"
        f"⏰ Time: {record.timestamp}\n"
        f"🏭 Area: {record.factory_area}\n"
        f"🔍 Section: {record.inspection_section}\n"
        f"⚠️ Violation: {record.violation_type}\n"
        f"📋 Status: {status_text}\n"
        f"🔗 Review Case: {case_url}\n\n"
        f"Reply with: 'resolve {record.row_index}' to mark as resolved"
    )

    # Send the violation message
    # Note: Incoming message handling is disabled in this build; this function is kept for reference.
    try:
        notification.answer(violation_text)
    except Exception:
        pass


def status_command(notification: Any) -> None:
    """Show current violation status"""
    status = monitor.get_status()
    chat_id = notification.chat
    is_subscribed = chat_id in monitor.active_chat_ids

    status_text = (
        f"📊 **VIOLATION MONITORING STATUS**\n\n"
        f"🚨 Total Violations: {status['total_violations']}\n"
        f"⚠️ Unresolved: {status['unresolved']}\n"
        f"✅ Resolved: {status['resolved']}\n"
        f"📈 Resolution Rate: {status['resolution_rate']:.1f}%\n\n"
        f"🔔 Monitoring: {'Active' if status['monitoring_active'] else 'Inactive'}\n"
        f"📱 Active Subscribers: {status['active_subscribers']}\n"
        f"💬 This Chat: {'Subscribed' if is_subscribed else 'Not Subscribed'}\n\n"
        f"🔗 Web Interface: {STREAMLIT_URL}\n\n"
        f"Type 'help' for available commands."
    )

    try:
        notification.answer(status_text)
    except Exception:
        pass


def start_monitoring_command(notification: Any) -> None:
    """Register this chat for monitoring notifications (does not start a new monitoring thread)"""
    chat_id = notification.chat

    if monitor.monitoring_active and chat_id in monitor.active_chat_ids:
        notification.answer("🔔 Monitoring system is already active for this chat!")
        return

    # Register this chat for notifications
    monitoring_started = monitor.start_monitoring(chat_id)

    if monitoring_started:
        try:
            notification.answer(
            "🔔 **MONITORING SYSTEM STARTED**\n\n"
            "✅ Now monitoring SQL db for new violations\n"
            "📊 Real-time notifications enabled for this chat\n"
            "⏱️ Checking every 5 seconds\n\n"
            f"📈 Currently tracking {monitor.last_record_count} existing records\n"
            "Use 'demo' to test with example violation!"
        )
        except Exception:
            pass
    else:
        try:
            notification.answer(
            "🔔 **NOTIFICATIONS ENABLED**\n\n"
            "✅ Added this chat to existing monitoring system\n"
            "📊 Real-time notifications enabled for this chat\n"
            "⏱️ Monitoring already active every 5 seconds\n\n"
            f"📈 Currently tracking {monitor.last_record_count} existing records\n"
            "Use 'demo' to test with example violation!"
        )
        except Exception:
            pass


def stop_monitoring_command(notification: Any) -> None:
    chat_id = notification.chat

    if not monitor.monitoring_active or chat_id not in monitor.active_chat_ids:
        notification.answer("🔕 Monitoring system is not active for this chat!")
        return

    # Stop monitoring for this chat
    global_stopped = monitor.stop_monitoring(chat_id)

    if global_stopped:
        try:
            notification.answer(
            "🔕 **MONITORING SYSTEM STOPPED**\n\n"
            "❌ SQL monitoring disabled globally\n"
            "📵 All real-time notifications paused"
        )
        except Exception:
            pass
    else:
        try:
            notification.answer(
            "🔕 **NOTIFICATIONS DISABLED**\n\n"
            "❌ This chat will no longer receive notifications\n"
            f"📊 Monitoring continues for {len(monitor.active_chat_ids)} other chat(s)"
        )
        except Exception:
            pass


def demo_command(notification: Any) -> None:
    """Demo the notification system with example violation"""
    chat_id = notification.chat

    try:
        notification.answer(
        "🚀 **STARTING DEMO**\n\n"
        "1️⃣ Adding example violation to SQL...\n"
        "2️⃣ Will send notification in 3 seconds...\n"
        "3️⃣ You can then test the resolve command!"
    )
    except Exception:
        pass

    # Add example violation using monitor
    example_record = monitor.add_demo_violation()

    if example_record:
        try:
            notification.answer("✅ Example violation added to SQL!")
        except Exception:
            pass

        # Wait a moment then send notification
        time.sleep(3)

        # Re-parse to get the correct row_index
        monitor.parser.records = []
        updated_records = monitor.parser.parse()

        # Find the newly added record (should be the last one)
        if updated_records:
            new_record = updated_records[-1]
            monitor.send_new_violation_alert(new_record, chat_id)

            try:
                notification.answer(
                "🎯 **DEMO COMPLETE!**\n\n"
                "✅ Violation notification sent above\n"
                "📝 Type 'resolve [case_id]' to test resolution\n"
                "📊 Type 'status' to check updated statistics"
            )
            except Exception:
                pass
        else:
            try:
                notification.answer("❌ Failed to retrieve the new record")
            except Exception:
                pass
    else:
        try:
            notification.answer("❌ Failed to add example violation")
        except Exception:
            pass


def help_command(notification: Any) -> None:
    """Send a message when the command /help is issued."""
    help_text = ("🚨 **CCTV Violation Monitoring Bot**\n\n"
                 "**Available Commands:**\n"
                 "• `start` - View current unresolved violations\n"
                 "• `status` - View violation statistics & monitoring status\n"
                 "• `monitor` - Start real-time SQL monitoring\n"
                 "• `stop` - Stop monitoring system\n"
                 "• `demo` - Test notification system with example\n"
                 "• `help` - Show this help message\n\n"
                 "**Violation Commands:**\n"
                 "• `resolve [case_id]` - Mark violation as resolved\n\n"
                 "**Features:**\n"
                 "• Real-time monitoring of new violations\n"
                 "• Case-specific web links for direct navigation\n"
                 "• Automatic SQL db updates\n"
                 "• Multiple chat support\n\n"
                 "🔗 **Web Interface:** " + STREAMLIT_URL + "\n"
                 "Each violation notification includes a direct link to view and manage that specific case.")
    try:
        notification.answer(help_text)
    except Exception:
        pass


def handle_resolve_command(notification: Any) -> None:
    """Handle resolve command via text"""
    text = notification.message_text.strip() if notification.message_text else ""

    try:
        case_id = int(text.split("resolve ")[1])
        success = monitor.update_resolved_status(case_id, True)

        if success:
            case_url = f"{STREAMLIT_URL}/?case_id={case_id}"
            try:
                notification.answer(
                f"✅ Case ID {case_id} has been marked as RESOLVED.\n\n"
                f"🔗 View updated case: {case_url}"
            )
            except Exception:
                pass
        else:
            try:
                notification.answer(
                f"❌ Failed to resolve Case ID {case_id}. Please try again or resolve manually in the web interface."
            )
            except Exception:
                pass
    except (IndexError, ValueError):
        try:
            notification.answer("❌ Invalid format. Use: resolve [case_id]")
        except Exception:
            pass





def create_web_app():
    """Create Flask web app for deployment health check."""
    app = Flask(__name__)

    @app.route('/')
    def hello():
        return "Hello! CCTV Violation Monitoring Bot is running."

    @app.route('/health')
    def health():
        return {"status": "healthy", "service": "cctv-violation-monitor"}

    return app

def run_web_server():
    """Run the Flask web server."""
    app = create_web_app()
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)

def main() -> None:
    """Start the WhatsApp bot and web server."""
    # Initialize monitor with WhatsApp client
    monitor.initialize(wa)
    # Start monitoring globally on bot launch (no chat_id needed)
    # This is the ONLY place the monitoring thread should ever be started!
    if not monitor.monitoring_active:
        monitor.monitoring_active = True
        monitor.monitoring_thread = threading.Thread(
            target=monitor.monitor_sql_db, daemon=True
        )
        if monitor.monitoring_thread is not None:
            monitor.monitoring_thread.start()
        logger.info("Global monitoring system started on bot launch")

    # Start web server in a separate thread
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("Web server started on port 5001")

    print("🚨 CCTV Violation Monitoring Bot is running!")
    print("📱 Send any message to be auto-subscribed to monitoring notifications")
    print("💬 Send 'help' for available commands")
    print("🌐 Web server running on port 5001")

    # Block main thread to keep the process alive since we don't run a message listener here
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
