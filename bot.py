import logging
import re

import telebot

from clearml_api import ClearML_API_Wrapped


class ClearMLBot:
    def __init__(self, bot_token, database):
        self.database = database
        self.bot = telebot.TeleBot(bot_token)

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

            self.bot.send_message(chat_id, "Please go to https://app.clear.ml/settings/workspace-configuration, "
                                  "select \"Create new credentials\" then copy and send credentials here",
                                  disable_web_page_preview=True)
            self.bot.register_next_step_handler(message, self.get_user_creds)

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
        while True:
            try:
                self.bot.polling()
            except Exception as e:
                print(f'An error occured in bot.polling: {e}')

    def subscribe_user(self, chat_id):
        user_from_db = self.database.get_user_by_id(chat_id)
        if user_from_db is None:
            self.bot.send_message(chat_id, "Use /register to add your ClearML credentials.")
            return

        db_chat_id, username, host, api_key, secret_key = user_from_db

        if chat_id in self.user_sessions:
            return

        user_api_client = ClearML_API_Wrapped(
            host,
            api_key,
            secret_key,
            self.database
        )
        self.user_sessions[chat_id] = user_api_client

    def _parse_json(self, text):
        api_server_pattern = r'api_server:\s*(\S+)'
        access_key_pattern = r'"access_key"\s*=\s*"(\S+)"'
        secret_key_pattern = r'"secret_key"\s*=\s*"(\S+)"'

        api_server = re.search(api_server_pattern, text)
        access_key = re.search(access_key_pattern, text)
        secret_key = re.search(secret_key_pattern, text)

        if api_server is None or \
                access_key is None or \
                secret_key is None:
            return None, None, None
        
        return api_server.group(1), access_key.group(1), secret_key.group(1) 

    def get_user_creds(self, message):
        chat_id = message.chat.id

        api_server, access_key, secret_key = self._parse_json(message.text)

        if api_server is None:
            self.bot.send_message(chat_id, "Incorrect credentials format!\n"
                                  "Please go to https://app.clear.ml/settings/workspace-configuration, "
                                  "select \"Create new credentials\" then copy and send credentials here",
                                  disable_web_page_preview=True)
            self.bot.register_next_step_handler(message, self.get_user_creds)
            return
        
        self.database.insert_user(
            chat_id,
            message.chat.username,
            api_server,
            access_key,
            secret_key
        )

        self.bot.send_message(chat_id, "Registration successful! Your credentials have been saved.")

    def send_updates_to_users(self):
        for chat_id in self.user_sessions.copy():
            user_api_client = self.user_sessions[chat_id]
            experiment_infos, train_images, val_images = user_api_client.update_running_experiments(chat_id)

            for experiment_info, train_image, val_image in zip(experiment_infos, train_images, val_images):
                experiment_name = experiment_info["experiment_name"]
                last_iteration = experiment_info["last_iteration"]
                message_text = experiment_info["message"]
                experiment_info = self.database.get_experiment_info(chat_id, experiment_name)

                if experiment_info is None:
                    self.database.store_experiment_info(chat_id, experiment_name, last_iteration, -1, -1, -1)
                    experiment_info = self.database.get_experiment_info(chat_id, experiment_name)

                _, _, last_iteration_db, text_msg_id, train_msg_id, val_msg_id = experiment_info
                if last_iteration == last_iteration_db:
                    continue
                
                if text_msg_id != -1:
                    _, _, _, text_msg_id, train_msg_id, val_msg_id = experiment_info
                    sent_message = self.bot.edit_message_text(message_text, chat_id, text_msg_id)
                    self.database.store_experiment_info(chat_id, experiment_name, last_iteration, 
                                                        sent_message.message_id, train_msg_id, val_msg_id)
                else:
                    sent_message = self.bot.send_message(chat_id, message_text)
                    self.database.store_experiment_info(chat_id, experiment_name, last_iteration, 
                                                        sent_message.message_id, -1, -1)

                if train_image is not None:
                    self.send_or_update_photo(chat_id, experiment_name, last_iteration, train_image, "train")
                if val_image is not None:
                    self.send_or_update_photo(chat_id, experiment_name, last_iteration, val_image, "val")

    def send_or_update_photo(self, chat_id, experiment_name, last_iteration, image, section):
        if section not in ["train", "val"]:
            print(f'Section {section} not in ["train", "val"]')
            return
        experiment_info = self.database.get_experiment_info(chat_id, experiment_name)

        _, _, _, text_msg_id, train_msg_id, val_msg_id = experiment_info
        if section == "train":
            message_id = train_msg_id
        elif section == "val":
            message_id = val_msg_id

        if message_id != -1:
            sent_message = self.bot.edit_message_media(chat_id=chat_id, message_id=message_id, 
                                                       media=telebot.types.InputMediaPhoto(image))
        else:
            sent_message = self.bot.send_photo(chat_id, image)

        if section == "train":
            train_msg_id = sent_message.message_id
        elif section == "val":
            val_msg_id = sent_message.message_id

        self.database.store_experiment_info(chat_id, experiment_name, last_iteration, 
                                            text_msg_id, train_msg_id, val_msg_id)

    def start_bot(self):
        self.bot.polling()
