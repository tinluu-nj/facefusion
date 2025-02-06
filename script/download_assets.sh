#!/bin/bash

# Directory to save the downloaded files
DIR="./.assets/models"
ASSET_LIST="./script.d/asset_urls.txt"
SEARCH_DIR="./facefusion"
MODEL_VERSIONS=("3.0.0" "3.1.0")

# Create necessary directories
mkdir -p "$DIR"

# Function to extract asset URLs
get_assets() {
    echo "Extracting asset URLs..."
    > "$ASSET_LIST"  # Clear the file before appending new results

    for VERSION in "${MODEL_VERSIONS[@]}"; do
        grep -r --include="*.py" "resolve_download_url('models-${VERSION}', '" "$SEARCH_DIR" | \
        awk -F"'" '{print "https://github.com/facefusion/facefusion-assets/releases/download/models-'$VERSION'/"$6}' >> "$ASSET_LIST"
    done

    # Remove duplicate URLs while preserving order
    awk '!seen[$0]++' "$ASSET_LIST" > temp_file && mv temp_file "$ASSET_LIST"

    echo "Asset list updated: $ASSET_LIST"
}

# Function to download assets
download_assets() {
    if [ ! -f "$ASSET_LIST" ]; then
        echo "Error: Asset list ($ASSET_LIST) not found. Run --get first."
        exit 1
    fi

    echo "Starting downloads..."
    while read -r url; do
        FILENAME=$(basename "$url")
        FILEPATH="$DIR/$FILENAME"

        if [ -f "$FILEPATH" ]; then
            echo "File '$FILENAME' already exists. Skipping."
        else
            echo "Downloading '$FILENAME'..."
            wget -T 1 -t 3 -P "$DIR" "$url" && echo "Downloaded: $FILENAME" || echo "Failed: $FILENAME"
        fi
    done < "$ASSET_LIST"

    echo "Download process completed!"
}

# Function to check missing assets
check_assets() {
    if [ ! -f "$ASSET_LIST" ]; then
        echo "Error: Asset list ($ASSET_LIST) not found. Run --get first."
        exit 1
    fi

    echo "Checking missing assets..."
    MISSING_FILES=()

    while read -r url; do
        FILENAME=$(basename "$url")
        FILEPATH="$DIR/$FILENAME"
        if [ ! -f "$FILEPATH" ]; then
            MISSING_FILES+=("$FILENAME")
        fi
    done < "$ASSET_LIST"

    if [ ${#MISSING_FILES[@]} -eq 0 ]; then
        echo "All assets are downloaded!"
    else
        echo "Missing assets:"
        printf '%s\n' "${MISSING_FILES[@]}"
    fi
}

# Argument handling
case "$1" in
    --get)
        get_assets
        ;;
    --download)
        download_assets
        ;;
    --check)
        check_assets
        ;;
    --all)
        get_assets
        download_assets
        check_assets
        ;;
    *)
        echo "Usage: $0 --get | --download | --check | --all"
        exit 1
        ;;
esac
