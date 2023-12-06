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

    bot = ClearMLBot(config["TG_TOKEN"], database)

    schedule.every(5).seconds.do(bot.send_updates_to_users)

    bot_thread = threading.Thread(target=bot.polling)
    bot_thread.daemon = True
    bot_thread.start()

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    main()
