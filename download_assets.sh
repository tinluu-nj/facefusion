#!/bin/bash

# Directory to save the downloaded files
asset_dir="./.assets/models"

# Create the directory if it doesn't exist
mkdir -p "$asset_dir"

# Extract URLs containing 'https://github.com/facefusion/facefusion-assets' from Python files and save them to urls.txt
grep -r --include="*.py" "https://github.com/facefusion/facefusion-assets/releases/download/models-3.0.0/" ./facefusion | awk -F"'" '{print $4}' > asset_urls.txt

# Loop through each URL in urls.txt and download the file using curl
while read -r url; do
  echo "Downloading $url..."
  wget -P "$asset_dir" "$url"
done < asset_urls.txt

echo "Download completed!"
