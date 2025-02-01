#!/bin/sh

# Path to the file containing the URLs
input_file="shorts_data.txt"

# Loop through each line in the file
while IFS= read -r url
do
  # Make the POST request with the current line (URL) replacing the "url" field in the JSON payload
  curl -X POST https://metube.trygve.site/add \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"$url\",\"quality\":\"best\",\"format\":\"mp4\",\"playlist_strict_mode\":false,\"auto_start\":true}"

  # Optionally, print a message after each POST request
  echo "Posted: $url"

done < "$input_file"
