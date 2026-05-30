import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "director_engine.log")

def get_logger(module_name: str) -> logging.Logger:
    """
    Returns a configured logger for the given module.
    Writes DEBUG and above to a rotating file.
    Writes INFO and above to the console.
    """
    logger = logging.getLogger(module_name)
    
    # If the logger already has handlers, return it to avoid duplicate logs
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.DEBUG) 
    
    # Formatter mapping: [Timestamp] | [Level] | [Module Name] | Message
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    # 1. File Handler (Max 5MB per file, keeps last 3 logs)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # 2. Standard Console Handler (Optional, useful if running via terminal)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger