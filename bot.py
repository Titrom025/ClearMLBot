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
                "/register - Add ClearML credentials\n"
                "/subscribe - Subscribe ClearML updates\n"
                "/unsubscribe - Stop receiving ClearML updates\n"
                "/experiments - Get info about running experiments\n"
                "/help - Print help message\n"
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

        @self.bot.message_handler(commands=['subscribe'])
        def subscribe_command(message):
            chat_id = message.chat.id
            if chat_id in self.user_sessions:
                send_and_log(f'User {message.chat.username} was already subscribed!', chat_id)
                return
            if self.subscribe_user(chat_id):
                send_and_log(f'User {message.chat.username} subscribed to updates!', chat_id)

        @self.bot.message_handler(commands=['unsubscribe'])
        def unsubscribe_command(message):
            chat_id = message.chat.id
            if chat_id not in self.user_sessions:
                send_and_log(f'User "{message.chat.username}" wasn\'t subscribed!', chat_id)
                return
            self.user_sessions.pop(chat_id)
            send_and_log(f'User "{message.chat.username}" unsubscribed from updates!', chat_id)

        @self.bot.message_handler(commands=['experiments'])
        def get_running_experiments(message):
            chat_id = message.chat.id
            if chat_id not in self.user_sessions:
                if not self.subscribe_user(chat_id):
                    return
            
            user_api_client = self.user_sessions[chat_id]
            running_experiments = user_api_client.get_running_experiments()
            
            message = f'Running experiment count: {len(running_experiments)}'
            for experiment in running_experiments:
                message += '\n\n'
                message += f'Name: {experiment["name"]}\n'
                message += f'  - Id: {experiment["id"]}\n'
                message += f'  - Epoch: {experiment["iteration"]}\n'
                message += f'  - Duration: {experiment["duration"]}'
            
            self.bot.send_message(chat_id, message)

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
            return False

        _, _, host, api_key, secret_key = user_from_db

        if chat_id in self.user_sessions:
            return True

        user_api_client = ClearML_API_Wrapped(
            host,
            api_key,
            secret_key,
            self.database
        )
        self.user_sessions[chat_id] = user_api_client
        return True

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

        try:
            self.bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass
        self.bot.send_message(chat_id, "Registration successful! Your credentials have been saved.")

    def send_updates_to_users(self):
        for chat_id in self.user_sessions.copy():
            user_api_client = self.user_sessions[chat_id]
            experiment_infos, train_images, val_images = user_api_client.update_running_experiments(chat_id)

            for experiment_info, train_image, val_image in zip(experiment_infos, train_images, val_images):
                experiment_id = experiment_info["id"]
                experiment_name = experiment_info["name"]
                last_iteration = experiment_info["iteration"]
                duration_str = experiment_info["duration"]

                message =  f'Name: {experiment_name}\n'
                message += f'  - Id: {experiment_id}\n'
                message += f'  - Epoch: {last_iteration}\n'
                message += f'  - Duration: {duration_str}'

                experiment_info = self.database.get_experiment_info(chat_id, experiment_id)

                if experiment_info is None:
                    self.database.store_experiment_info(chat_id, experiment_id, experiment_name, last_iteration, -1, -1, -1)
                    experiment_info = self.database.get_experiment_info(chat_id, experiment_id)

                _, _, _, last_iteration_db, text_msg_id, train_msg_id, val_msg_id = experiment_info
                if last_iteration == last_iteration_db:
                    continue
                
                if text_msg_id != -1:
                    _, _, _, _, text_msg_id, train_msg_id, val_msg_id = experiment_info
                    try:
                        sent_message = self.bot.edit_message_text(message, chat_id, text_msg_id)
                        self.database.store_experiment_info(chat_id, experiment_id, 
                                                            experiment_name, last_iteration, 
                                                            sent_message.message_id, train_msg_id, val_msg_id)
                    except Exception:
                        pass
                else:
                    sent_message = self.bot.send_message(chat_id, message)
                    self.database.store_experiment_info(chat_id, experiment_id, 
                                                        experiment_name, last_iteration, 
                                                        sent_message.message_id, -1, -1)

                if train_image is not None:
                    self.send_or_update_photo(chat_id, experiment_id, experiment_name, 
                                              last_iteration, train_image, "train")
                if val_image is not None:
                    self.send_or_update_photo(chat_id, experiment_id, experiment_name, 
                                              last_iteration, val_image, "val")

    def send_or_update_photo(self, chat_id, experiment_id, experiment_name, last_iteration, image, section):
        if section not in ["train", "val"]:
            print(f'Section {section} not in ["train", "val"]')
            return
        experiment_info = self.database.get_experiment_info(chat_id, experiment_id)

        _, _, _, _, text_msg_id, train_msg_id, val_msg_id = experiment_info
        if section == "train":
            message_id = train_msg_id
        elif section == "val":
            message_id = val_msg_id

        if message_id != -1:
            try:
                sent_message = self.bot.edit_message_media(chat_id=chat_id, message_id=message_id, 
                                                       media=telebot.types.InputMediaPhoto(image))
            except Exception:
                return
        else:
            sent_message = self.bot.send_photo(chat_id, image)

        if section == "train":
            train_msg_id = sent_message.message_id
        elif section == "val":
            val_msg_id = sent_message.message_id

        self.database.store_experiment_info(chat_id, experiment_id,
                                            experiment_name, last_iteration, 
                                            text_msg_id, train_msg_id, val_msg_id)

    def start_bot(self):
        self.bot.polling()
