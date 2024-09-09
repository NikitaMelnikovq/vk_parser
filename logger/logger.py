import logging
import sys
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Функция для создания уникальных файлов логов на каждый запуск
def create_log_files(script_name):
    current_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Папка для логов (если её нет, создаём)
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Пути к файлам логов с добавлением названия файла скрипта
    console_log_file = os.path.join(log_dir, f"{script_name}_console_log_{current_time}.log")
    error_log_file = os.path.join(log_dir, f"{script_name}_error_log_{current_time}.log")
    
    return console_log_file, error_log_file

# Функция для настройки логгера
def setup_logger():
    # Получаем имя текущего файла скрипта без расширения
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    
    # Создаём уникальные файлы логов для текущего запуска
    console_log_file, error_log_file = create_log_files(script_name)
    
    # Создаём логгер
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # Форматирование сообщений
    console_formatter = logging.Formatter(
        'CONSOLE - %(asctime)s\n\t%(message)s\n'
        + '-' * 50 + '\n', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    error_formatter = logging.Formatter(
        'ERROR - %(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Логгер для вывода консоли (INFO)
    console_handler = RotatingFileHandler(console_log_file, maxBytes=5*1024*1024, backupCount=5)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Логгер для ошибок и предупреждений (WARNING и ERROR)
    error_handler = RotatingFileHandler(error_log_file, maxBytes=5*1024*1024, backupCount=5)
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(error_formatter)
    
    # Вывод ошибок и предупреждений в stderr
    console_error_handler = logging.StreamHandler(sys.stderr)
    console_error_handler.setLevel(logging.WARNING)
    console_error_handler.setFormatter(error_formatter)
    
    # Добавляем обработчики к логгеру
    logger.addHandler(console_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_error_handler)

    return logger

# Инициализируем логгер
logger = setup_logger()

# Пример использования логгера
if __name__ == "__main__":
    logger.info("This is an info message to console log.")
    logger.warning("This is a warning message to error log.")
    logger.error("This is an error message to error log.")
