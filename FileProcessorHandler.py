import json
from watchdog.events import FileSystemEventHandler
from facefusion.core import is_image
import os
from time import sleep
from pathlib import Path
queue_file = "ff-job_processing_queue.json"


def save_queue(queue):
    with open(queue_file, "w") as f:
        json.dump(queue, f)

# --- Watchdog Event Handler ---
class FileProcessorHandler(FileSystemEventHandler):
    def __init__(self, processing_queue, processed_files):
        self.processing_queue = processing_queue
        self.processed_files = processed_files

    def on_created(self, event):
        if not event.is_directory:  # Ignore directory creation events
            temp_file_path = event.src_path

            # Extract base filename from the temporary file
            directory, temp_filename = os.path.split(temp_file_path)
            
            # Remove temporary markers (e.g., starting dot, ending "~XXXX") to get the final filename
            final_filename = temp_filename.lstrip('.').split('~')[0]  # Assuming this pattern: ".IMG_XXXX.JPG.~XXXX"
            final_file_path = os.path.join(directory, final_filename)

            # Check if there's a '.' in the filename
            if final_file_path.endswith('.'):
                # Remove the last dot if it exists
                final_file_path = final_file_path.rstrip('.')
            else:
                pass

            # Poll until the final file exists and is stable (transfer complete)
            while not os.path.exists(final_file_path):
                print(f"Waiting for the final file: {final_file_path}")
                sleep(1)  # Adjust the sleep time as needed

            # Wait for file size to stabilize (file transfer to complete)
            file_size = -1
            while file_size != os.path.getsize(final_file_path):
                sleep(1)  # Check every second
                file_size = os.path.getsize(final_file_path)

            # If it's an image, add the final file to the queue
            if is_image(final_file_path):
                self.add_to_queue(final_file_path)
                print(f"Final file transfer complete: {final_file_path}")
            else:
                print(f"Not an image file: {final_file_path}")

    def add_to_queue(self, file_path):
        if not Path(file_path).is_dir() and file_path not in self.processed_files:
            if not file_path in self.processing_queue:
                self.processing_queue.append(file_path)
                save_queue(self.processing_queue)


# --- Queue and Processed File Management ---
def load_queue():
    if os.path.exists(queue_file):
        with open(queue_file, "r") as f:
            return json.load(f)
    return []


processed_files_log = "ff-job_processed_files.json"


def load_processed_files():
    if os.path.exists(processed_files_log):
        with open(processed_files_log, "r") as f:
            return set(json.load(f))
    return set()


def save_processed_files(processed_files):
    with open(processed_files_log, "w") as f:
        json.dump(list(processed_files), f)


def poll_for_new_files(path, processing_queue, processed_files, interval=5):
    known_files = set()

    # Initialize known_files with all current files in the directory and subdirectories
    for root, _, files in os.walk(path):
        for file in files:
            full_path = os.path.join(root, file)
            known_files.add(full_path)

    while True:
        sleep(interval)
        current_files = set()

        # Walk through all directories and subdirectories
        for root, _, files in os.walk(path):
            for file in files:
                full_path = os.path.join(root, file)
                current_files.add(full_path)

        # Find new files
        new_files = current_files - known_files

        # Process new files
        for full_path in new_files:
            if not os.path.isdir(full_path) and full_path not in processed_files and is_image(full_path):
                if not full_path in processing_queue:
                    processing_queue.append(full_path)

        # Update the known files set
        known_files = current_files