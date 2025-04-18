import argparse

from script.FileProcessorHandler import setup_automation

# Global variables for directory paths
PHOTO_DIRECTORY = "/home/tinluu/Nextcloud/Record/Photo/"

def main() -> None:
    """
    Main function to initialize jobs and start the directory monitoring process.
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Automate facefusion jobs")
    parser.add_argument("--polling", action="store_true", help="Enable polling for new files")
    parser.add_argument("--debug", action="store_true", help="Enable debug")
    args = parser.parse_args()

    # Process the monitoring directory with or without polling
    setup_automation(PHOTO_DIRECTORY, args.polling, args.debug)

if __name__ == '__main__':
    main()
