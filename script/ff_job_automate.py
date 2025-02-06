import argparse

from script.FileProcessorHandler import setup_automation

# Global variables for directory paths
JOB_DIRECTORY = "./.jobs/"
PHOTO_DIRECTORY = "/home/tinluu/Nextcloud/Record/Photo/"

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
    setup_automation(PHOTO_DIRECTORY, args.polling)

if __name__ == '__main__':
    main()
