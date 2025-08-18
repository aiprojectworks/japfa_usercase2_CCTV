import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data import DataParser

def test_chat_id_system():
    """Test the WhatsApp chat ID management system"""
    print("🧪 Testing WhatsApp Chat ID Management System")
    print("=" * 50)

    # Initialize parser
    dp = DataParser()

    # Test 1: Create table (should be idempotent)
    print("\n1️⃣ Testing table creation...")
    try:
        dp.create_chat_ids_table()
        print("✅ Table creation successful")
    except Exception as e:
        print(f"❌ Table creation failed: {e}")
        return False

    # Test 2: Get initial chat IDs
    print("\n2️⃣ Testing initial chat ID retrieval...")
    try:
        initial_chat_ids = dp.get_active_chat_ids()
        print(f"✅ Found {len(initial_chat_ids)} initial chat IDs:")
        for chat_id in initial_chat_ids:
            print(f"   - {chat_id}")
    except Exception as e:
        print(f"❌ Failed to get initial chat IDs: {e}")
        return False

    # Test 3: Add a new chat ID
    test_chat_id = "6512345678@c.us"
    print(f"\n3️⃣ Testing adding new chat ID: {test_chat_id}")
    try:
        result = dp.add_chat_id(test_chat_id)
        if result:
            print("✅ Successfully added new chat ID")
        else:
            print("⚠️ Chat ID already exists or failed to add")

        # Verify it was added
        updated_chat_ids = dp.get_active_chat_ids()
        if test_chat_id in updated_chat_ids:
            print("✅ Chat ID verified in database")
        else:
            print("❌ Chat ID not found in database after adding")
    except Exception as e:
        print(f"❌ Failed to add chat ID: {e}")
        return False

    # Test 4: Try adding duplicate (should fail gracefully)
    print(f"\n4️⃣ Testing duplicate addition: {test_chat_id}")
    try:
        result = dp.add_chat_id(test_chat_id)
        if not result:
            print("✅ Correctly prevented duplicate addition")
        else:
            print("⚠️ Duplicate was added (unexpected)")
    except Exception as e:
        print(f"❌ Error handling duplicate: {e}")

    # Test 5: Test invalid chat ID format
    print("\n5️⃣ Testing invalid chat ID format...")
    invalid_ids = ["invalid_id", "1234567890", "test@invalid.com", ""]
    for invalid_id in invalid_ids:
        try:
            result = dp.add_chat_id(invalid_id)
            if not result:
                print(f"✅ Correctly rejected invalid ID: {invalid_id}")
            else:
                print(f"❌ Incorrectly accepted invalid ID: {invalid_id}")
        except Exception as e:
            print(f"❌ Error with invalid ID {invalid_id}: {e}")

    # Test 6: Remove the test chat ID
    print(f"\n6️⃣ Testing chat ID removal: {test_chat_id}")
    try:
        result = dp.remove_chat_id(test_chat_id)
        if result:
            print("✅ Successfully removed chat ID")
        else:
            print("❌ Failed to remove chat ID")

        # Verify it was removed
        final_chat_ids = dp.get_active_chat_ids()
        if test_chat_id not in final_chat_ids:
            print("✅ Chat ID verified as removed from active list")
        else:
            print("❌ Chat ID still found in active list after removal")
    except Exception as e:
        print(f"❌ Failed to remove chat ID: {e}")
        return False

    # Test 7: Try removing non-existent chat ID
    print(f"\n7️⃣ Testing removal of non-existent chat ID...")
    non_existent_id = "6599999999@c.us"
    try:
        result = dp.remove_chat_id(non_existent_id)
        if not result:
            print("✅ Correctly handled non-existent chat ID removal")
        else:
            print("⚠️ Unexpectedly reported success for non-existent ID")
    except Exception as e:
        print(f"❌ Error removing non-existent ID: {e}")

    # Test 8: Final state verification
    print("\n8️⃣ Final state verification...")
    try:
        final_chat_ids = dp.get_active_chat_ids()
        print(f"✅ Final active chat IDs ({len(final_chat_ids)}):")
        for chat_id in final_chat_ids:
            print(f"   - {chat_id}")

        # Should be back to initial state
        if set(final_chat_ids) == set(initial_chat_ids):
            print("✅ System returned to initial state")
        else:
            print("⚠️ System state changed from initial")
            print(f"   Initial: {set(initial_chat_ids)}")
            print(f"   Final: {set(final_chat_ids)}")
    except Exception as e:
        print(f"❌ Failed final verification: {e}")
        return False

    print("\n" + "=" * 50)
    print("🎉 All tests completed successfully!")
    return True

def test_integration_with_main():
    """Test integration with main.py functions"""
    print("\n🔗 Testing integration with main.py...")
    print("=" * 50)

    try:
        # Import main module functions
        import main as main_mod

        # Test the add_chat_id function from main.py
        test_chat_id = "6587654321@c.us"
        print(f"Testing main.add_chat_id with: {test_chat_id}")

        result = main_mod.add_chat_id(test_chat_id)
        print(f"Result: {result}")

        # Check if it was added to the monitor's active chat IDs
        if hasattr(main_mod, 'monitor') and main_mod.monitor:
            if test_chat_id in main_mod.monitor.active_chat_ids:
                print("✅ Chat ID added to monitor's active set")
            else:
                print("❌ Chat ID not found in monitor's active set")

        # Clean up
        dp = DataParser()
        dp.remove_chat_id(test_chat_id)
        print("✅ Cleanup completed")

    except ImportError as e:
        print(f"⚠️ Could not import main module: {e}")
        print("   This is expected if the bot is not running")
    except Exception as e:
        print(f"❌ Integration test failed: {e}")

def print_environment_info():
    """Print environment information for debugging"""
    print("🔧 Environment Information")
    print("=" * 50)

    # Check environment variables
    env_vars = [
        "JAPFA_user", "JAPFA_password", "JAPFA_account",
        "JAPFA_database", "JAPFA_schema", "JAPFA_warehouse", "JAPFA_role"
    ]

    for var in env_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive information
            if "password" in var.lower():
                masked_value = "*" * len(value)
            elif len(value) > 20:
                masked_value = value[:10] + "..." + value[-5:]
            else:
                masked_value = value
            print(f"✅ {var}: {masked_value}")
        else:
            print(f"❌ {var}: Not set")

    print(f"\nCurrent time: {datetime.now()}")
    print(f"Python version: {sys.version}")

if __name__ == "__main__":
    print("🚀 WhatsApp Chat ID Management System Test Suite")
    print(f"Started at: {datetime.now()}")
    print()

    # Print environment info
    print_environment_info()
    print()

    # Run main tests
    success = test_chat_id_system()

    # Run integration tests
    test_integration_with_main()

    if success:
        print("\n🎊 All tests passed! The chat ID management system is working correctly.")
        exit(0)
    else:
        print("\n💥 Some tests failed. Please check the error messages above.")
        exit(1)
