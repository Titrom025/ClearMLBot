import logging

import telebot

from clearml_api import ClearML_API_Wrapped


class ClearMLBot:
    def __init__(self, bot_token, database):
        self.database = database
        self.bot = telebot.TeleBot(bot_token)

        self.user_data = {}
        self.subscribed_users = set()
        self.user_sessions = {}

        def send_and_log(message, chat_id):
            logging.info(message)
            self.bot.send_message(chat_id, message)

        @self.bot.message_handler(commands=['start'])
        def start_command(message):
            self.bot.reply_to(
                message, 
                "Welcome to the ClearML assistant bot!\n"
                "Use /register to add your ClearML credentials.\n"
                "For more info type /help"
            )
            
        @self.bot.message_handler(commands=['help'])
        def start_command(message):
            self.bot.reply_to(
                message, 
                "Available commands:\n"
                "/help - print this message\n"
                "/register - add your ClearML credentials\n"
                "/subscribe - subscribe to your ClearML experiment updates\n"
                "/unsubscribe - stop receiving experiment updates\n"
                "/update - manually request information about active experiments\n"
            )

        @self.bot.message_handler(commands=['register'])
        def register_command(message):
            chat_id = message.chat.id
            if self.database.get_user_by_id(chat_id) is not None:
                self.bot.send_message(chat_id, "You have already registered!")
                return
            self.user_data[chat_id] = {
                "chat_id": message.chat.id,
                "username": message.chat.username
            }
            self.bot.send_message(chat_id, "Please enter your host:")
            self.bot.register_next_step_handler(message, self.get_host)

        @self.bot.message_handler(commands=['running_experiments'])
        def get_running_experiments(message):
            chat_id = message.chat.id
            if chat_id in self.subscribed_users:
                send_and_log(f'User {chat_id} was already subscribed!', chat_id)
                return
            self.subscribed_users.add(chat_id)
            send_and_log(f'User {chat_id} subscribed to updates!', chat_id)

        @self.bot.message_handler(commands=['subscribe'])
        def subscribe_command(message):
            chat_id = message.chat.id
            if chat_id in self.user_sessions:
                send_and_log(f'User {message.chat.username} was already subscribed!', chat_id)
                return
            self.subscribe_user(chat_id)
            send_and_log(f'User {message.chat.username} subscribed to updates!', chat_id)

        @self.bot.message_handler(commands=['unsubscribe'])
        def unsubscribe_command(message):
            chat_id = message.chat.id
            if chat_id not in self.user_sessions:
                send_and_log(f'User "{message.chat.username}" wasn\'t subscribed!', chat_id)
                return
            self.user_sessions.pop(chat_id)
            send_and_log(f'User "{message.chat.username}" unsubscribed from updates!', chat_id)

        @self.bot.message_handler(commands=['update'])
        def update_command(message):
            chat_id = message.chat.id
            if chat_id not in self.user_sessions:
                send_and_log(f'Use /subscribe to start tracking experiments', chat_id)
                return
            
            user_api_client = self.user_sessions[chat_id]
            experiments_info = user_api_client.update_running_experiments()
            if experiments_info is None:
                experiments_info = "No updates were found!"
            self.bot.send_message(chat_id, experiments_info)
            
        
    def polling(self):
        self.bot.polling()

    def get_host(self, message):
        chat_id = message.chat.id
        host = message.text.strip()
        self.user_data[chat_id]['host'] = host
        self.bot.send_message(chat_id, "Please enter your API token:")
        self.bot.register_next_step_handler(message, self.get_api_key)

    def get_api_key(self, message):
        chat_id = message.chat.id
        api_key = message.text.strip()
        self.user_data[chat_id]['api_key'] = api_key
        self.bot.send_message(chat_id, "Please enter your secret token:")
        self.bot.register_next_step_handler(message, self.get_secret_key)

    def subscribe_user(self, chat_id):
        user_from_db = self.database.get_user_by_id(chat_id)
        if user_from_db is None:
            self.bot.send_message(chat_id, "Use /register to add your ClearML credentials.")
            return

        db_chat_id, username, host, api_key, secret_key = user_from_db

        assert chat_id == db_chat_id
        user_api_client = ClearML_API_Wrapped(
            host,
            api_key,
            secret_key,
            self.database
        )
        self.user_sessions[chat_id] = user_api_client

    def get_secret_key(self, message):
        chat_id = message.chat.id
        secret_key = message.text.strip()
        self.user_data[chat_id]['secret_key'] = secret_key

        registered_data = self.user_data[chat_id]
        self.database.insert_user(
            chat_id,
            message.chat.username,
            registered_data['host'],
            registered_data['api_key'],
            registered_data['secret_key']
        )

        self.bot.send_message(chat_id, "Registration successful! Your credentials have been saved.")

    def send_updates_to_users(self):
        for chat_id in self.user_sessions:
            user_api_client = self.user_sessions[chat_id]
            experiments_info, train_image, val_image = user_api_client.update_running_experiments()
            if experiments_info is not None:
                self.bot.send_message(chat_id, experiments_info)
            if train_image is not None:
                self.bot.send_photo(chat_id, train_image)
            if val_image is not None:
                self.bot.send_photo(chat_id, val_image)


    def start_bot(self):
        self.bot.polling()
