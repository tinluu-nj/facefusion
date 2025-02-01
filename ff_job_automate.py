import os
import sys
import subprocess
import shutil
import logging
import json
from time import sleep
from threading import Thread
from watchdog.observers import Observer
import argparse

from facefusion.jobs import (
    job_helper,
    job_manager
)
from facefusion import core

from FileProcessorHandler import (
    FileProcessorHandler,
    load_processed_files,
    load_queue,
    poll_for_new_files,
    save_processed_files,
    save_queue
)

# Global variables for directory paths
JOB_DIRECTORY = "./.jobs/"
BACKUP_DIRECTORY = "/home/tinluu/Record/Backup/"
PHOTO_DIRECTORY = "/home/tinluu/Nextcloud/Record/Photo/"
# PHOTO_DIRECTORY = "/home/tinluu/Vault/Downloads/"
CONFIG_FILE = "ESTHERA-conf.json"
LOG_FILE = "ff_job_automate.log"

# Configure the logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),  # Log to a file
        logging.StreamHandler()  # Also log to console
    ]
)

# Create a logger instance
logger = logging.getLogger("ff_job_automate")

# Load configuration from file
with open(CONFIG_FILE, 'r') as file:
    generic_arg = json.load(file)

def process_monitoring_directory(target_path, polling: bool) -> None:
    """
    Monitor the target directory for new files and process them.
    """
    processing_queue = load_queue()
    processed_files = load_processed_files()

    # Add existing files to the queue
    for root, _, files in os.walk(target_path):
        for file in files:
            file_path = os.path.join(root, file)
            if file_path not in processed_files:
                processing_queue.append(file_path)

    # Save initial queue
    save_queue(processing_queue)
    logger.debug(f"Monitoring {target_path}")

    if polling:
        # Start the polling thread if polling is enabled
        polling_thread = Thread(
            target=poll_for_new_files,
            args=(target_path, processing_queue, processed_files),
        )
        polling_thread.daemon = True  # Allow script to exit even if polling thread is running
        polling_thread.start()

    # Process the directory
    process_directory(target_path, processing_queue, processed_files)

def process_directory(target_path, processing_queue, processed_files)  -> None:
    """
    Process the files in the target directory using the event handler and observer.
    """
    # Set up file event handler and observer
    event_handler = FileProcessorHandler(processing_queue, processed_files)
    observer = Observer()
    observer.schedule(event_handler, path=target_path, recursive=True)
    observer.start()

    try:
        while True:
            # If there are files in the queue, process them
            if processing_queue:
                process_file_queue(processing_queue, processed_files)
            sleep(1)  # Sleep for a short duration before checking again
    except KeyboardInterrupt:
        # Stop the observer on keyboard interrupt
        observer.stop()
    observer.join()

def process_file_queue(processing_queue, processed_files) -> None:
    """
    Process files from the queue and submit jobs.
    """
    # Suggest a job ID
    job_id = job_helper.suggest_job_id("ESTHERA")
    job_manager.create_job(job_id)

    # Process the first file in the queue
    file_path = processing_queue.pop(0)
    if str(file_path).endswith(".mp4"):
        logger.info(f"Video file: {file_path}")
    elif file_path not in processed_files and os.path.exists(file_path) and core.is_image(file_path):
        logger.info(f"Processing: {file_path}")
        directory, filename = os.path.split(file_path)
        name, ext = os.path.splitext(filename)
        output_path = os.path.join(directory, f"{name}-ff{ext}")

        # Set target and output paths in generic arguments
        generic_arg["target_path"] = file_path
        generic_arg["output_path"] = output_path

        # Add a step to the job manager
        if job_manager.add_step(job_id, generic_arg):
            processed_files.add(file_path)
            processed_files.add(output_path)
        else:
            logger.warning(f"Failed to add_step for: {file_path}")

        # Submit the job
        job_manager.submit_job(job_id)

        # Run job commands
        run_job_commands(file_path, processed_files)
    else:
        logger.info(f"Already processed or not existed: {file_path}")

    # Save the updated queue
    save_queue(processing_queue)

def run_job_commands(file_path: str, processed_files: str) -> None:
    """
    Run the facefusion job-run-all command and handle processed files.
    """
    # Command to execute facefusion
    commands = [sys.executable, 'facefusion.py', 'job-run-all', "--execution-provider", "cuda", "cpu"]
    if subprocess.run(commands).returncode == 0:
        # Save processed files if the job ran successfully
        save_processed_files(processed_files)
        try:
            # Move the processed file to backup directory
            shutil.move(file_path, BACKUP_DIRECTORY)
        except Exception as e:
            logger.warning(f"Failed to move file: {e}")

def main() -> None:
    """
    Main function to initialize jobs and start the directory monitoring process.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Automate facefusion jobs")
    parser.add_argument("--polling", action="store_true", help="Enable polling for new files")
    args = parser.parse_args()

    # Clear and initialize the job directory
    job_manager.clear_jobs(JOB_DIRECTORY)
    job_manager.init_jobs(JOB_DIRECTORY)

    # Process the monitoring directory with or without polling
    process_monitoring_directory(PHOTO_DIRECTORY, args.polling)

if __name__ == '__main__':
    main()
