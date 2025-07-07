from data import DataParser
import logging
import os
import asyncio
from datetime import datetime
from telegram import ForceReply, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.constants import ParseMode
from dotenv import load_dotenv
from telegram import constants
load_dotenv("../.env")
token = os.getenv("TELEGRAM_API_KEY")
if token == None:
    print("no token!!")
    exit()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

class ViolationMonitor:
    """Global monitoring system for CCTV violations"""

    def __init__(self):
        self.parser = DataParser()
        self.last_record_count = 0
        self.monitoring_active = False
        self.monitoring_task = None
        self.active_chat_ids = set()
        self.application = None

    def initialize(self, application):
        """Initialize the monitor with the Telegram application"""
        self.application = application
        records = self.parser.parse()
        self.last_record_count = len(records)
        logger.info(f"Monitor initialized with {self.last_record_count} existing records")

    async def send_new_violation_alert(self, record, chat_id):
        """Send alert for new violation to specific chat"""
        if not record.resolved and not record.confirmed:  # Only send alerts for unresolved and unconfirmed violations
            # Create case-specific Streamlit app link
            case_url = f"http://100.77.181.25:8501/?case_id={record.row_index}"

            violation_text = (f"🚨 NEW VIOLATION DETECTED\n\n"
                             f"🆔 Case ID: {record.row_index}\n"
                             f"⏰ Time: {record.timestamp}\n"
                             f"🏭 Area: {record.factory_area}\n"
                             f"🔍 Section: {record.inspection_section}\n"
                             f"⚠️ Violation: {record.violation_type}\n\n"
                             f"🔗 Review Case: {case_url}\n"
                             f"📋 Action Required: Click the buttons below or the link above to review this violation.")

            # Create inline keyboard
            keyboard = [
                [
                    InlineKeyboardButton("✅ Mark as Resolved", callback_data=f"resolve_{record.row_index}"),
                    InlineKeyboardButton("👁️ Confirm Violation", callback_data=f"confirm_{record.row_index}")
                ],
                [InlineKeyboardButton("🔗 Open in Web App", url=case_url)]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                # Send image with caption if available, otherwise send text message
                if hasattr(record, 'image_url') and record.image_url:
                    await self.application.bot.send_photo(
                        chat_id=chat_id,
                        photo=record.image_url,
                        caption=violation_text,
                        reply_markup=reply_markup
                    )
                else:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=violation_text,
                        reply_markup=reply_markup
                    )
            except Exception as e:
                    logger.error(f"Failed to send violation alert: {e}")
                    # Fallback: try to send just the text message if image fails
                    try:
                        await self.application.bot.send_message(
                            chat_id=chat_id,
                            text=violation_text,
                            reply_markup=reply_markup
                        )
                    except Exception as fallback_error:
                        logger.error(f"Failed to send fallback message: {fallback_error}")

    async def monitor_csv_file(self):
        """Monitor CSV file for new records"""
        while self.monitoring_active:
            try:
                # Create a fresh parser instance to avoid data conflicts
                temp_parser = DataParser()
                current_records = temp_parser.parse()
                current_count = len(current_records)

                logger.info(f"Monitoring: Found {current_count} total records, last count was {self.last_record_count}")

                if current_count > self.last_record_count:
                    # New records detected
                    new_records = current_records[self.last_record_count:]
                    logger.info(f"Detected {len(new_records)} new violation(s)")

                    # Send notifications to all active chat IDs
                    for record in new_records:
                        for chat_id in self.active_chat_ids:
                            try:
                                await self.send_new_violation_alert(record, chat_id)
                            except Exception as e:
                                logger.error(f"Failed to send notification to chat {chat_id}: {e}")

                    self.last_record_count = current_count

                    # Update the global parser's records to keep it in sync
                    self.parser.records = current_records

                await asyncio.sleep(1)  # Check every 5 seconds

            except Exception as e:
                logger.error(f"Error monitoring CSV file: {e}")
                await asyncio.sleep(1)

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

            # Start monitoring - ensure only one task exists
            if self.monitoring_task is not None:
                self.monitoring_task.cancel()

            self.monitoring_active = True
            self.monitoring_task = asyncio.create_task(self.monitor_csv_file())
            logger.info("Global monitoring system started")
            return True  # Indicate new monitoring started
        else:
            logger.info(f"Chat {chat_id} added to existing monitoring system")
            return False  # Indicate monitoring was already active

    def stop_monitoring(self, chat_id):
        """Stop monitoring for a specific chat, or globally if no more chats"""
        self.active_chat_ids.discard(chat_id)

        # If no more active chats, stop monitoring completely
        if not self.active_chat_ids:
            self.monitoring_active = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                self.monitoring_task = None
            logger.info("Global monitoring system stopped")
            return True  # Indicate global stop
        return False  # Indicate only chat-specific stop

    def get_status(self):
        """Get current monitoring status"""
        # Refresh data from CSV
        temp_parser = DataParser()
        records = temp_parser.parse()
        unresolved = [record for record in records if not record.resolved]
        unconfirmed = [record for record in records if not record.confirmed]

        return {
            'total_violations': len(records),
            'unresolved': len(unresolved),
            'unconfirmed': len(unconfirmed),
            'resolved': len(records) - len(unresolved),
            'resolution_rate': ((len(records) - len(unresolved)) / len(records) * 100) if records else 0,
            'monitoring_active': self.monitoring_active,
            'active_subscribers': len(self.active_chat_ids)
        }

    def add_demo_violation(self):
        """Add demo violation and return the record"""
        return self.parser.add_example_violation()

    def get_unresolved_records(self):
        """Get all unresolved violation records"""
        return self.parser.get_unresolved_records()

    def update_resolved_status(self, row_index, resolved=True):
        """Update resolved status of a violation"""
        return self.parser.update_resolved_status(row_index, resolved)

    def get_unconfirmed_records(self):
        """Get all unconfirmed violation records"""
        return self.parser.get_unconfirmed_records()

    def update_confirmed_status(self, row_index, confirmed=True):
        """Update confirmed status of a violation"""
        return self.parser.update_confirmed_status(row_index, confirmed)

# Global monitor instance
monitor = ViolationMonitor()
application = None

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks for marking violations as resolved"""
    query = update.callback_query
    await query.answer()

    if query.data.startswith("resolve_"):
        case_id = int(query.data.split("_")[1])
        # Update the violation status in the CSV
        success = monitor.update_resolved_status(case_id, True)

        if success:
            await query.edit_message_text(
                text=f"✅ Case ID {case_id} has been marked as RESOLVED.\n\n"
                     f"🔗 View updated case: http://100.77.181.25:8501/?case_id={case_id}"
            )
        else:
            await query.edit_message_text(
                text=f"❌ Failed to resolve Case ID {case_id}. Please try again or resolve manually in the web interface."
            )
    elif query.data.startswith("confirm_"):
        case_id = int(query.data.split("_")[1])
        # Update the confirmation status in the CSV
        success = monitor.update_confirmed_status(case_id, True)

        if success:
            # Handle case where message might have an image (photo) instead of just text
            try:
                await query.edit_message_text(
                    text=f"✅ Case ID {case_id} has been CONFIRMED.\n\n"
                         f"🔗 View updated case: http://100.77.181.25:8501/?case_id={case_id}"
                )
            except Exception as e:
                # If editing text fails (e.g., message has photo), edit caption instead
                try:
                    await query.edit_message_caption(
                        caption=f"✅ Case ID {case_id} has been CONFIRMED.\n\n"
                               f"🔗 View updated case: http://100.77.181.25:8501/?case_id={case_id}"
                    )
                except Exception as caption_error:
                    # If both fail, send a new message
                    await query.message.reply_text(
                        f"✅ Case ID {case_id} has been CONFIRMED.\n\n"
                        f"🔗 View updated case: http://100.77.181.25:8501/?case_id={case_id}"
                    )
        else:
            await query.edit_message_text(
                text=f"❌ Failed to confirm Case ID {case_id}. Please try again or confirm manually in the web interface."
            )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued and initialize monitoring."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Check if monitoring is already active and if this chat is already subscribed
    if monitor.monitoring_active and chat_id in monitor.active_chat_ids:
        await update.message.reply_text(
            f"Hi {user.first_name}! 🚨 CCTV Violation Monitoring Bot is already active for this chat.",
            reply_markup=ForceReply(selective=True),
        )
    else:
        # Initialize monitoring system when /start is called
        monitoring_started = monitor.start_monitoring(chat_id)

        if monitoring_started:
            initialization_msg = "\n🔔 MONITORING SYSTEM INITIALIZED"
        else:
            initialization_msg = "\n📱 NOTIFICATIONS ENABLED FOR THIS CHAT"

        await update.message.reply_text(
            f"Hi {user.first_name}! 🚨 CCTV Violation Monitoring Bot is active.{initialization_msg}",
            reply_markup=ForceReply(selective=True),
        )

    # Show current unresolved violations
    records = monitor.get_unresolved_records()
    unconfirmed = monitor.get_unconfirmed_records()

    if records:
        await update.message.reply_text(f"📋 Current unresolved violations: {len(records)}")
        for record in records[:5]:  # Show max 5 records
            await send_violation_message(update, record)
    else:
        await update.message.reply_text("✅ No unresolved violations at the moment.")

        if len(unconfirmed) > 0:
            unconfirmed_links = []
            for record in unconfirmed[:3]:  # Show max 3 direct links
                case_url = f"http://100.77.181.25:8501/?case_id={record.row_index}"
                unconfirmed_links.append(f"• Case {record.row_index} - {record.violation_type}: {case_url}")

            links_text = "\n".join(unconfirmed_links)
            if len(unconfirmed) > 3:
                links_text += f"\n• ... and {len(unconfirmed) - 3} more cases"

            await update.message.reply_text(f"⚠️ Unconfirmed violations require your attention:\n{links_text}")

    # await update.message.reply_text(
    #     "🚨 CCTV Violation Monitoring Bot\\n\\n"
    #     "Commands:\\n"
    #     "/start - View current unresolved violations\\n"
    #     "/status - View violation statistics & monitoring status\\n"
    #     "/monitor - Start real-time CSV monitoring\\n"
    #     "/stop - Stop monitoring system\\n"
    #     "/demo - Test notification system with example\\n"
    #     "/help - Show this help message\\n\\n"
    #     "Features:\\n"
    #     "• Real-time monitoring of new violations\\n"
    #     "• Case-specific web links for direct navigation\\n"
    #     "• Mark violations as resolved with one click\\n"
    #     "• Automatic CSV file updates\\n"
    #     "• Demo mode for testing functionality\\n\\n"
    #     "🔗 Direct Case Access:\\n"
    #     "Each violation notification includes a direct link to view and manage that specific case in the web interface.",
    #     parse_mode=constants.ParseMode.MARKDOWN_V2
    # )

async def send_violation_message(update, record):
    """Send a violation message with case-specific Streamlit link"""
    # Create case-specific Streamlit app link
    case_url = f"http://100.77.181.25:8501/?case_id={record.row_index}"
    status_text = '✅ Confirmed' if record.confirmed else '⚠️ Pending Confirmation'

    violation_text = (f"🆔 Case ID: {record.row_index}\n"
                     f"⏰ Time: {record.timestamp}\n"
                     f"🏭 Area: {record.factory_area}\n"
                     f"🔍 Section: {record.inspection_section}\n"
                     f"⚠️ Violation: {record.violation_type}\n"
                     f"📋 Status: {status_text}\n"
                     f"🔗 Review Case: {case_url}")

    # Create inline keyboard for unresolved violations
    keyboard = []
    if not record.resolved:
        keyboard.append([
            InlineKeyboardButton("✅ Mark as Resolved", callback_data=f"resolve_{record.row_index}")
        ])
    if not record.confirmed:
        keyboard.append([
            InlineKeyboardButton("👁️ Confirm Violation", callback_data=f"confirm_{record.row_index}")
        ])
    keyboard.append([InlineKeyboardButton("🔗 Open in Web App", url=case_url)])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    try:
        # Send image with caption if available, otherwise send text message
        if hasattr(record, 'image_url') and record.image_url:
            await update.message.reply_photo(
                photo=record.image_url,
                caption=violation_text,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                violation_text,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Failed to send violation message: {e}")
        # Fallback: try to send plain text message
        try:
            await update.message.reply_text(violation_text)
        except Exception as fallback_error:
            logger.error(f"Failed to send fallback violation message: {fallback_error}")



async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current violation status"""
    status = monitor.get_status()
    chat_id = update.effective_chat.id
    is_subscribed = chat_id in monitor.active_chat_ids

    await update.message.reply_text(
        "🚨 CCTV Violation Monitoring Bot\n\n"
        "Commands:\n"
        "/start - View current unresolved violations\n"
        "/status - View violation statistics & monitoring status\n"
        "/monitor - Start real-time CSV monitoring\n"
        "/stop - Stop monitoring system\n"
        "/demo - Test notification system with example\n"
        "/help - Show this help message\n\n"
        "Features:\n"
        "• Real-time monitoring of new violations\n"
        "• Case-specific web links for direct navigation\n"
        "• Web-based violation management interface\n"
        "• Automatic CSV file updates\n"
        "• Demo mode for testing functionality\n\n"
        "🔗 Web Interface: http://100.77.181.25:8501\n"
        "Each violation includes a direct link to view that specific case."
    )

async def start_monitoring_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the CSV monitoring system"""
    chat_id = update.effective_chat.id

    if monitor.monitoring_active and chat_id in monitor.active_chat_ids:
        await update.message.reply_text("🔔 Monitoring system is already active for this chat!")
        return

    # Start monitoring for this chat
    monitoring_started = monitor.start_monitoring(chat_id)

    if monitoring_started:
        await update.message.reply_text(
            "🔔 **MONITORING SYSTEM STARTED**\n\n"
            "✅ Now monitoring CSV file for new violations\n"
            "📊 Real-time notifications enabled for this chat\n"
            "⏱️ Checking every 5 seconds\n\n"
            f"📈 Currently tracking {monitor.last_record_count} existing records\n"
            "Use /demo to test with example violation!"
        )
    else:
        await update.message.reply_text(
            "🔔 **NOTIFICATIONS ENABLED**\n\n"
            "✅ Added this chat to existing monitoring system\n"
            "📊 Real-time notifications enabled for this chat\n"
            "⏱️ Monitoring already active every 5 seconds\n\n"
            f"📈 Currently tracking {monitor.last_record_count} existing records\n"
            "Use /demo to test with example violation!"
        )

async def stop_monitoring_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stop the CSV monitoring system"""
    chat_id = update.effective_chat.id

    if not monitor.monitoring_active or chat_id not in monitor.active_chat_ids:
        await update.message.reply_text("🔕 Monitoring system is not active for this chat!")
        return

    # Stop monitoring for this chat
    global_stopped = monitor.stop_monitoring(chat_id)

    if global_stopped:
        await update.message.reply_text(
            "🔕 **MONITORING SYSTEM STOPPED**\n\n"
            "❌ CSV monitoring disabled globally\n"
            "📵 All real-time notifications paused"
        )
    else:
        await update.message.reply_text(
            "🔕 **NOTIFICATIONS DISABLED**\n\n"
            "❌ This chat will no longer receive notifications\n"
            f"📊 Monitoring continues for {len(monitor.active_chat_ids)} other chat(s)"
        )

async def demo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Demo the notification system with example violation"""
    chat_id = update.effective_chat.id

    await update.message.reply_text(
        "🚀 **STARTING DEMO**\n\n"
        "1️⃣ Adding example violation to CSV...\n"
        "2️⃣ Will send notification in 3 seconds...\n"
        "3️⃣ You can then test the resolve button!"
    )

    # Add example violation using monitor
    example_record = monitor.add_demo_violation()

    if example_record:
        await update.message.reply_text("✅ Example violation added to CSV!")

        # Wait a moment then send notification
        await asyncio.sleep(3)

        # Re-parse to get the correct row_index
        monitor.parser.records = []
        updated_records = monitor.parser.parse()

        # Find the newly added record (should be the last one)
        if updated_records:
            new_record = updated_records[-1]
            await monitor.send_new_violation_alert(new_record, chat_id)

            await update.message.reply_text(
                "🎯 **DEMO COMPLETE!**\n\n"
                "✅ Violation notification sent above\n"
                "🔘 Click 'Mark as Resolved ✅' to test resolution\n"
                "📊 Use /status to check updated statistics"
            )
        else:
            await update.message.reply_text("❌ Failed to retrieve the new record")
    else:
        await update.message.reply_text("❌ Failed to add example violation")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "🚨 CCTV Violation Monitoring Bot\n\n"
        "Commands:\n"
        "/start - View current unresolved violations\n"
        "/status - View violation statistics & monitoring status\n"
        "/monitor - Start real-time CSV monitoring\n"
        "/stop - Stop monitoring system\n"
        "/demo - Test notification system with example\n"
        "/help - Show this help message\n\n"
        "Features:\n"
        "• Real-time monitoring of new violations\n"
        "• Case-specific web links for direct navigation\n"
        "• Mark violations as resolved with one click\n"
        "• Automatic CSV file updates\n"
        "• Demo mode for testing functionality\n\n"
        "🔗 Direct Case Access:\n"
        "Each violation notification includes a direct link to view and manage that specific case in the web interface."
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)


def main() -> None:
    """Start the bot."""
    global application

    application = Application.builder().token(token).build()
    print("Bot is running! Use /help to see available commands")

    # Initialize monitor with application
    monitor.initialize(application)

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("monitor", start_monitoring_command))
    application.add_handler(CommandHandler("stop", stop_monitoring_command))
    application.add_handler(CommandHandler("demo", demo_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()


# import requests
# import re

# instance_id = "7105261734"
# token = "53932e1d9cc54807b89f20ceb89d159de794f9123037431780"

# # Country code mapping and validation regex per country
# country_data = {
#     "Singapore (+65)": {"code": "65", "regex": r"^[689]\d{7}$"},
#     "Malaysia (+60)": {"code": "60", "regex": r"^1[0-9]{8,9}$"},
#     "Indonesia (+62)": {"code": "62", "regex": r"^8[1-9][0-9]{6,9}$"},
#     "Philippines (+63)": {"code": "63", "regex": r"^9\d{9}$"},
#     "Thailand (+66)": {"code": "66", "regex": r"^8\d{8}$|^9\d{8}$"},
#     "Vietnam (+84)": {"code": "84", "regex": r"^((3[2-9])|(5[6|8|9])|(7[0|6-9])|(8[1-9])|(9[0-9]))\d{7}$"},
#     "India (+91)": {"code": "91", "regex": r"^[6-9]\d{9}$"},
#     "Pakistan (+92)": {"code": "92", "regex": r"^3[0-6]\d{8}$"},
#     "China (+86)": {"code": "86", "regex": r"^1[3-9]\d{9}$"},
#     "Japan (+81)": {"code": "81", "regex": r"^([789]0)\d{8}$"},
#     "South Korea (+82)": {"code": "82", "regex": r"^1[0-9]{9}$"},
#     "Bangladesh (+880)": {"code": "880", "regex": r"^1[3-9]\d{8}$"},
# }

# selected_country="Singapore (+65)"
# local_number="81899220"
# data = country_data[selected_country]
# full_number = data["code"] + local_number
# print(full_number)
# phone_pattern = re.compile(data["regex"])

# message=""""""
# for record in records:
#     message += f"Time: {record.timestamp}, Area: {record.factory_area}, Violation: {record.violation_type}\n"

# if not phone_pattern.match(local_number):
#     print(f"Invalid number format for {selected_country}.")
# else:
#     url = f"https://api.green-api.com/waInstance{instance_id}/sendMessage/{token}"
#     payload = {
#         "chatId": f"{full_number}@c.us",
#         "message": message
#     }

# response = requests.post(url, json=payload)
# print(response.status_code)
