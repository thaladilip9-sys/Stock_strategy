from src.main.commodity.get_current_price import main as commodity_main
from src.main.commodity.get_contract_data import smart_mcx_contracts
from src.main.commodity.get_three_day_high_low import simple_trading_strategy
import threading
from src.utils.send_message import send_telegram_message
import schedule
import time


def analyze_and_alert(data):
    if data:
        result = simple_trading_strategy(data)
        print(result['message'])

        commodity_main( result)

def send_initial_message():
    initial_message = (
        "🚀 *Commodity Alert System Started!*\n"
        "You'll receive alerts for GOLDM and SILVERM based on the latest market data.\n"
        "Stay tuned for updates!"
    )
    send_telegram_message(initial_message)

def schedule_initial_message():
    schedule.every().day.at("08:00").do(send_initial_message)
    threading.Thread(target=run_schedule, daemon=True).start()

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(30)

# Call this function at the start of your main()



def main():
    """Main function to run the commodity analysis and alert system with threading"""
    goldm_data, silverm_data = smart_mcx_contracts()


    threads = []
    if goldm_data:
        t1 = threading.Thread(target=analyze_and_alert, args=(goldm_data,))
        threads.append(t1)
        t1.start()
    if silverm_data:
        t2 = threading.Thread(target=analyze_and_alert, args=(silverm_data,))
        threads.append(t2)
        t2.start()

    for t in threads:
        t.join()

if __name__ == "__main__":
    main()

