import logging
import os
from datetime import datetime
from config import SYSTEM_CONFIG

class Logger:
    """Centralized logging for the Computer Use AI system"""
    
    def __init__(self, name="computer_use_ai"):
        self.logger = logging.getLogger(name)
        self.setup_logger()
    
    def setup_logger(self):
        """Setup logging configuration"""
        # Create logs directory if it doesn't exist
        if not os.path.exists("logs"):
            os.makedirs("logs")
        
        # Set logging level
        level = getattr(logging, SYSTEM_CONFIG["log_level"], logging.INFO)
        self.logger.setLevel(level)
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )
        
        # Create file handler
        log_filename = f"logs/computer_use_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"Logger initialized. Log file: {log_filename}")
    
    def log_step(self, step_number, action_data, result):
        """Log a complete step with action and result"""
        self.logger.info(f"=== STEP {step_number} ===")
        self.logger.info(f"Action: {action_data}")
        self.logger.info(f"Result: {result}")
        self.logger.info("=" * 50)
    
    def log_action(self, action_type, target, success, message=None):
        """Log an individual action"""
        status = "SUCCESS" if success else "FAILED"
        log_msg = f"Action {action_type} on '{target}': {status}"
        if message:
            log_msg += f" - {message}"
        
        if success:
            self.logger.info(log_msg)
        else:
            self.logger.error(log_msg)
    
    def log_llm_request(self, prompt_length, response_length, model):
        """Log LLM API request details"""
        self.logger.debug(f"LLM Request - Model: {model}, Prompt: {prompt_length} chars, Response: {response_length} chars")
    
    def log_html_processing(self, original_length, processed_length):
        """Log HTML processing details"""
        reduction = original_length - processed_length
        percentage = (reduction / original_length * 100) if original_length > 0 else 0
        self.logger.debug(f"HTML Processing - Original: {original_length} chars, Processed: {processed_length} chars, Reduced by {percentage:.1f}%")
    
    def log_history_summary(self, total_steps):
        """Log summary of action history"""
        self.logger.debug(f"Action history now contains {total_steps} steps")
    
    def log_history_context(self, context):
        """Log the history context being sent to LLM"""
        self.logger.debug(f"History context: {context}")
    
    def log_error(self, error_msg, exception=None):
        """Log errors with optional exception details"""
        self.logger.error(f"Error: {error_msg}")
        if exception:
            self.logger.exception("Exception details:", exc_info=exception)
    
    def log_session_start(self, task, url):
        """Log the start of a new session"""
        self.logger.info("=" * 60)
        self.logger.info("NEW SESSION STARTED")
        self.logger.info(f"Task: {task}")
        self.logger.info(f"Starting URL: {url}")
        self.logger.info("=" * 60)
    
    def log_session_end(self, total_steps, success):
        """Log the end of a session"""
        status = "COMPLETED SUCCESSFULLY" if success else "ENDED WITH ERRORS"
        self.logger.info("=" * 60)
        self.logger.info(f"SESSION {status}")
        self.logger.info(f"Total steps executed: {total_steps}")
        self.logger.info("=" * 60)
    
    # Convenience methods for different log levels
    def info(self, message):
        self.logger.info(message)
    
    def debug(self, message):
        self.logger.debug(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def critical(self, message):
        self.logger.critical(message)