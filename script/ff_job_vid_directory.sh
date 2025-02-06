#!/bin/sh

# Directory to list files from (you can change this or pass it as an argument)
directory="$1"

# If no directory is provided, default to the current directory
if [ -z "$directory" ]; then
  directory="."
fi

# Loop through all files in the directory and its subdirectories
find "$directory" -type f | while IFS= read -r file
do
  # Print the full path of each file
  echo "$file"
  ./ff_job_vid.sh -t $file -o .
  python facefusion.py job-run-all --execution-providers cuda --execution-thread-count 4 --execution-queue-count 4 --log-level debug
done


