import pandas as pd
import xarray as xr
import glob
import os
import re
import warnings

# Suppress warnings for cleaner output, can be removed for debugging
warnings.filterwarnings('ignore', category=FutureWarning)

def clean_station_name(name):
    """
    A robust function to clean and standardize station names for reliable matching.
    It replaces underscores, removes special characters, converts to lowercase,
    and standardizes spacing.
    """
    # Replace underscores with spaces first
    cleaned_name = name.replace('_', ' ')
    # Keep only letters, numbers, and spaces, then convert to lowercase
    cleaned_name = re.sub(r'[^a-zA-Z0-9\s]', '', cleaned_name).lower()
    # Replace multiple spaces with a single space
    cleaned_name = re.sub(r'\s+', ' ', cleaned_name).strip()
    return cleaned_name

def compile_solar_data_to_netcdf(location_file, file_pattern, output_file, exclude_station=None):
    """
    Compiles multiple CSV files of solar radiation data into a single NetCDF file.

    This script reads station metadata (latitude, longitude, elevation, timezone)
    from a location file. It then finds all data files matching a specific pattern,
    treats the source time column as UTC, and calculates the corresponding local time.

    The final output is a NetCDF file containing the time-series data for all
    stations, with coordinates for time, station, latitude, longitude, and elevation.

    Args:
        location_file (str): Path to the CSV file with station metadata.
        file_pattern (str): Glob pattern to find the data CSV files (e.g., 'processed_*_cloud.csv').
        output_file (str): Path for the output NetCDF file.
        exclude_station (str, optional): Case-insensitive name of a station to exclude.
    """
    # --- 1. Read and Prepare Station Location Data ---
    try:
        locations_df = pd.read_csv(location_file)
        
        # Keep the original station name with its capitalization for the final output.
        locations_df['station_original'] = locations_df['station'].str.strip()
        # Create a robust, cleaned key for matching using the helper function.
        locations_df['station_key'] = locations_df['station_original'].apply(clean_station_name)
        
        # Calculate numeric UTC offset from timezone string (e.g., 'UTC+7' -> 7).
        locations_df['utc_offset'] = locations_df['timezone'].str.replace('UTC', '').astype(int)
        # Set the cleaned 'station_key' as the index for reliable lookups.
        locations_df.set_index('station_key', inplace=True)

    except FileNotFoundError:
        print(f"Error: Location file not found at '{location_file}'. Please ensure the file is in the correct directory.")
        return
    except Exception as e:
        print(f"An error occurred while reading or processing the location file: {e}")
        return

    # --- 2. Find Data Files ---
    all_files = glob.glob(file_pattern)
    if not all_files:
        print(f"Warning: No files found matching the pattern '{file_pattern}'.")
        return

    # --- 3. Process Each File and Collect Data ---
    all_data_list = []
    print("Starting to process station files...")
    for filepath in all_files:
        try:
            filename = os.path.basename(filepath)
            # Use a regular expression to robustly extract the station name part from the filename.
            match = re.search(r'processed_10min_(.*?)_observed_cloud\.csv', filename)
            if not match:
                print(f"  - Could not extract station name from '{filename}'. Skipping.")
                continue
            
            # Get the raw name part from the filename.
            station_name_from_file = match.group(1)
            # Create a cleaned key from the filename for matching.
            station_key = clean_station_name(station_name_from_file)

            # Skip the specified station (using the cleaned key for comparison).
            if exclude_station and station_key == clean_station_name(exclude_station):
                print(f"  - Excluding station: {station_name_from_file.replace('_', ' ')}")
                continue

            # Check if the cleaned key exists in the location data index.
            if station_key not in locations_df.index:
                print(f"  - Warning: No location info for '{station_name_from_file.replace('_', ' ')}' in '{location_file}'. Skipping file.")
                continue

            # If it exists, retrieve the station's data.
            station_info = locations_df.loc[station_key]
            # Get the original, properly-cased station name for use in the output file.
            original_station_name = station_info['station_original']

            # Read the required columns from the CSV.
            df = pd.read_csv(filepath, usecols=['time', 'GHI', 'DHI', 'BNI'])
            if df.empty:
                print(f"  - Warning: File '{filename}' is empty. Skipping.")
                continue

            # Rename BNI column to DNI as requested.
            df.rename(columns={'BNI': 'DNI'}, inplace=True)
            
            # --- CORRECTED Time Conversion ---
            utc_offset = station_info['utc_offset']
            # Treat the source 'time' column as UTC.
            df['time_utc'] = pd.to_datetime(df['time'], errors='coerce')
            # Calculate local time by ADDING the offset to UTC time.
            df['time_local'] = df['time_utc'] + pd.to_timedelta(utc_offset, unit='h')
            
            df.dropna(subset=['time_utc', 'time_local'], inplace=True)
            
            # Add the original, properly-cased station name to the DataFrame for later indexing.
            df['station'] = original_station_name
            
            all_data_list.append(df[['station', 'time_utc', 'time_local', 'GHI', 'DHI', 'DNI']])
            print(f"  + Successfully processed: {original_station_name}")

        except Exception as e:
            print(f"  - Error processing file '{filepath}': {e}")

    if not all_data_list:
        print("\nNo data was successfully processed. Aborting NetCDF file creation.")
        return

    # --- 4. Combine Data and Create xarray Dataset ---
    print("\nCombining data from all stations...")
    combined_df = pd.concat(all_data_list, ignore_index=True)
    combined_df.set_index(['station', 'time_utc'], inplace=True)

    print("Creating xarray Dataset...")
    ds = combined_df.to_xarray()

    # --- 5. Assign Coordinates and Attributes ---
    # We need to get the coordinates for the unique, original station names.
    unique_stations = ds.station.values
    station_keys_for_coords = [clean_station_name(s) for s in unique_stations]
    station_coords = locations_df.loc[station_keys_for_coords]

    ds = ds.assign_coords({
        'latitude': ('station', station_coords['latitude'].values),
        'longitude': ('station', station_coords['longitude'].values),
        'elevation': ('station', station_coords['elevation'].values)
    })

    # Rename the 'time_utc' dimension to just 'time' for convention.
    ds = ds.rename({'time_utc': 'time'})

    # Add descriptive attributes to the file and variables.
    ds.attrs = {
        'title': 'Compiled Solar Radiation Data from CAMS ECMWF',
        'institution': 'BMKG for WETSA Project',
        'source': f'Compiled from CSV files matching "{file_pattern}"',
        'history': f'Created on {pd.Timestamp.now(tz="utc").isoformat()} using a Python script.',
        'comment': 'Data includes GHI, DHI, and DNI for multiple stations in Indonesia.'
    }

    # Variable-specific attributes
    ds['time'].attrs = {'long_name': 'Time (UTC)', 'standard_name': 'time', 'axis': 'T'}
    ds['time_local'].attrs = {'long_name': 'Local Time at Station', 'description': 'Calculated local time corresponding to the UTC time dimension.'}
    ds['station'].attrs = {'long_name': 'Observation Station Name', 'cf_role': 'timeseries_id'}
    ds['latitude'].attrs = {'long_name': 'Latitude', 'units': 'degrees_north', 'standard_name': 'latitude'}
    ds['longitude'].attrs = {'long_name': 'Longitude', 'units': 'degrees_east', 'standard_name': 'longitude'}
    ds['elevation'].attrs = {'long_name': 'Elevation', 'units': 'm', 'positive': 'up'}
    ds['GHI'].attrs = {'long_name': 'Global Horizontal Irradiance', 'units': 'Wh/m^2', 'standard_name': 'surface_solar_radiation_downwards'}
    ds['DHI'].attrs = {'long_name': 'Diffuse Horizontal Irradiance', 'units': 'Wh/m^2', 'standard_name': 'diffuse_solar_radiation'}
    ds['DNI'].attrs = {'long_name': 'Direct Normal Irradiance', 'units': 'Wh/m^2', 'standard_name': 'direct_solar_radiation'}

    # --- 6. Save to NetCDF ---
    try:
        # --- FIX: Define encoding for BOTH time and time_local ---
        # This ensures both time variables use the same units and calendar.
        encoding_options = {
            'time': {
                'units': 'seconds since 1970-01-01 00:00:00',
                'calendar': 'proleptic_gregorian'
            },
            'time_local': {
                'units': 'seconds since 1970-01-01 00:00:00',
                'calendar': 'proleptic_gregorian'
            }
        }
        print(f"\nSaving data to '{output_file}'...")
        ds.to_netcdf(output_file, format='NETCDF4', engine='netcdf4', encoding=encoding_options)
        print("\n--- Success! ---")
        print(f"NetCDF file created at: {output_file}")
        print("\nDataset Summary:")
        print(ds)
    except Exception as e:
        print(f"\nAn error occurred while saving the NetCDF file: {e}")


if __name__ == '__main__':
    # --- Configuration ---
    # Path to the file containing station locations and metadata
    LOCATION_FILE = 'asrs_location.csv'
    # Pattern to find all the data files to be processed
    FILE_PATTERN = 'processed_10min_*_observed_cloud.csv'
    # Name of the output file
    OUTPUT_FILE = 'compiled_solar_data.nc'
    # Name of the station to exclude from the compilation
    EXCLUDE_STATION = 'Sleman'

    # --- Run the main function ---
    compile_solar_data_to_netcdf(
        location_file=LOCATION_FILE,
        file_pattern=FILE_PATTERN,
        output_file=OUTPUT_FILE,
        exclude_station=EXCLUDE_STATION
    )

