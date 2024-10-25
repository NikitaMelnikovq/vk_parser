from locust import HttpUser, task, between
import json
import random

class TelegramBotUser(HttpUser):
    wait_time = between(1, 3)  # Интервал ожидания между запросами для эмуляции реальных пользователей

    user_id = random.randint(100000, 999999)  # Идентификатор пользователя для тестов
    bot_token = "6617538418:AAGt-AoWc8d2P_bBYLouMJXbftFuGdiYHus"  # Ваш API-ключ для бота

    @task
    def start_command(self):
        # Симулируем команду "/start", отправляемую через Telegram API
        payload = {
            "chat_id": self.user_id,
            "text": "/start"
        }
        headers = {'Content-Type': 'application/json'}
        self.client.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", 
                         data=json.dumps(payload), headers=headers)

    @task
    def authorize_command(self):
        # Симулируем команду "/authorize"
        payload = {
            "chat_id": self.user_id,
            "text": "/authorize"
        }
        headers = {'Content-Type': 'application/json'}
        self.client.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", 
                         data=json.dumps(payload), headers=headers)

    @task
    def add_group_command(self):
        # Симулируем команду "/add_group"
        payload = {
            "chat_id": self.user_id,
            "text": "/add_group"
        }
        headers = {'Content-Type': 'application/json'}
        self.client.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", 
                         data=json.dumps(payload), headers=headers)

    @task
    def remove_group_command(self):
        # Симулируем команду "/remove_group"
        payload = {
            "chat_id": self.user_id,
            "text": "/remove_group"
        }
        headers = {'Content-Type': 'application/json'}
        self.client.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", 
                         data=json.dumps(payload), headers=headers)

    @task
    def updates_toggle_command(self):
        # Симулируем команды "/updates_on" и "/updates_off"
        command = random.choice(["/updates_on", "/updates_off"])
        payload = {
            "chat_id": self.user_id,
            "text": command
        }
        headers = {'Content-Type': 'application/json'}
        self.client.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage", 
                         data=json.dumps(payload), headers=headers)
