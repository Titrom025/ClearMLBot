from clearml import Task
from clearml.backend_api.session import Session
from clearml.backend_api.session.client import APIClient


class ClearML_API_Wrapped(APIClient):
    def __init__(self, host, api_key, secret_key):
        session = Session(
            host=host,
            api_key=api_key,
            secret_key=secret_key
        )

        self.client = super(ClearML_API_Wrapped, self).__init__(
            session=session
        )
        
        self.running_tasks = {}

    def update_running_experiments(self):
        running_task_list = self.tasks.get_all(status=[Task.TaskStatusEnum.in_progress.value])
        if not len(running_task_list):
            return None
        message_text = f"Running experiment count: {len(running_task_list)}\n"
        skip_message_sending = True
        for running_task in running_task_list:
            if self.running_tasks.get(running_task.name, -1) == running_task.last_iteration:
                continue

            skip_message_sending = False
            self.running_tasks[running_task.name] = running_task.last_iteration

            message_text += f'Name: {running_task.name}, Iteration: {running_task.last_iteration}\n'

            last_task_metrics = running_task.last_metrics
            for metric_info in ClearML_API_Wrapped._extract_metrics(last_task_metrics):
                metric_str =  f'  - {metric_info["section"]}/{metric_info["metric"]}: Value: {metric_info["value"]}\n'
                if metric_info["section"] == "train":
                    metric_str += f'    Min value: {metric_info["min_value"]}, Min iter: {metric_info["min_value_iteration"]}\n'
                elif metric_info["section"] == "val":
                    metric_str += f'    Max value: {metric_info["max_value"]}, Max iter: {metric_info["max_value_iteration"]}\n'
                message_text += metric_str
            message_text += '\n'

        if skip_message_sending:
            return None
        return message_text
    
    @staticmethod
    def _extract_metrics(data):
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
                metrics.extend(ClearML_API_Wrapped._extract_metrics(item))

        return metrics
