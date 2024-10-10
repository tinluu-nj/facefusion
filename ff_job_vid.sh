#!/bin/bash

TEMPLATE_JSON="ESTHERA-vid-tmpl.json"
SOURCE_PATH=${SOURCE_PATH:-"/home/tinluu/Record/Esthera/unsorted/SRC.jpg"}

# Clean up old job files
cleanup() {
    log_info "Cleaning up old job files..."
    rm -fv .jobs/drafted/*.json \
		.jobs/queued/*.json \
		.jobs/failed/*.json \
		.jobs/completed/*.json
}

# Check if the template file exists
check_template_exists() {
    if [ ! -f "$1" ]; then
        log_error "Template file not found!"
        return 1  # Exit with error code 1 if the template is missing
    fi
    log_info "Template file found: $1"
    return 0
}

# Generate timestamp for job ID
generate_job_id() {
    local timestamp=$(date +"%Y-%m-%d-%H-%M-%S-%3N")
    echo "ESTHERA-vid-${timestamp}"  # Output the generated job ID
}

# Prompt for target and output paths
prompt_paths() {
    read -p "Enter target path: " target_path
    read -p "Enter output path: " output_path
    echo "$target_path|$output_path"  # Output both paths as a pipe-separated string
}

# Get file extension from path
get_filename_extension() {
    local filepath="$1"
    echo "${filepath##*.}"  # Extract the file extension
}

# Check if target file exists and convert paths to absolute
validate_paths() {
    local target_path="$1"
    local output_path="$2"

    # Check if target file exists
    if [ ! -f "$target_path" ]; then
        log_error "Target file does not exist!"
        return 1
    fi

    # Convert paths to absolute
    target_path=$(realpath "$target_path")
    local target_filename=$(basename "$target_path")
    local target_extension=$(get_filename_extension "$target_path")

    if [ -d "$output_path" ]; then
        output_path="${output_path%/}/${target_filename}"
    elif [ -f "$output_path" ]; then
        log_error "Output file already exists!"
        return 1
    else
        local output_extension=$(get_filename_extension "$output_path")
        if [ "$output_extension" != "$target_extension" ]; then
            log_error "Output file extension must match target file extension ($target_extension)!"
            return 2
        fi
    fi

    output_path=$(realpath "$output_path")

    # Check if target and output paths are the same, and add a suffix if necessary
    if [ "$target_path" == "$output_path" ]; then
        output_path="${output_path%.*}-ff.${target_extension}"
        log_info "Target and output paths are the same. Output will be saved as: $output_path"
    fi

    # log_info "Validated paths: Target: $target_path, Output: $output_path"
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

    if [ $? -ne 0 ]; then
        log_error "Failed to update JSON template"
        exit 3
    fi
    log_info "JSON updated successfully and saved as .jobs/drafted/${job_id}.json"
}

# Activate conda environment
activate_conda() {
    conda init
	conda activate facefusion
    if [ $? -ne 0 ]; then
        log_error "Failed to activate Conda environment"
        exit 4
    fi
    log_info "Conda environment 'facefusion' activated"
}

# Submit and run the facefusion job
run_facefusion() {
    local job_id="$1"
    python facefusion.py job-submit "${job_id}"
    if [ $? -ne 0 ]; then
        log_error "Job submission failed"
        exit 5
    fi

    python facefusion.py job-run "${job_id}" \
        --execution-providers cuda \
        --execution-thread-count 4 \
        --execution-queue-count 4 \
        --log-level debug
    if [ $? -ne 0 ]; then
        log_error "Job execution failed"
        exit 6
    fi
    log_info "Job ${job_id} executed successfully"
}

# Deactivate conda environment
deactivate_conda() {
    conda deactivate
    if [ $? -ne 0 ]; then
        log_error "Failed to deactivate Conda environment"
        exit 7
    fi
    log_info "Conda environment deactivated"
}

# Parse command-line arguments
parse_args() {
    while getopts "t:o:" opt; do
        case ${opt} in
            t ) # target path
                TARGET_PATH=$OPTARG
                ;;
            o ) # output path
                OUTPUT_PATH=$OPTARG
                ;;
            \? ) # Invalid option
                log_error "Invalid option: -$OPTARG"
                exit 1
                ;;
            : ) # Missing argument for option
                log_error "Missing argument for -$OPTARG"
                exit 1
                ;;
        esac
    done
}

# Log info message with timestamp
log_info() {
    local msg="$1"
    echo "$(date +"%Y-%m-%d %H:%M:%S") - INFO: $msg"
}

# Log error message with timestamp
log_error() {
    local msg="$1"
    echo "$(date +"%Y-%m-%d %H:%M:%S") - ERROR: $msg" 1>&2
}

# Ensure required tools are installed
check_tools() {
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed. Please install jq."
        exit 1
    fi
    log_info "All required tools are available"
}

# Main function
main() {
    # trap cleanup EXIT  # Ensure cleanup runs on exit

    log_info "Starting the script"

    # Ensure necessary tools are available
    check_tools

    # Clean up old job files
    cleanup

    # Check if the template JSON exists
    if ! check_template_exists "$TEMPLATE_JSON"; then
        exit 1
    fi

    # Generate a new job ID
    JOB_ID=$(generate_job_id)
    log_info "Generated Job ID: $JOB_ID"

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

	log_info "TARGET_PATH: $TARGET_PATH"
	log_info "OUTPUT_PATH: $OUTPUT_PATH"

    # Update the JSON template with the validated paths
    update_json "$SOURCE_PATH" "$TARGET_PATH" "$OUTPUT_PATH" "$JOB_ID"

    # Activate conda environment, run the job, and deactivate environment
    # activate_conda
    run_facefusion "$JOB_ID"
    # deactivate_conda

    log_info "Script completed successfully"
}

# Run the main function with all command-line arguments passed in
main "$@"

