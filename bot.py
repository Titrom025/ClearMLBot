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
            experiment_infos, train_images, val_images = user_api_client.update_running_experiments()

            for experiment_info, train_image, val_image in zip(experiment_infos, train_images, val_images):
                experiment_name = experiment_info["experiment_name"]
                last_iteration = experiment_info["last_iteration"]
                message_text = experiment_info["message"]
                experiment_info = self.database.get_experiment_info(experiment_name)

                last_iteration_db = experiment_info[1]
                if last_iteration == last_iteration_db:
                    continue
                
                if experiment_info and experiment_info[2] != -1:
                    _, _, _, train_msg_id, val_msg_id = experiment_info
                    sent_message = self.bot.send_message(chat_id, message_text)
                    self.database.store_experiment_info(experiment_name, last_iteration, sent_message.message_id, train_msg_id, val_msg_id)
                else:
                    sent_message = self.bot.send_message(chat_id, message_text)
                    self.database.store_experiment_info(experiment_name, last_iteration, sent_message.message_id, -1, -1)

                if train_image is not None:
                    self.send_or_update_photo(chat_id, experiment_name, last_iteration, train_image, "train")
                if val_image is not None:
                    self.send_or_update_photo(chat_id, experiment_name, last_iteration, val_image, "val")


    def send_or_update_photo(self, chat_id, experiment_name, last_iteration, image, section):
        if section not in ["train", "val"]:
            print(f'Section {section} not in [train, val]')
            return
        experiment_info = self.database.get_experiment_info(experiment_name)
        if not experiment_info:
            print(f'Experiment {experiment_name} has no info in database')
            return

        _, _, text_msg_id, train_msg_id, val_msg_id = experiment_info
        if section == "train":
            message_id = train_msg_id
            train_msg_id = message_id
        elif section == "val":
            message_id = val_msg_id
            val_msg_id = message_id

        if message_id != -1:
            self.bot.delete_message(chat_id, message_id)
        sent_message = self.bot.send_photo(chat_id, image)
        self.database.store_experiment_info(experiment_name, last_iteration, sent_message.message_id, train_msg_id, val_msg_id)


    def start_bot(self):
        self.bot.polling()
