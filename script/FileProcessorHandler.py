import os
import json
import time
import logging
import threading
import shutil
import sys
import subprocess

from time import sleep
from pathlib import Path
from watchdog.events import FileSystemEventHandler
from PIL import Image
from PIL.ExifTags import TAGS
from pymediainfo import MediaInfo
from threading import Thread
from watchdog.observers import Observer

from facefusion.jobs import job_helper, job_manager

"""
File: FileProcessorHandler.py

Description:
This module provides file monitoring and media profiling functionalities. It includes:
- A watchdog event handler to monitor newly created files and update a directory profile.
- A polling function to detect new files periodically.
- Functions to extract EXIF metadata and profile media files.

Usage:
- Use `FileProcessorHandler` to monitor a directory for file creation events.
- Call `poll_for_new_files()` to scan for new files at intervals.
- Use `profile_media()` to extract metadata from images and videos.

Author: Tin Luu
Change History:
- 02-02-2025 - 1.0.0 - Initial

"""
JOB_DIRECTORY = "./.jobs/"
BACKUP_DIRECTORY = "/home/tinluu/Record/Backup/facefusion.bak.d/"
IMG_CONFIG_FILE = "./config.d/ESTHERA-conf.json"
VID_CONFIG_FILE = "./config.d/ESTHERA-vid-tmpl.json"
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

def setup_automation(target_path: str, polling: bool, debug: bool) -> None:
    """
    Sets up automation for monitoring a directory, using either polling or event-based monitoring.

    Parameters
    ----------
    target_path : str
        The path of the directory to monitor.
    polling : bool
        Whether to enable polling-based monitoring in addition to event-based monitoring.
    """
    if debug:
        logger.setLevel(logging.DEBUG)

    # Clear and initialize the job directory
    job_manager.clear_jobs(JOB_DIRECTORY)
    job_manager.init_jobs(JOB_DIRECTORY)

    directory_profile = {}
    logger.debug(f"Monitoring {target_path}")

    stop_event = threading.Event()
    polling_thread = None
    
    # Start the polling thread if polling is enabled
    if polling:
        logger.info(f"Setting up polling thread...")
        polling_thread = Thread(
            target=redundant_poll_for_new_files,
            args=(target_path, directory_profile),
            kwargs={"interval": 1, "stop_event": stop_event},
            daemon=True  # Allows script to exit even if polling thread is running
        )
        try:
            polling_thread.start()
            logger.info(f"Started polling thread...")
        except Exception as e:
            logger.error(f"Failed with exception: {e}")

    # Set up file event handler and observer
    logger.info(f"Setting up Observer...")
    event_handler = FileProcessorHandler(directory_profile)
    observer = Observer()
    observer.schedule(event_handler, path=target_path, recursive=True)
    observer.start()
    logger.info(f"Started Observer...")

    # Process the directory
    try:
        while True:
            process_directory_profile(directory_profile)
            sleep(1)  # Sleep briefly before checking again
    except KeyboardInterrupt:
        logger.info("Stopping automation due to keyboard interrupt...")
        stop_event.set()
        observer.stop()
    
    # Ensure threads exit cleanly
    if polling_thread:
        polling_thread.join()
    observer.join()


def load_configuration(file_path: str) -> dict:
    """
    Loads configuration from a JSON file.
    
    Parameters
    ----------
    file_path : str
        The path to the configuration file.

    Returns
    -------
    dict
        The loaded configuration dictionary.
    """
    with open(file_path, 'r') as file:
        return json.load(file)

# Load configurations
IMG_GENERIC_ARG = load_configuration(IMG_CONFIG_FILE)
VID_GENERIC_ARG = load_configuration(VID_CONFIG_FILE)

def process_directory_profile(directory_profile: dict) -> None:
    """
    Processes files in the directory profile based on their attributes.
    
    Parameters
    ----------
    directory_profile : dict
        A dictionary containing file metadata to be processed.
    """
    for processing_file in filter_directory_profile(directory_profile, is_faceplay=True):
        logger.info(f"Processing faceplay item: {processing_file['directory']}")
        backup_file(directory_profile, BACKUP_DIRECTORY, processing_file)

    for processing_file in filter_directory_profile(directory_profile, processed=False, is_image=True, is_facefusion=True):
        logger.info(f"Processing image: {processing_file['directory']}")
        execute_facefusion_job(directory_profile, processing_file, IMG_GENERIC_ARG)

    for processing_file in filter_directory_profile(directory_profile, processed=False, is_video=True, is_facefusion=True):
        logger.info(f"Processing video: {processing_file['directory']}")
        execute_facefusion_job(directory_profile, processing_file, VID_GENERIC_ARG)

def execute_facefusion_job(directory_profile: dict, processing_file: dict, generic_arg: dict) -> None:
    """
    Executes a FaceFusion job for an image or video file.
    
    Parameters
    ----------
    processing_file : dict
        The file metadata dictionary.
    generic_arg : dict
        The FaceFusion job arguments.
    """
    # Suggest a job ID
    job_id = job_helper.suggest_job_id("ESTHERA")
    job_manager.create_job(job_id)

    file_path = processing_file["directory"]
    directory, filename = os.path.split(file_path)
    name, ext = os.path.splitext(filename)
    output_path = os.path.join(directory, f"{name}-ff{ext}")

    # Set target and output paths in generic arguments
    generic_arg["target_path"] = file_path
    generic_arg["output_path"] = output_path

    # Add a step to the job manager
    if job_manager.add_step(job_id, generic_arg):
        # Submit the job
        job_manager.submit_job(job_id)

        # Execute FaceFusion processing
        commands = [sys.executable, 'facefusion.py', 'job-run-all', "--execution-provider", "cuda", "--log-level", "debug"]
        if subprocess.run(commands).returncode == 0:
            backup_file(directory_profile, BACKUP_DIRECTORY, processing_file)
        else:
            logger.warning(f"FaceFusion processing failed for: {file_path}")

    else:
        logger.warning(f"Failed to add_step for: {file_path}")


def backup_file(directory_profile: dict, backup_directory: Path, processing_file: dict) -> None:
    """
    Moves a processed file to the backup directory.
    
    Parameters
    ----------
    processing_file : dict
        The file metadata dictionary.
    """
    try:
        # Extract reserved path from directory (6th and 7th segments in path)
        reserved_path = "/".join(processing_file["directory"].split('/')[6:8])
        backup_path = Path("/".join([backup_directory, reserved_path]))

        # Ensure the backup directory exists
        backup_path.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(processing_file["directory"], backup_path)
        except:
            # File already exists at the destination, delete it and retry move
            logging.warning(f"File already exists at {backup_path}, deleting and retrying move.")
            
            try:
                os.remove(processing_file["directory"])  # Remove the existing file
            except Exception as e:
                logging.warning(f"Failed to remove file: {e}")

        # Remove the file entry from the directory profile
        matching_key = next(
            (key for key, value in directory_profile.items() if value["directory"] == processing_file["directory"]),
            None
        )
        if matching_key:
            directory_profile.pop(matching_key, None)

    except Exception as e:
        logger.warning(f"Failed to move file: {e}")


def filter_directory_profile(profile: dict, **conditions) -> list:
    """
    Filters a dictionary of dictionaries based on given conditions.

    Parameters
    ----------
    profile : dict
        The dictionary to filter.

    conditions : keyword arguments
        The conditions to match (e.g., is_image=True).

    Returns
    ----------
    list
        A list of dictionaries matching the conditions.
    """
    return [
        {"filename": key, **value} for key, value in profile.items()
        if all(value.get(k) == v for k, v in conditions.items())
    ]


# --- Watchdog Event Handler ---
class FileProcessorHandler(FileSystemEventHandler):
    """
    Handles newly created files in a monitored directory and updates the directory profile.
    
    This class listens for file creation events and ensures that new files are fully transferred 
    before processing their metadata. It is designed to be compatible with various cloud storage 
    synchronization tools that use temporary filenames during transfer.

    Attributes
    ----------
    directory_profile : dict
        A dictionary storing metadata of detected files.
    """
    def __init__(self, directory_profile: dict) -> None:
        """
        Initializes the FileProcessorHandler.

        Parameters
        ----------
        directory_profile : dict
            Dictionary storing metadata of detected files.
        """
        self.directory_profile = directory_profile

    def on_created(self, event) -> None:
        """
        Handles newly created files by extracting and processing their metadata.

        This function waits until the file is fully transferred before updating 
        the directory profile with its metadata.

        Parameters
        ----------
        event : FileSystemEvent
            The event triggered when a file is created.
        """
        if event.is_directory:
            return  # Ignore directory creation events
        
        temp_file_path = event.src_path
        directory, temp_filename = os.path.split(temp_file_path)
        
        # Remove temporary markers and reconstruct final filename
        final_filename = temp_filename.lstrip('.').split('~')[0]
        final_file_path = os.path.join(directory, final_filename)
        
        if final_file_path.endswith('.'):
            final_file_path = final_file_path.rstrip('.')
        
        # Wait until the final file exists
        while not os.path.exists(final_file_path):
            logger.info(f"Waiting for the final file: {final_file_path}")
            sleep(1)
        
        # Ensure the file transfer is complete by monitoring file size stabilization
        previous_size = -1
        while previous_size != os.path.getsize(final_file_path):
            sleep(1)
            previous_size = os.path.getsize(final_file_path)
        
        # Update the directory profile with metadata
        self.directory_profile.update(profile_media(final_file_path))


def redundant_poll_for_new_files(
    directory_path: str,
    directory_profile: dict,
    interval: int = 5,
    stop_event: threading.Event = None,
) -> None:
    """
    Monitors a directory for new files and updates the directory profile.

    Parameters
    ----------
    directory_path : str
        The path to the directory to monitor.

    directory_profile : dict
        A dictionary storing metadata of detected files.

    interval : int, optional
        The interval (in seconds) between checks for new files. Default is 5.

    stop_event : threading.Event, optional
        A threading event to allow graceful stopping of the loop.

    Raises
    ------
    FileNotFoundError
        If the specified directory does not exist.
    """
    path_obj = Path(directory_path)

    if not path_obj.exists() or not path_obj.is_dir():
        logging.warning(f"File not found: {directory_path}")

    # Initialize known_files with no files in directory and subdirectories
    known_files = set()

    logger.info(f"Monitoring directory: {directory_path}")

    while stop_event is None or not stop_event.is_set():
        time.sleep(interval)

        # Get the current set of files
        current_files = {file for file in path_obj.rglob("*") if file.is_file()}
        
        # Find new files
        new_files = current_files - known_files

        if new_files and known_files:
            logger.info(f"New files detected: {[file.name for file in new_files]}")
        elif not known_files:
            logger.info(f"Initialized Profiling...")

        # Process new files
        for file in new_files:
            file_path = str(file)
            directory_profile.update(profile_media(file_path))

        # Update the known files set
        known_files = current_files

def _extract_exif_metadata(file_path: str) -> dict:
    """
    Extracts EXIF metadata from an image file.

    Parameters
    ----------
    file_path : str
        The path to the image file.

    Return
    ------
    metadata : dict
        A dictionary containing EXIF metadata. If no metadata is found, returns an empty dictionary.

    Raises
    ------
    FileNotFoundError
        If the specified image file does not exist.
    PIL.UnidentifiedImageError
        If the file is not a valid image.
    """
    try:
        image = Image.open(file_path)
        exif_data = image._getexif()
        if not exif_data:
            return {}

        # Convert EXIF data into a readable dictionary format
        return {TAGS.get(tag, tag): value for tag, value in exif_data.items()}
    except FileNotFoundError:
        logging.warning(f"File not found: {file_path}")
    except UnidentifiedImageError:
        logging.warning(f"Invalid image file: {file_path}")
    except Exception as error:
        logging.warning(f"Error extracting EXIF metadata: {error}")

def profile_media(file_path: str) -> dict:
    """
    Profiles a media file (image or video) and extracts relevant metadata.

    Parameters
    ----------
    file_path : str
        The path to the media file (image or video).

    Return
    ------
    media_profile : dict
        A dictionary containing metadata about the media file, including:
            - directory (str): The full file path.
            - backup (NoneType): Placeholder for backup-related info.
            - processed (bool): Whether the file has been processed.
            - is_image (bool): Whether the file is an image.
            - is_video (bool): Whether the file is a video.
            - is_faceplay (bool): Whether the file originates from FacePlay.
            - is_facefusion (bool): Whether the file is FaceFusion-compatible.

    Raises
    ------
    FileNotFoundError
        If the specified media file does not exist.
    """
    path_obj = Path(file_path)

    if not path_obj.exists():
        logging.warning(f"File not found: {file_path}")

    file_name = path_obj.name
    file_extension = path_obj.suffix.lstrip(".").casefold()  # Normalize case for extension comparison

    media_profile = {
        file_name: {
            "directory": str(path_obj),
            "backup": None,
            "processed": path_obj.stem.endswith("-ff"),  # Check if filename indicates processing
            "is_image": file_extension in {"png", "jpg", "jpeg"},
            "is_video": file_extension in {"mp4", "mov"},
            "is_faceplay": False,  # Default assumptions
            "is_facefusion": True,
        }
    }

    file_metadata = media_profile[file_name]

    # Process Image Files
    if file_metadata["is_image"]:
        try:
            metadata = _extract_exif_metadata(file_path)
            # Check EXIF metadata for 'Apple' to determine FaceFusion compatibility
            if any(str(value).casefold() == "apple" for value in metadata.values()):
                file_metadata["is_facefusion"] = False
        except:
            logger.warning(f"Failed to extract exif metadata: {file_path}")

    # Process Video Files
    elif file_metadata["is_video"]:
        try:
            media_info = MediaInfo.parse(file_path)
            for track in media_info.tracks:
                metadata = track.to_data()
                # Identify FacePlay files based on metadata
                if any("深圳市鹏中科技有限公司" in str(value) for value in metadata.values()):
                    file_metadata["is_faceplay"] = True
                    file_metadata["is_facefusion"] = False
                    break
                # Identify Apple-related metadata
                if any(str(value).casefold() == "apple" for value in metadata.values()):
                    file_metadata["is_facefusion"] = False
                    break
        except:
            logger.warning(f"Failed to extract MediaInfo: {file_path}")


    logger.debug(f"Finished profiling file: {file_path}")
    return media_profile
