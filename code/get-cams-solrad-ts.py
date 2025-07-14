import cdsapi
import pandas as pd
import os
import sys
import re
import zipfile

# --- CONFIGURATION ---
# The CSV file containing the locations to process.
# It must have 'latitude', 'longitude', 'elevation', and 'station' columns.
INPUT_CSV_PATH = 'asrs_location.csv'

# The directory where all output files will be saved.
OUTPUT_DIR = 'solar_data_output'

# The name of the CAMS dataset to be downloaded.
CAMS_DATASET = 'cams-solar-radiation-timeseries'

# --- Utility Functions ---

def zip_and_delete_raw_file(raw_file_path):
    """
    Compresses the given raw data file into a ZIP archive and then deletes the original.

    Args:
        raw_file_path (str): The path to the raw CSV file to be zipped.
    """
    if not os.path.exists(raw_file_path):
        print(f"Warning: Cannot zip file, {raw_file_path} does not exist.", file=sys.stderr)
        return

    zip_file_path = raw_file_path.replace('.csv', '.zip')
    
    try:
        print(f"Compressing {raw_file_path} to {zip_file_path}...")
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # arcname ensures the file is stored in the zip without the directory path
            zf.write(raw_file_path, arcname=os.path.basename(raw_file_path))
        
        print(f"Successfully created zip archive. Deleting original raw file...")
        os.remove(raw_file_path)

    except Exception as e:
        print(f"Error during zipping or deleting {raw_file_path}: {e}", file=sys.stderr)


def aggregate_to_10min(raw_file_path, processed_file_path):
    """
    Reads a raw 1-minute CAMS solar data file, aggregates it to 10-minute
    averages, and saves the result to a new CSV file.

    This function is designed to handle the specific 'csv_expert' format from CAMS,
    where metadata and the header row are commented out with '#'.

    Args:
        raw_file_path (str): The path to the input raw data file.
        processed_file_path (str): The path where the processed data will be saved.
    
    Returns:
        bool: True if processing was successful, False otherwise.
    """
    try:
        # Manually find the header from the commented lines
        header_line = None
        with open(raw_file_path, 'r') as f:
            for line in f:
                if line.startswith('#'):
                    header_line = line
                else:
                    break
        
        if header_line is None:
            print(f"Error: Could not find a header line in {raw_file_path}", file=sys.stderr)
            return False

        column_names = [col.strip() for col in header_line.strip().lstrip('#').split(';')]

        df = pd.read_csv(
            raw_file_path,
            comment='#',
            delimiter=';',
            header=None,
            names=column_names
        )

        if df.empty:
            print(f"Warning: Raw data file {raw_file_path} is empty or contains only data comments.")
            return False

        df['time'] = pd.to_datetime(df['Observation period'].str.split('/').str[0])
        df.set_index('time', inplace=True)

        numeric_cols = df.select_dtypes(include='number')
        df_10min = numeric_cols.resample('10min').mean()

        df_10min.to_csv(processed_file_path)
        print(f"Successfully processed and saved to {processed_file_path}")
        return True
    except Exception as e:
        print(f"An unexpected error occurred while processing {raw_file_path}: {e}", file=sys.stderr)
        return False

# --- Main Execution Block ---

def main():
    """
    Main function to orchestrate the download and processing workflow.
    It reads locations, downloads data for each, triggers aggregation, and zips the raw file.
    """
    if not os.path.exists(INPUT_CSV_PATH):
        print(f"Error: Input file '{INPUT_CSV_PATH}' not found.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output will be saved in the '{OUTPUT_DIR}' directory.")

    try:
        locations_df = pd.read_csv(INPUT_CSV_PATH)
        required_cols = {'latitude', 'longitude', 'elevation', 'station'}
        if not required_cols.issubset(locations_df.columns):
            print(f"Error: CSV must contain 'latitude', 'longitude', 'elevation', 'station'.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error reading or validating the CSV file: {e}", file=sys.stderr)
        sys.exit(1)

    client = cdsapi.Client()
    
    # --- NEW: Define the list of sky types to download ---
    sky_types_to_download = ["clear", "observed_cloud"]

    for index, location in locations_df.iterrows():
        station_name = location['station']
        lat = float(location['latitude'])
        lon = float(location['longitude'])
        alt = str(location['elevation'])
        sanitized_station_name = re.sub(r'[^\w\.-]', '_', station_name)
        
        # --- NEW: Loop through each sky type for the current station ---
        for sky_type in sky_types_to_download:
            try:
                print(f"\n--- Processing Station: {station_name}, Sky Type: {sky_type} ---")

                # UPDATED: Filenames now include the sky type
                raw_file = os.path.join(OUTPUT_DIR, f"raw_1min_{sanitized_station_name}_{sky_type}.csv")
                processed_file = os.path.join(OUTPUT_DIR, f"processed_10min_{sanitized_station_name}_{sky_type}.csv")

                request = {
                    "sky_type": sky_type, # UPDATED: Use the current sky type in the loop
                    "location": {"latitude": lat, "longitude": lon},
                    "altitude": alt,
                    "date": "2024-01-01/2024-12-31",
                    "time_step": "1minute",
                    "time_reference": "universal_time",
                    "format": "csv_expert"
                }

                print(f"Requesting 1-minute data...")
                client.retrieve(CAMS_DATASET, request, raw_file)
                print(f"Raw data downloaded to {raw_file}")

                print(f"Aggregating data to 10-minute intervals...")
                success = aggregate_to_10min(raw_file, processed_file)

                if success:
                    zip_and_delete_raw_file(raw_file)

            except Exception as e:
                print(f"A critical error occurred for station {station_name} with sky type {sky_type}: {e}", file=sys.stderr)
                print("Skipping to the next task.")
                continue

    print("\n--- All locations and sky types have been processed. ---")

if __name__ == "__main__":
    main()

