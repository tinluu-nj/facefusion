import pytest
from pathlib import Path
import time
import threading
from unittest.mock import patch, MagicMock
import shutil
import os
import json
from watchdog.events import FileCreatedEvent
from script.FileProcessorHandler import setup_automation, FileProcessorHandler, redundant_poll_for_new_files, _extract_exif_metadata, profile_media, load_configuration, process_directory_profile, execute_facefusion_job, backup_file, execute_facefusion_job

def test__extract_exif_metadata_no_exif():
    """
    Test extract_exif_metadata when no EXIF data is present.
    """
    with patch("PIL.Image.open") as mock_open:
        mock_image = MagicMock()
        mock_image._getexif.return_value = None
        mock_open.return_value = mock_image

        metadata = _extract_exif_metadata("test_image.jpg")
        assert metadata == {}

def test__extract_exif_metadata_with_exif():
    """
    Test extract_exif_metadata when EXIF data is present.
    """
    with patch("PIL.Image.open") as mock_open:
        mock_image = MagicMock()
        mock_image._getexif.return_value = {305: "Apple"}
        mock_open.return_value = mock_image

        metadata = _extract_exif_metadata("test_image.jpg")
        assert metadata == {"Software": "Apple"}

def test_profile_media_file_not_found():
    """
    Test profile_media when the file does not exist.
    """
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError):
            profile_media("non_existent_file.jpg")

def test_profile_media_image():
    """
    Test profile_media for an image file.
    """
    with patch("pathlib.Path.exists", return_value=True), \
         patch("script.FileProcessorHandler._extract_exif_metadata", return_value={"Software": "Apple"}):

        profile = profile_media("test_image.jpg")
        assert profile["test_image.jpg"]["is_image"] is True
        assert profile["test_image.jpg"]["is_video"] is False
        assert profile["test_image.jpg"]["is_facefusion"] is False

def test_profile_media_video():
    """
    Test profile_media for a video file.
    """
    mock_track = MagicMock()
    mock_track.to_data.return_value = {"encoded_library_name": "Apple"}
    mock_media_info = MagicMock()
    mock_media_info.tracks = [mock_track]

    with patch("pathlib.Path.exists", return_value=True), \
         patch("pymediainfo.MediaInfo.parse", return_value=mock_media_info):

        profile = profile_media("test_video.mp4")
        assert profile["test_video.mp4"]["is_image"] is False
        assert profile["test_video.mp4"]["is_video"] is True
        assert profile["test_video.mp4"]["is_facefusion"] is False

def test_profile_media_with_sample():
    """
    Test profile_media with real file paths.
    """
    test_cases = [
        ("/home/tinluu/Projects/facefusion/sample/IMG_8624.jpg", False, True, False, False, False),
        ("/home/tinluu/Projects/facefusion/sample/IMG_8611.JPG", False, True, False, False, True),
        ("/home/tinluu/Projects/facefusion/sample/IMG_8625.MOV", False, False, True, False, False),
        ("/home/tinluu/Projects/facefusion/sample/05c2b2f4f9c175f4ea40743faccaf8d4.mp4", False, False, True, True, False),
        ("/home/tinluu/Projects/facefusion/sample/srii_6230 2024-10-24T071320-2.mp4", False, False, True, False, True),
    ]

    for img_path, processed, is_image, is_video, is_faceplay, is_facefusion in test_cases:
        profile = profile_media(img_path)
        file_name = Path(img_path).name
        assert profile[file_name] == {
            "directory": img_path,
            "backup": None,
            "processed": processed,
            "is_image": is_image,
            "is_video": is_video,
            "is_faceplay": is_faceplay,
            "is_facefusion": is_facefusion,
        }

@pytest.fixture
def test_directory():
    """
    Creates a test directory in the current working directory and removes it after the test.
    """
    test_dir = Path.cwd() / "test_directory"
    test_dir.mkdir(exist_ok=True)

    yield test_dir  # Provide the directory path to the test function

    # Cleanup after test
    shutil.rmtree(test_dir, ignore_errors=True)

def test_poll_for_new_files_sample(test_directory):
    """
    Test poll_for_new_files by copying real files to the monitored directory.
    """
    directory_profile = {}
    stop_event = threading.Event()

    # Sample file to copy
    source_file = test_directory / "sample.txt"
    source_file.write_text("This is a sample file.")

    # Start polling in a background thread
    monitor_thread = threading.Thread(
        target=redundant_poll_for_new_files,
        args=(str(test_directory), directory_profile),
        kwargs={"interval": 1, "stop_event": stop_event}
    )
    monitor_thread.start()

    # Copy file to monitored directory
    time.sleep(2)  # Allow poller to start
    dest_file = test_directory / "copied_sample.txt"
    dest_file.write_text(source_file.read_text())

    # Wait for the poller to detect new files
    time.sleep(3)

    # Stop the polling thread
    stop_event.set()
    monitor_thread.join()

    # Assertions
    assert "copied_sample.txt" in directory_profile
    assert directory_profile["copied_sample.txt"]["directory"] == str(dest_file)


@pytest.fixture
def temp_directory(tmp_path):
    """
    Creates a temporary directory for testing and cleans up after the test.
    """
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()
    yield test_dir
    shutil.rmtree(test_dir, ignore_errors=True)

@pytest.fixture
def mock_directory_profile():
    """
    Returns a mock directory profile for testing.
    """
    return {}

def test_on_created_file_processing(temp_directory, mock_directory_profile, monkeypatch):
    """
    Tests that on_created waits for the file transfer to complete and updates the directory profile.
    """
    handler = FileProcessorHandler(mock_directory_profile)
    
    # Create a mock event for a new file
    temp_file = temp_directory / "test_file.txt.~XXXX"
    final_file = temp_directory / "test_file.txt"
    
    temp_file.touch()
    event = FileCreatedEvent(str(temp_file))
    
    # Mock os.path.exists to simulate file transfer completion
    def mock_exists(path):
        return path in {str(final_file), str(temp_file)}
    
    def mock_getsize(path):
        return 1024 if path == str(final_file) else 512  # Simulate file size change for stabilization
    
    monkeypatch.setattr(os.path, "exists", mock_exists)
    monkeypatch.setattr(os.path, "getsize", mock_getsize)
    
    # Create the final file
    temp_file.rename(final_file)  # Simulate file renaming upon transfer completion
    
    # Mock profile_media function
    def mock_profile_media(file_path):
        return {file_path: {"directory": file_path, "processed": True}}
    
    monkeypatch.setattr("script.FileProcessorHandler.profile_media", mock_profile_media)
    
    handler.on_created(event)
    
    assert str(final_file) in mock_directory_profile
    assert mock_directory_profile[str(final_file)]["processed"] is True

@pytest.fixture
def temp_config_file(tmp_path):
    """Creates a temporary JSON configuration file for testing."""
    config_file = tmp_path / "config.json"
    config_data = {"key": "value"}
    config_file.write_text(json.dumps(config_data))
    return config_file

def test_load_configuration(temp_config_file):
    """Tests loading a JSON configuration file."""
    config = load_configuration(str(temp_config_file))
    assert config == {"key": "value"}

@pytest.fixture
def mock_directory_profile():
    """Returns a mock directory profile."""
    return {
        "test_file.jpg": {"directory": "/mock/path/test_file.jpg", "processed": False, "is_image": True, "is_facefusion": True},
        "test_video.mp4": {"directory": "/mock/path/test_video.mp4", "processed": False, "is_video": True, "is_facefusion": True}
    }

def test_process_directory_profile(mock_directory_profile):
    """Tests processing files from a directory profile."""
    with patch("script.FileProcessorHandler.execute_facefusion_job") as mock_job:
        process_directory_profile(mock_directory_profile)
        assert mock_job.call_count == 2  # Ensures both image and video processing calls occur

@pytest.fixture
def temp_file(tmp_path):
    """Creates a temporary file for testing backup operations."""
    tmp_directory = tmp_path / "Photo/2024/10"
    tmp_directory.mkdir(parents=True)
    file_path = tmp_path / "Photo/2024/10/test_file.jpg"
    file_path.touch()
    return file_path

def test_backup_file(temp_file, mock_directory_profile):
    """Tests backing up a processed file."""
    backup_directory = temp_file.parent / "backup"
    backup_directory.mkdir()

    processing_file = mock_directory_profile["test_file.jpg"]
    processing_file["directory"] = str(temp_file)

    with patch("shutil.move") as mock_move:
        backup_file(mock_directory_profile, backup_directory, processing_file)
        mock_move.assert_called_once()  # Ensure file was moved

        # Check if the file entry was removed
        matching_key = next(
            (key for key, value in mock_directory_profile.items() if value["directory"] == processing_file["directory"]),
            None
        )
        assert matching_key is None

@pytest.fixture
def mock_generic_arg():
    """Returns a mock generic argument dictionary."""
    return {}

def test_execute_facefusion_job_success(mock_directory_profile, mock_generic_arg):
    """Tests executing a FaceFusion job successfully."""
    with patch("facefusion.jobs.job_manager.add_step", return_value=True) as mock_add_step, \
         patch("facefusion.jobs.job_manager.create_job") as mock_create_job, \
         patch("facefusion.jobs.job_manager.submit_job") as mock_submit_job, \
         patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_subprocess:
        
        execute_facefusion_job(mock_directory_profile, mock_directory_profile["test_file.jpg"], mock_generic_arg)
        
        # Ensure create_job was called
        mock_create_job.assert_called_once()
        # Ensure add_step was called
        mock_add_step.assert_called_once()
        # Ensure submit_job was called
        mock_submit_job.assert_called_once()
        # Ensure subprocess.run was called to execute facefusion
        mock_subprocess.assert_called_once()

def test_execute_facefusion_job_failure(mock_directory_profile, mock_generic_arg):
    """Tests handling of a FaceFusion job failure."""
    with patch("facefusion.jobs.job_manager.add_step", return_value=False) as mock_add_step, \
         patch("facefusion.jobs.job_manager.create_job") as mock_create_job, \
         patch("logging.Logger.warning") as mock_logger:
        
        execute_facefusion_job(mock_directory_profile, mock_directory_profile["test_file.jpg"], mock_generic_arg)
        
        # Ensure add_step was called
        mock_add_step.assert_called_once()
        # Ensure warning log was triggered
        mock_logger.assert_called_with(f"Failed to add_step for: {mock_directory_profile["test_file.jpg"]['directory']}")

@pytest.fixture
def mock_directory():
    """Returns a mock directory path."""
    return "/mock/directory"

def test_setup_automation_with_polling(mock_directory):
    """Tests setup_automation function with polling enabled."""
    with patch("script.FileProcessorHandler.redundant_poll_for_new_files") as mock_poll, \
         patch("script.FileProcessorHandler.FileProcessorHandler") as mock_handler, \
         patch("script.FileProcessorHandler.Observer") as mock_observer, \
         patch("script.FileProcessorHandler.process_directory_profile", side_effect=KeyboardInterrupt) as mock_process, \
         patch("threading.Thread", autospec=True) as mock_thread:
        
        mock_thread_instance = mock_thread.return_value
        mock_thread_instance.start.side_effect = lambda: mock_poll("mock_dir", {}, interval=1, stop_event=MagicMock())
        mock_thread_instance.is_alive.return_value = False
        
        setup_automation(mock_directory, polling=True)
        
        # # Ensure the polling thread was started and joined
        # mock_thread_instance.start.assert_called_once()
        # mock_thread_instance.join.assert_called_once()
        
        # Ensure observer methods were called
        mock_handler.assert_called_once()
        mock_observer_instance = mock_observer.return_value
        mock_observer_instance.schedule.assert_called_once()
        mock_observer_instance.start.assert_called_once()
        mock_observer_instance.stop.assert_called_once()
        mock_observer_instance.join.assert_called_once()

def test_setup_automation_without_polling(mock_directory):
    """Tests setup_automation function without polling enabled."""
    with patch("script.FileProcessorHandler.FileProcessorHandler") as mock_handler, \
         patch("script.FileProcessorHandler.Observer") as mock_observer, \
         patch("script.FileProcessorHandler.process_directory_profile", side_effect=KeyboardInterrupt) as mock_process:
        
        setup_automation(mock_directory, polling=False)
        
        # Ensure observer methods were called
        mock_handler.assert_called_once()
        mock_observer_instance = mock_observer.return_value
        mock_observer_instance.schedule.assert_called_once()
        mock_observer_instance.start.assert_called_once()
        mock_observer_instance.stop.assert_called_once()
        mock_observer_instance.join.assert_called_once()
