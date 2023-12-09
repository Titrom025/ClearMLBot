import json
import time
import schedule
import threading

from bot import ClearMLBot
from database import Database


def main():
    database = Database()
    with open('config.json', 'r') as file:
        config = json.load(file)
    
    if config["TG_TOKEN"] == "TG_TOKEN":
        print("Please specify TG_TOKEN in config.json")
        exit(1)

    bot = ClearMLBot(config["TG_TOKEN"], database)

    schedule.every(5).seconds.do(bot.send_updates_to_users)

    bot_thread = threading.Thread(target=bot.polling)
    bot_thread.daemon = True
    bot_thread.start()

    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            print(f'An error occured in schedule.run_pending: {e}')


if __name__ == '__main__':
    main()
