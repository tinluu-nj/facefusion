#!/bin/bash

TEMPLATE_JSON="ESTHERA-vid-tmpl.json"
SOURCE_PATH="/home/tinluu/Record/Esthera/unsorted/SRC.jpg"

# Clean up old job files
cleanup() {
    rm -fv .jobs/drafted/*.json \
		   .jobs/queued/*.json \
		   .jobs/failed/*.json \
		   .jobs/completed/*.json
}

# Check if the template file exists
check_template_exists() {
    if [ ! -f "$1" ]; then
        echo "Template file not found!"
        return 1  # Exit with error code 1 if the template is missing
    fi
    return 0
}

# Generate timestamp for job ID
generate_job_id() {
    local timestamp=$(date +"%Y-%m-%d-%H-%M-%S")
    echo "ESTHERA-vid-${timestamp}"  # Output the generated job ID
}

# Prompt for target and output paths
prompt_paths() {
    read -p "Enter target path: " target_path
    read -p "Enter output path: " output_path
    echo "$target_path|$output_path"  # Output both paths as a pipe-separated string
}

# Check if target file exists and convert paths to absolute
validate_paths() {
    local target_path="$1"
    local output_path="$2"

    # Check if target file exists
    if [ ! -f "$target_path" ]; then
        echo "Target file does not exist!"
        return 1
    fi

    # Convert paths to absolute
    target_path=$(realpath "$target_path")
    local target_filename=$(basename "$target_path")
    local target_extension="${target_filename##*.}"

    if [ -d "$output_path" ]; then
        output_path="${output_path%/}/${target_filename}"
    elif [ -f "$output_path" ]; then
        echo "Output file already exists!"
        return 1
    else
        local output_extension="${output_path##*.}"
        if [ "$output_extension" != "$target_extension" ]; then
            echo "Output file extension must match target file extension ($target_extension)!"
            return 1
        fi
    fi

    output_path=$(realpath "$output_path")

    # Check if target and output paths are the same, and add a suffix if necessary
    if [ "$target_path" == "$output_path" ]; then
        output_path="${output_path%.*}-ff.${target_extension}"
        echo "Target and output paths are the same. Output will be saved as: $output_path"
    fi

    echo "$target_path|$output_path"  # Return both validated paths as a pipe-separated string
}

# Modify the JSON template and save it as a drafted job file
update_json() {
    local source_path="$1"
    local target_path="$2"
    local output_path="$3"
    local job_id="$4"

    jq \
        --arg src "$source_path" \
        --arg tgt "$target_path" \
        --arg out "$output_path" \
        '.steps[0].args.source_paths[0] = $src | .steps[0].args.target_path = $tgt | .steps[0].args.output_path = $out' \
        "$TEMPLATE_JSON" > ".jobs/drafted/${job_id}.json"
}

# Activate conda environment
activate_conda() {
    conda init
    conda activate facefusion
}

# Submit and run the facefusion job
run_facefusion() {
    local job_id="$1"
    python facefusion.py job-submit "${job_id}"
    python facefusion.py job-run "${job_id}" \
        --execution-providers cuda \
        --execution-thread-count 4 \
        --execution-queue-count 4 \
        --log-level debug
}

# Deactivate conda environment
deactivate_conda() {
    conda deactivate
}

# Parse command-line arguments
parse_args() {
    while getopts "tgt:out:" opt; do
        case ${opt} in
            tgt )
                TARGET_PATH=$OPTARG
                ;;
            out )
                OUTPUT_PATH=$OPTARG
                ;;
            \? )
                echo "Invalid option: -$OPTARG" 1>&2
                exit 1
                ;;
            : )
                echo "Invalid option: -$OPTARG requires an argument" 1>&2
                exit 1
                ;;
        esac
    done
}

# Main function
main() {
    cleanup

    # Check if the template JSON exists
    if ! check_template_exists "$TEMPLATE_JSON"; then
        exit 1
    fi

    # Generate a new job ID
    JOB_ID=$(generate_job_id)

    # Parse command-line arguments
    parse_args "$@"

    # If target or output path is not provided by command-line, prompt user
    if [ -z "$TARGET_PATH" ] || [ -z "$OUTPUT_PATH" ]; then
        paths=$(prompt_paths)
        TARGET_PATH=$(echo "$paths" | cut -d'|' -f1)
        OUTPUT_PATH=$(echo "$paths" | cut -d'|' -f2)
    fi

    # Validate paths
    validated_paths=$(validate_paths "$TARGET_PATH" "$OUTPUT_PATH")
    if [ $? -ne 0 ]; then
        exit 1
    fi

    TARGET_PATH=$(echo "$validated_paths" | cut -d'|' -f1)
    OUTPUT_PATH=$(echo "$validated_paths" | cut -d'|' -f2)

    # Update the JSON template with the validated paths
    update_json "$SOURCE_PATH" "$TARGET_PATH" "$OUTPUT_PATH" "$JOB_ID"

    # Activate conda environment, run the job, and deactivate environment
    activate_conda
    run_facefusion "$JOB_ID"
    deactivate_conda
}

# Run the main function
main "$@"

