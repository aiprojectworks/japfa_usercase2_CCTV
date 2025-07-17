from data import DataParser
import logging
import os

from dotenv import load_dotenv
import threading
import time

# WhatsApp GreenAPI imports
from whatsapp_chatbot_python import (
    GreenAPIBot,
    Notification,
    filters,
)

load_dotenv("../.env")

# WhatsApp credentials
instance_id = os.getenv("ID_INSTANCE")
token = os.getenv("API_TOKEN_INSTANCE")

if not instance_id or not token:
    raise ValueError("INSTANCE_ID and TOKEN must be set in .env file")

# Streamlit web interface URL
STREAMLIT_URL = "https://hrtowii-fyp-proj-japfa-cctvstreamlit-app-xyay89.streamlit.app/"

# Initialize GreenAPI bot
bot = GreenAPIBot(instance_id, token)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class ViolationMonitor:
    """Global monitoring system for CCTV violations using WhatsApp"""

    def __init__(self):
        self.parser = DataParser()
        self.last_record_count = 0
        self.monitoring_active = False
        self.monitoring_thread = None
        self.active_chat_ids = set()
        self.bot = None

    def initialize(self, bot_instance):
        """Initialize the monitor with the WhatsApp bot"""
        self.bot = bot_instance
        records = self.parser.parse()
        self.last_record_count = len(records)
        logger.info(
            f"Monitor initialized with {self.last_record_count} existing records"
        )

    def send_new_violation_alert(self, record, chat_id):
        """Send alert for new violation to specific WhatsApp chat"""
        if not record.resolved:  # Only send alerts for unresolved violations
            # Create case-specific Streamlit app link
            case_url = f"{STREAMLIT_URL}/?case_id={record.row_index}"

            violation_text = (
                f"🚨 NEW VIOLATION DETECTED\n\n"
                f"🆔 Case ID: {record.row_index}\n"
                f"⏰ Time: {record.timestamp}\n"
                f"🏭 Area: {record.factory_area}\n"
                f"🔍 Section: {record.inspection_section}\n"
                f"⚠️ Violation: {record.violation_type}\n\n"
                f"🔗 Review Case: {case_url}\n\n"
                f"📋 Action Required: Reply with commands below:\n"
                f"• Type 'resolve {record.row_index}' to mark as resolved\n"
                f"• Type 'status' to view current statistics"
            )

            if self.bot is None:
                logger.error("Bot is not initialized")
                return

            try:
                # Send image with caption if available, otherwise send text message
                if hasattr(record, "image_url") and record.image_url:
                    self.bot.api.sending.sendFileByUrl(
                        chatId=chat_id,
                        urlFile=record.image_url,
                        fileName=f"violation_{record.row_index}.jpg",
                        caption=violation_text,
                    )
                else:
                    self.bot.api.sending.sendMessage(
                        chatId=chat_id, message=violation_text
                    )
            except Exception as e:
                logger.error(f"Failed to send violation alert: {e}")
                # Fallback: try to send just the text message
                try:
                    self.bot.api.sending.sendMessage(
                        chatId=chat_id, message=violation_text
                    )
                except Exception as fallback_error:
                    logger.error(f"Failed to send fallback message: {fallback_error}")

    def monitor_csv_file(self):
        """Monitor CSV file for new records in a separate thread"""
        while self.monitoring_active:
            try:
                # Create a fresh parser instance to avoid data conflicts
                temp_parser = DataParser()
                current_records = temp_parser.parse()
                current_count = len(current_records)

                logger.info(
                    f"Monitoring: Found {current_count} total records, last count was {self.last_record_count}"
                )

                if current_count > self.last_record_count:
                    # New records detected
                    new_records = current_records[self.last_record_count :]
                    logger.info(f"Detected {len(new_records)} new violation(s)")

                    # Send notifications to all active chat IDs
                    for record in new_records:
                        for chat_id in self.active_chat_ids:
                            try:
                                self.send_new_violation_alert(record, chat_id)
                            except Exception as e:
                                logger.error(
                                    f"Failed to send notification to chat {chat_id}: {e}"
                                )

                    self.last_record_count = current_count

                    # Update the global parser's records to keep it in sync
                    self.parser.records = current_records

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error monitoring CSV file: {e}")
                time.sleep(5)

    def start_monitoring(self, chat_id):
        """Start monitoring system for a specific chat"""
        self.active_chat_ids.add(chat_id)

        if not self.monitoring_active:
            # Initialize record count with fresh parsing
            temp_parser = DataParser()
            records = temp_parser.parse()
            self.last_record_count = len(records)

            # Update global parser
            self.parser.records = records

            # Start monitoring in a separate thread
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(
                target=self.monitor_csv_file, daemon=True
            )
            self.monitoring_thread.start()
            logger.info("Global monitoring system started")
            if self.bot is not None:
                try:
                    self.bot.api.sending.sendMessage(
                        chatId=chat_id,
                        message="Now monitoring CSV file for new violations."
                    )
                except Exception as e:
                    logger.error(f"Failed to send monitoring started message: {e}")
            return True
        else:
            logger.info(f"Chat {chat_id} added to existing monitoring system")
            return False

    def stop_monitoring(self, chat_id):
        """Stop monitoring for a specific chat, or globally if no more chats"""
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
        # Refresh data from CSV
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


# Global monitor instance
monitor = ViolationMonitor()


# WhatsApp message handlers
@bot.router.message(type_message=filters.TEXT_TYPES)
def message_handler(notification: Notification) -> None:
    """Handle all incoming WhatsApp messages"""
    text = notification.message_text.strip().lower()

    # Handle monitoring commands
    if text == "/start" or text == "start":
        start_command(notification)
        return
    elif text == "/status" or text == "status":
        status_command(notification)
        return
    elif text == "/monitor" or text == "monitor":
        start_monitoring_command(notification)
        return
    elif text == "/stop" or text == "stop":
        stop_monitoring_command(notification)
        return
    elif text == "/demo" or text == "demo":
        demo_command(notification)
        return
    elif text == "/help" or text == "help":
        help_command(notification)
        return
    elif text.startswith("resolve "):
        handle_resolve_command(notification)
        return

    else:
        # Unknown command - show help
        help_command(notification)


def start_command(notification: Notification) -> None:
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
    notification.answer(violation_text)


def status_command(notification: Notification) -> None:
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

    notification.answer(status_text)


def start_monitoring_command(notification: Notification) -> None:
    """Start the CSV monitoring system"""
    chat_id = notification.chat

    if monitor.monitoring_active and chat_id in monitor.active_chat_ids:
        notification.answer("🔔 Monitoring system is already active for this chat!")
        return

    # Start monitoring for this chat
    monitoring_started = monitor.start_monitoring(chat_id)

    if monitoring_started:
        notification.answer(
            "🔔 **MONITORING SYSTEM STARTED**\n\n"
            "✅ Now monitoring CSV file for new violations\n"
            "📊 Real-time notifications enabled for this chat\n"
            "⏱️ Checking every 5 seconds\n\n"
            f"📈 Currently tracking {monitor.last_record_count} existing records\n"
            "Use 'demo' to test with example violation!"
        )
    else:
        notification.answer(
            "🔔 **NOTIFICATIONS ENABLED**\n\n"
            "✅ Added this chat to existing monitoring system\n"
            "📊 Real-time notifications enabled for this chat\n"
            "⏱️ Monitoring already active every 5 seconds\n\n"
            f"📈 Currently tracking {monitor.last_record_count} existing records\n"
            "Use 'demo' to test with example violation!"
        )


def stop_monitoring_command(notification: Notification) -> None:
    """Stop the CSV monitoring system"""
    chat_id = notification.chat

    if not monitor.monitoring_active or chat_id not in monitor.active_chat_ids:
        notification.answer("🔕 Monitoring system is not active for this chat!")
        return

    # Stop monitoring for this chat
    global_stopped = monitor.stop_monitoring(chat_id)

    if global_stopped:
        notification.answer(
            "🔕 **MONITORING SYSTEM STOPPED**\n\n"
            "❌ CSV monitoring disabled globally\n"
            "📵 All real-time notifications paused"
        )
    else:
        notification.answer(
            "🔕 **NOTIFICATIONS DISABLED**\n\n"
            "❌ This chat will no longer receive notifications\n"
            f"📊 Monitoring continues for {len(monitor.active_chat_ids)} other chat(s)"
        )


def demo_command(notification: Notification) -> None:
    """Demo the notification system with example violation"""
    chat_id = notification.chat

    notification.answer(
        "🚀 **STARTING DEMO**\n\n"
        "1️⃣ Adding example violation to CSV...\n"
        "2️⃣ Will send notification in 3 seconds...\n"
        "3️⃣ You can then test the resolve command!"
    )

    # Add example violation using monitor
    example_record = monitor.add_demo_violation()

    if example_record:
        notification.answer("✅ Example violation added to CSV!")

        # Wait a moment then send notification
        time.sleep(3)

        # Re-parse to get the correct row_index
        monitor.parser.records = []
        updated_records = monitor.parser.parse()

        # Find the newly added record (should be the last one)
        if updated_records:
            new_record = updated_records[-1]
            monitor.send_new_violation_alert(new_record, chat_id)

            notification.answer(
                "🎯 **DEMO COMPLETE!**\n\n"
                "✅ Violation notification sent above\n"
                "📝 Type 'resolve [case_id]' to test resolution\n"
                "📊 Type 'status' to check updated statistics"
            )
        else:
            notification.answer("❌ Failed to retrieve the new record")
    else:
        notification.answer("❌ Failed to add example violation")


def help_command(notification: Notification) -> None:
    """Send a message when the command /help is issued."""
    help_text = ("🚨 **CCTV Violation Monitoring Bot**\n\n"
                 "**Available Commands:**\n"
                 "• `start` - View current unresolved violations\n"
                 "• `status` - View violation statistics & monitoring status\n"
                 "• `monitor` - Start real-time CSV monitoring\n"
                 "• `stop` - Stop monitoring system\n"
                 "• `demo` - Test notification system with example\n"
                 "• `help` - Show this help message\n\n"
                 "**Violation Commands:**\n"
                 "• `resolve [case_id]` - Mark violation as resolved\n\n"
                 "**Features:**\n"
                 "• Real-time monitoring of new violations\n"
                 "• Case-specific web links for direct navigation\n"
                 "• Automatic CSV file updates\n"
                 "• Multiple chat support\n\n"
                 "🔗 **Web Interface:** " + STREAMLIT_URL + "\n"
                 "Each violation notification includes a direct link to view and manage that specific case.")
    notification.answer(help_text)


def handle_resolve_command(notification: Notification) -> None:
    """Handle resolve command via text"""
    text = notification.message_text.strip()

    try:
        case_id = int(text.split("resolve ")[1])
        success = monitor.update_resolved_status(case_id, True)

        if success:
            case_url = f"{STREAMLIT_URL}/?case_id={case_id}"
            notification.answer(
                f"✅ Case ID {case_id} has been marked as RESOLVED.\n\n"
                f"🔗 View updated case: {case_url}"
            )
        else:
            notification.answer(
                f"❌ Failed to resolve Case ID {case_id}. Please try again or resolve manually in the web interface."
            )
    except (IndexError, ValueError):
        notification.answer("❌ Invalid format. Use: resolve [case_id]")





def main() -> None:
    """Start the WhatsApp bot."""
    # Initialize monitor with WhatsApp bot
    monitor.initialize(bot)
    print("🚨 CCTV Violation Monitoring Bot is running!")
    print("📱 Send 'start' to begin monitoring violations")
    print("💬 Send 'help' for available commands")

    # Start the WhatsApp bot
    bot.run_forever()


if __name__ == "__main__":
    main()
