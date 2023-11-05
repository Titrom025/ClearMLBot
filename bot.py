import time

import telebot

from typing import Any
from clearml import Task
from clearml.backend_api.session.client import APIClient


telegram_token = 'TG_BOT_TOKEN'
bot = telebot.TeleBot(telegram_token)
client = APIClient()

task_db = {}

def extract_metrics(data):
    metrics = [] 

    for item in data.values():
        if 'metric' in item:
            if ":monitor:" in item['metric']:
                continue
            metrics.append({
                'section': item['metric'], 
                'metric': item['variant'],
                'value': item['value'],
                'min_value': item['min_value'],
                'max_value': item['max_value'],
                'min_value_iteration': item['min_value_iteration'],
                'max_value_iteration': item['max_value_iteration']
            })
        else:
            metrics.extend(extract_metrics(item))

    return metrics


@bot.message_handler(commands=['running_experiments'])
def get_running_experiments(message):
    chat_id = message.chat.id

    running_task_list = client.tasks.get_all(status=[Task.TaskStatusEnum.in_progress.value])

    message_text = f"Running experiment count: {len(running_task_list)}\n"
    skip_message_sending = True
    for running_task in running_task_list:
        if task_db.get(running_task.name, -1) == running_task.last_iteration:
            continue

        skip_message_sending = False
        task_db[running_task.name] = running_task.last_iteration

        message_text += f'Name: {running_task.name}, Iteration: {running_task.last_iteration}\n'

        last_task_metrics = running_task.last_metrics
        for metric_info in extract_metrics(last_task_metrics):
            metric_str =  f'  - {metric_info["section"]}/{metric_info["metric"]}: Value: {metric_info["value"]}\n'
            if metric_info["section"] == "train":
                metric_str += f'    Min value: {metric_info["min_value"]}, Min iter: {metric_info["min_value_iteration"]}\n'
            elif metric_info["section"] == "val":
                metric_str += f'    Max value: {metric_info["max_value"]}, Max iter: {metric_info["max_value_iteration"]}\n'
            message_text += metric_str
        message_text += '\n'

    if not skip_message_sending:
        print(message_text)
        bot.send_message(chat_id, message_text)


class DummyMessage():
    def __getattribute__(self, __name: str) -> Any:
        if __name == "chat":
            return DummyMessage()
        elif __name == "id": 
            return 215956314

if __name__ == '__main__':
    message = DummyMessage()
    while True:
        get_running_experiments(message)
        time.sleep(30)
