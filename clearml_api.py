import io
from datetime import datetime
from math import log

import numpy as np
from clearml import Task
from clearml.backend_api.session import Session
from clearml.backend_api.session.client import APIClient
from matplotlib import pyplot as plt


class ClearML_API_Wrapped(APIClient):
    def __init__(self, host, api_key, secret_key, database):
        self.db = database
        session = Session(
            host=host,
            api_key=api_key,
            secret_key=secret_key
        )

        self.client = super(ClearML_API_Wrapped, self).__init__(
            session=session
        )
        
        self.running_tasks = {}

    @staticmethod
    def _get_duration(running_task_dict):
        tz = running_task_dict["started"].tzinfo
        datetime_now = datetime.now(tz=tz)
        experiment_duration = datetime_now - running_task_dict["started"]
        days = experiment_duration.days
        hours = experiment_duration.seconds // 3600
        minutes = (experiment_duration.seconds // 60) % 60

        if days > 0:
            duration_str = f'{days} days {hours}H:{minutes}m'
        else:
            duration_str = f'{hours}H:{minutes}m'

        return duration_str

    def get_running_experiments(self):
        running_task_list = self.tasks.get_all(status=[Task.TaskStatusEnum.in_progress.value])
        if not len(running_task_list):
            return []

        running_experiments = []
        for running_task in running_task_list:
            running_task_dict = running_task.to_dict()
            id = running_task_dict["id"]
            name = running_task_dict["name"]
            iteration = running_task_dict["last_iteration"]

            duration_str = ClearML_API_Wrapped._get_duration(running_task_dict)
            
            running_experiments.append({
                "id": id,
                "name": name,
                "iteration": iteration,
                "duration": duration_str
            })

        return running_experiments

    def update_running_experiments(self, chat_id):
        experiment_infos = []
        train_images = []
        val_images = []
        running_task_list = self.tasks.get_all(status=[Task.TaskStatusEnum.in_progress.value])
        if not len(running_task_list):
            return experiment_infos, train_images, val_images

        for running_task in running_task_list:
            running_task_dict = running_task.to_dict()
            experiment_id = running_task_dict["id"]
            experiment_name = running_task_dict["name"]
            last_iteration = running_task_dict["last_iteration"]
    
            if self.running_tasks.get(experiment_id, -1) == last_iteration:
                continue

            self.running_tasks[experiment_id] = last_iteration
            last_task_metrics = running_task.last_metrics

            all_metrics = []
            for metric_info in ClearML_API_Wrapped._extract_metrics(last_task_metrics):
                if metric_info["section"] in ["train", "val"]:
                    metric_iteration = last_iteration
                    if metric_info["metric"] != "lr":
                        metric_iteration -= 1
                    all_metrics.append((
                        chat_id,
                        experiment_id,
                        metric_info["section"],
                        metric_info["metric"],
                        metric_iteration,
                        metric_info["value"]
                    ))

            for metric_data in all_metrics:
                self.db.insert_metric(*metric_data)

            train_image, val_image = self.plot_metrics_for_experiment(experiment_id, experiment_name)

            duration_str = ClearML_API_Wrapped._get_duration(running_task_dict)

            experiment_infos.append({
                "id": experiment_id,
                "name": experiment_name,
                "iteration": last_iteration,
                "duration": duration_str
            })

            train_images.append(train_image)
            val_images.append(val_image)

        return experiment_infos, train_images, val_images
    
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

    @staticmethod
    def _get_plot(metrics, metric_type, experiment_name, color_palette):
        metric_names = [metric[3] for metric in metrics]
        iterations = [metric[4] for metric in metrics]
        values = [metric[5] for metric in metrics]
        unique_metric_names = set(metric_names)

        legend_labels = []
        plt.figure(figsize=(10, 6))

        for i, metric_name in enumerate(unique_metric_names):
            mask = [name == metric_name for name in metric_names]
            metric_iterations = [iterations[j] for j, m in enumerate(mask) if m]
            metric_values = [values[j] for j, m in enumerate(mask) if m]
            plt.plot(
                metric_iterations,
                metric_values,
                marker='o',
                linestyle='-',
                label=f'{metric_name}',
                color=color_palette(i)
            )
            legend_labels.append(f'{metric_name}: {round(metric_values[-1], 3)}') 

        plt.title(f"{metric_type} metrics for {experiment_name}")
        plt.xlabel('Iterations')
        plt.ylabel('Values')
        if max(iterations) - min(iterations) > 50:
            iter_step = 2
        else:
            iter_step = 1
        plt.xticks(np.arange(min(iterations), max(iterations) + 1, iter_step))
        plt.yticks(np.arange(0, 1.01, 0.1))
        plt.yticks(np.arange(0, 1.0, 0.05), minor=True)
        plt.grid(axis='y', which='both')
        ax = plt.gca()
        ax.set_ylim([-0.05, 1.05])
        plt.legend(labels=legend_labels, loc='upper center', 
                    bbox_to_anchor=(0.5, -0.15), shadow=True, ncol=4)
        plt.tight_layout()
        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plt.close()
        return img
    
    def plot_metrics_for_experiment(self, experiment_id, experiment_name):
        train_metrics = self.db.get_metrics_by_section(experiment_id, "train")
        val_metrics = self.db.get_metrics_by_section(experiment_id, "val")

        all_metrics = train_metrics + val_metrics
        unique_metrics = set(metric[3] for metric in all_metrics)

        num_unique_metrics = len(unique_metrics)
        color_palette = plt.cm.get_cmap('tab10', num_unique_metrics)

        train_image = None
        if train_metrics:
            train_image = ClearML_API_Wrapped._get_plot(
                train_metrics, "train", 
                experiment_name, color_palette
            )

        val_image = None
        if val_metrics:
            val_image = ClearML_API_Wrapped._get_plot(
                val_metrics, "Val", 
                experiment_name, color_palette
            )

        return train_image, val_image
