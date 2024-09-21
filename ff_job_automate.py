from facefusion.jobs import job_helper, job_list, job_manager, job_runner, job_store
from facefusion import core

from FileProcessorHandler import (
    FileProcessorHandler,
    load_processed_files,
    load_queue,
    poll_for_new_files,
    save_processed_files,
    save_queue,
)

from watchdog.observers import Observer

from time import sleep
import os, sys, subprocess, shutil
import logging
import json

# Configure the logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ff_job_automate.log"),  # Log to a file named script.log
        logging.StreamHandler()  # Also log to console
    ]
)

# Create a logger instance
logger = logging.getLogger("ff_job_automate")

with open('ESTHERA-conf.json', 'r') as file:
    generic_arg = json.load(file)  # Load the file's content into a dictionary

def process_monitoring_directory(target_path: str):
    processing_queue = load_queue()
    processed_files = load_processed_files()

        # Add existing files to the queue
    for root, _, files in os.walk(target_path):
        for file in files:
            file_path = os.path.join(root, file)
            if file_path not in processed_files:
                processing_queue.append(file_path)

    save_queue(processing_queue)  # Save initial queue

    logger.debug("Monitoring " + target_path)

    POLLING = False
    if POLLING:
        # Start the polling thread
        from threading import Thread

        polling_thread = Thread(
                target=poll_for_new_files,
                args=(
                    target_path,
                    processing_queue,
                    processed_files,
                ),
            )
        polling_thread.daemon = (
                True  # Allow the script to exit even if the polling thread is running
            )
        polling_thread.start()
    else:
        pass

    process_directory(target_path, processing_queue, processed_files)

def process_directory(target_path,  processing_queue, processed_files):
    event_handler = FileProcessorHandler(processing_queue, processed_files)
    observer = Observer()
    observer.schedule(
            event_handler, path=target_path, recursive=True
        )
    observer.start()

    try:
        while True:
            if processing_queue:
                job_id = job_helper.suggest_job_id("ESTHERA")
                job_manager.create_job(job_id)

                # Process the first file in the queue
                file_path = processing_queue.pop(0)
                # Make sure the file still exists
                if file_path not in processed_files and os.path.exists(file_path) and core.is_image(file_path):
                    logger.info(f"Processing: {file_path}")
                    generic_arg["target_path"] = file_path

                    # Split the file path into directory, filename and extension
                    directory, filename = os.path.split(file_path)
                    name, ext = os.path.splitext(filename)
                    # Create the new file path
                    output_path = os.path.join(directory, f"{name}-ff{ext}")

                    generic_arg["output_path"] = output_path

                    if job_manager.add_step(job_id, generic_arg):
                        processed_files.add(file_path)
                        processed_files.add(output_path)
                    else:
                        logger.warn(f"Failed to add_step for: {file_path}")
                else:
                    logger.info(f"Already processed or not existed: {file_path}")

                job_manager.submit_job(job_id)

                commands = [ sys.executable, 'facefusion.py', 'job-run-all', "--execution-provider", "cuda", "cpu"]
                if subprocess.run(commands).returncode == 0:
                    save_processed_files(processed_files)
                else:
                    pass
                
                try:
                    shutil.move(file_path, "/home/tinluu/Record/Backup/")
                except:
                    pass
                finally:
                    pass

                save_queue(processing_queue)
            else:
                pass
            sleep(1)  # Sleep for a short duration before checking again
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

def main():
    job_manager.clear_jobs("./.jobs/")
    job_manager.init_jobs("./.jobs/")
    process_monitoring_directory("/home/tinluu/Nextcloud/Record/Photo/")


if __name__ == '__main__':
    main()