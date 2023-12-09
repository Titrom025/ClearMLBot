
# ClearML Telegram Bot Interface

The ClearML Telegram bot provides an easy and convenient way to monitor ongoing experiments and view training/validation metrics directly from your Telegram messenger.

## Why use the ClearML Telegram Bot?

While ClearML does not currently have a mobile version of its website, monitoring experiments on mobile devices becomes difficult due to the interface not being adapted for smaller screens.

However, the ClearML Telegram bot interface offers a solution by making experiment management easier. It puts important information and updates right at your fingertips, allowing you to stay updated on the progress of your experiments and performance metrics without leaving the Telegram app.

## Features:

- **Experiment Monitoring**: Keep track of your running experiments in real-time.
- **Metrics Viewing**: Access training and validation metrics effortlessly.
- **Convenient Interface**: Receive updates and information right within your Telegram app.

## How to Use:

1. **Add the ClearML Telegram Bot**:
   - Open your Telegram messenger and search for `@clearml_bot`.
   - Click on it to open the bot profile.

2. **Link ClearML Account**:
   - Type `/register` in the chat with the ClearML bot.
   - Visit [ClearML settings](https://app.clear.ml/settings/workspace-configuration).
   - Select "Create new credentials" to generate API credentials.
   - Copy the generated credentials and send them to the ClearML bot.

3. **Subscription**:
   - To initiate updates on your experiments, enter `/subscribe`. Going forward, you'll receive notifications about all ongoing experiments. The bot will initially send images with train and validation metrics just once, subsequently updating existing messages to prevent excessive notifications.
 
4. **Cancel your subscription**:
   - Type `/unsubscribe` to stop receiving information and updates about your experiments.
  
5. **Running experiments**
   - Type `/experiments` to manually get the list of running experiments.

## Developing

To configure your personalized ClearML bot, follow these steps:

1. Clone the repository.
2. Obtain a Telegram token from Botfather by following these instructions:
   - Open Telegram and search for `@BotFather`.
   - Follow the prompts to create a new bot and receive the token.
   - Save the token for the next step.
3. Open the file named `config.json` at the root of the repository. Replace `"Paste your token here"` with your actual Telegram token: 
   
   ```
   {
       "TG_TOKEN": "Paste your token here"
   }
   ```
4. Execute `docker-compose up` to start the bot.

## Demo

<p align="center">
  <img width="320" height="570" src="Demo.gif">
</p>