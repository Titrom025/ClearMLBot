import io
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

    def update_running_experiments(self):
        experiment_infos = []
        train_images = []
        val_images = []
        running_task_list = self.tasks.get_all(status=[Task.TaskStatusEnum.in_progress.value])
        if not len(running_task_list):
            return experiment_infos, train_images, val_images

        for running_task in running_task_list:
            if self.running_tasks.get(running_task.name, -1) == running_task.last_iteration:
                continue

            self.running_tasks[running_task.name] = running_task.last_iteration

            message_text = f'Name: {running_task.name}, Iteration: {running_task.last_iteration}\n'

            last_task_metrics = running_task.last_metrics

            all_metrics = []
            for metric_info in ClearML_API_Wrapped._extract_metrics(last_task_metrics):
                if metric_info["section"] in ["train", "val"]:
                    all_metrics.append((
                        running_task.name,
                        metric_info["section"],
                        metric_info["metric"],
                        running_task.last_iteration,
                        metric_info["value"]
                    ))

            for metric_data in all_metrics:
                self.db.insert_metric(*metric_data)

            train_image, val_image = self.plot_metrics_for_experiment(running_task.name)

            experiment_infos.append({
                "experiment_name": running_task.name,
                "last_iteration": running_task.last_iteration,
                "message": message_text
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

    def plot_metrics_for_experiment(self, experiment_name):
        train_metrics = self.db.get_metrics_by_section(experiment_name, "train")
        val_metrics = self.db.get_metrics_by_section(experiment_name, "val")

        all_metrics = train_metrics + val_metrics
        unique_metrics = set(metric[2] for metric in all_metrics)

        num_unique_metrics = len(unique_metrics)
        color_palette = plt.cm.get_cmap('tab10', num_unique_metrics)

        train_image = None
        if train_metrics:
            train_iterations = [metric[3] for metric in train_metrics]
            train_values = [metric[4] for metric in train_metrics]
            train_metric_names = [metric[2] for metric in train_metrics]
            unique_train_metric_names = set(train_metric_names)

            legend_labels = []
            plt.figure(figsize=(8, 6))

            for i, metric_name in enumerate(unique_train_metric_names):
                mask = [name == metric_name for name in train_metric_names]
                plt.plot(
                    [train_iterations[j] for j, m in enumerate(mask) if m],
                    [train_values[j] for j, m in enumerate(mask) if m],
                    marker='o',
                    linestyle='-',
                    label=f'{metric_name}',
                    color=color_palette(i)
                )
                legend_labels.append(f'{metric_name}') 

            plt.title(f"Train Metrics for {experiment_name}")
            plt.xlabel('Iterations')
            plt.ylabel('Values')
            plt.xticks(np.arange(min(train_values), max(train_values)+1, 1.0))
            plt.yscale('log')
            plt.legend(labels=legend_labels, loc='upper center', 
                       bbox_to_anchor=(0.5, -0.15), shadow=True, ncol=5)
            plt.tight_layout()
            img = io.BytesIO()
            plt.savefig(img, format='png')
            img.seek(0)
            train_image = img
            plt.close()

        val_image = None
        if val_metrics:
            val_iterations = [metric[3] for metric in val_metrics]
            val_values = [metric[4] for metric in val_metrics]
            val_metric_names = [metric[2] for metric in val_metrics]
            unizue_val_metric_names = set(val_metric_names)

            legend_labels = []
            plt.figure(figsize=(8, 6))

            for i, metric_name in enumerate(unizue_val_metric_names):
                mask = [name == metric_name for name in val_metric_names]
                plt.plot(
                    [val_iterations[j] for j, m in enumerate(mask) if m],
                    [val_values[j] for j, m in enumerate(mask) if m],
                    marker='o',
                    linestyle='-',
                    label=f'{metric_name}',
                    color=color_palette(i)
                )
                legend_labels.append(f'{metric_name}') 

            plt.title(f"Validation Metrics for {experiment_name}")
            plt.xlabel('Iterations')
            plt.ylabel('Values')
            plt.yscale('log')
            plt.legend(labels=legend_labels, loc='upper center', 
                       bbox_to_anchor=(0.5, -0.15), shadow=True, ncol=5)
            plt.tight_layout()
            img = io.BytesIO()
            plt.savefig(img, format='png')
            img.seek(0)
            val_image = img
            plt.close()

        return train_image, val_image
