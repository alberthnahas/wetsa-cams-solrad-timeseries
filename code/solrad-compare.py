import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats
import os

def analyze_and_plot_solar_data(ground_filepath, cams_filepath, location_name, output_filename):
    """
    Main function to load, process, and visualize solar radiation data,
    with explicit UTC timezone handling and unit correction.

    Args:
        ground_filepath (str): Path to the ground-based measurement CSV file.
        cams_filepath (str): Path to the CAMS model data CSV file.
        location_name (str): The name of the location for the plot title.
        output_filename (str): Filename for the output PNG plot.
    """

    # --- 1. Load and Clean Ground-Based Data (W/m^2) ---
    try:
        ground_df = pd.read_csv(ground_filepath)
        dt_series = pd.to_datetime(ground_df['Datetime (UTC)'])
        if dt_series.dt.tz is None:
            ground_df['timestamp'] = dt_series.dt.tz_localize('UTC')
            print("Ground data timestamp was naive, localized to UTC.")
        else:
            ground_df['timestamp'] = dt_series.dt.tz_convert('UTC')
            print("Ground data timestamp is timezone-aware, converted to UTC.")
        ground_df.set_index('timestamp', inplace=True)
    except Exception as e:
        print(f"An error occurred while reading the ground data file: {e}")
        return

    flag_cols = [
        'flag_ghi', 'flag_dhi', 'flag_dni', 'flag_ghi_rare',
        'flag_dhi_rare', 'flag_dni_rare', 'flag_comp1', 'flag_comp2'
    ]
    existing_flag_cols = [col for col in flag_cols if col in ground_df.columns]
    initial_rows = len(ground_df)
    cleaned_ground_df = ground_df[ground_df[existing_flag_cols].sum(axis=1) == 0].copy()
    print(f"Ground data: Loaded {initial_rows} rows, {len(cleaned_ground_df)} rows remain after QC filtering.")
    cleaned_ground_df.rename(columns={'GHI': 'GHI_ground', 'DHI': 'DHI_ground', 'DNI': 'DNI_ground'}, inplace=True)
    ground_final_df = cleaned_ground_df[['GHI_ground', 'DHI_ground', 'DNI_ground']]

    # --- 2. Load CAMS Model Data (Wh/m^2) ---
    try:
        cams_df = pd.read_csv(cams_filepath)
        dt_series_cams = pd.to_datetime(cams_df['time'])
        if dt_series_cams.dt.tz is None:
            cams_df['timestamp'] = dt_series_cams.dt.tz_localize('UTC')
            print("CAMS data timestamp was naive, localized to UTC.")
        else:
            cams_df['timestamp'] = dt_series_cams.dt.tz_convert('UTC')
            print("CAMS data timestamp is timezone-aware, converted to UTC.")
        cams_df.set_index('timestamp', inplace=True)
    except Exception as e:
        print(f"An error occurred while reading the CAMS data file: {e}")
        return

    conversion_factor = 60
    rad_cols_cams = ['GHI', 'DHI', 'BNI']
    for col in rad_cols_cams:
        if col in cams_df.columns:
            cams_df[col] = cams_df[col] * conversion_factor
    print(f"\nApplied unit conversion to CAMS data (assuming Wh/m^2 -> W/m^2) by multiplying by {conversion_factor}.")

    cloud_col_name = 'Cloud coverage'
    has_cloud_data = cloud_col_name in cams_df.columns
    cams_rename_dict = {'GHI': 'GHI_cams', 'DHI': 'DHI_cams', 'BNI': 'DNI_cams'}
    cams_cols_to_select = ['GHI_cams', 'DHI_cams', 'DNI_cams']
    if has_cloud_data:
        cams_rename_dict[cloud_col_name] = 'cloud_cover'
        cams_cols_to_select.append('cloud_cover')

    cams_df.rename(columns=cams_rename_dict, inplace=True)
    cams_final_df = cams_df[cams_cols_to_select]

    # --- 3. Merge and Analyze ---
    merged_df = pd.merge(ground_final_df, cams_final_df, left_index=True, right_index=True, how='inner')
    merged_df.dropna(inplace=True)
    print(f"Merged data: Found {len(merged_df)} common data points for comparison after filtering.")

    if merged_df.empty:
        print("No common data points found. Cannot generate plot.")
        return

    merged_df['GHI_bias'] = merged_df['GHI_cams'] - merged_df['GHI_ground']
    merged_df['DHI_bias'] = merged_df['DHI_cams'] - merged_df['DHI_ground']
    merged_df['DNI_bias'] = merged_df['DNI_cams'] - merged_df['DNI_ground']
    merged_df['GHI_DHI_ratio'] = merged_df['GHI_ground'] / merged_df['DHI_ground'].replace(0, np.nan)


    # --- 4. Create Visualization ---
    num_rows = 4 if has_cloud_data else 3
    fig = plt.figure(figsize=(22, 5 * num_rows))
    # The plot title is now dynamic based on the location_name parameter.
    fig.suptitle(f'Comparison of CAMS Model vs. Ground Measurements in {location_name} (2024)', fontsize=16)

    outer_gs = gridspec.GridSpec(num_rows, 1, figure=fig, hspace=0.6)

    components = ['GHI', 'DHI', 'DNI']
    colors = ['royalblue', 'darkorange', 'seagreen']
    vmax = 500

    for i, comp in enumerate(components):
        inner_gs = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=outer_gs[i], wspace=0.2, width_ratios=[3, 2])

        bias_ax = fig.add_subplot(inner_gs[0])
        scatter_ax = fig.add_subplot(inner_gs[1])

        # Bias Plot (as scatter)
        bias_ax.scatter(merged_df.index, merged_df[f'{comp}_bias'], label=f'{comp} Bias (CAMS - Ground)', s=1, alpha=0.5, color=colors[i])
        bias_ax.axhline(0, color='black', linestyle='--', linewidth=1)
        bias_ax.set_ylabel(f'Bias {comp} [W/m²]')
        bias_ax.set_title(f'{comp} Bias')
        bias_ax.grid(True, linestyle=':', alpha=0.7)
        bias_ax.legend(markerscale=5)

        # Comparison Scatter Plot
        x_data = merged_df[f'{comp}_ground']
        y_data = merged_df[f'{comp}_cams']
        abs_bias = abs(merged_df[f'{comp}_bias'])

        # Filter out NaN or infinite values before linear regression
        valid_data = pd.concat([x_data, y_data], axis=1).dropna()
        if valid_data.empty:
            print(f"Skipping regression for {comp} due to lack of valid data.")
            continue
            
        slope, intercept, r_value, p_value, std_err = stats.linregress(valid_data[f'{comp}_ground'], valid_data[f'{comp}_cams'])
        r_squared = r_value**2

        sc = scatter_ax.scatter(x_data, y_data, c=abs_bias, cmap='viridis', s=10, alpha=0.7, vmin=0, vmax=vmax)
        cbar = fig.colorbar(sc, ax=scatter_ax)
        cbar.set_label('Absolute Bias [W/m²]')

        max_val = max(x_data.max(), y_data.max())
        line_x = np.array([0, max_val])
        line_y = slope * line_x + intercept
        scatter_ax.plot(line_x, line_y, 'r-', linewidth=2, label=f'Fit: y={slope:.2f}x + {intercept:.1f}\nR²={r_squared:.3f}')
        scatter_ax.plot([0, max_val], [0, max_val], 'k--', linewidth=1.5, label='1:1 Line')

        scatter_ax.set_xlabel(f'Measured {comp} (Ground) [W/m²]')
        scatter_ax.set_ylabel(f'Calculated {comp} (CAMS) [W/m²]')
        scatter_ax.set_title(f'{comp} Comparison (n={len(merged_df)})')
        scatter_ax.legend()
        scatter_ax.grid(True, linestyle=':', alpha=0.5)
        scatter_ax.set_aspect('equal', adjustable='box')
        scatter_ax.set_xlim(0, max_val * 1.05)
        scatter_ax.set_ylim(0, max_val * 1.05)

    # --- Last Row with Cloud Bias and GHI/DHI Ratio ---
    if has_cloud_data:
        last_row_gs = gridspec.GridSpecFromSubplotSpec(1, 2, subplot_spec=outer_gs[3], wspace=0.2)

        # GHI Bias vs Cloud Coverage Plot
        ax_cloud_bias = fig.add_subplot(last_row_gs[0])
        sc_cloud = ax_cloud_bias.scatter(
            merged_df['cloud_cover'],
            merged_df['GHI_bias'],
            alpha=0.3,
            c=merged_df['GHI_bias'],
            cmap='coolwarm_r',
            vmin=-vmax,
            vmax=vmax
        )
        ax_cloud_bias.axhline(0, color='black', linestyle='--', linewidth=1)
        ax_cloud_bias.set_xlabel('Cloud Coverage (from CAMS, %)')
        ax_cloud_bias.set_ylabel('GHI Bias [W/m²]')
        ax_cloud_bias.set_title('GHI Bias vs. Cloud Coverage')
        ax_cloud_bias.grid(True, linestyle=':', alpha=0.7)
        cbar_cloud = fig.colorbar(sc_cloud, ax=ax_cloud_bias)
        cbar_cloud.set_label('GHI Bias [W/m²]')

        # GHI/DHI Ratio Plot
        ax_ratio = fig.add_subplot(last_row_gs[1])
        ax_ratio.scatter(merged_df.index, merged_df['GHI_DHI_ratio'], s=1, alpha=0.5, color='purple')
        ax_ratio.set_title('GHI to DHI Ratio from Ground Measurements')
        ax_ratio.set_ylabel('Ratio GHI / DHI')
        ax_ratio.set_xlabel('Date')
        ax_ratio.grid(True, linestyle=':', alpha=0.7)
        ax_ratio.set_ylim(bottom=0)

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # --- 5. Save and Close Plot ---
    plt.savefig(output_filename, dpi=300)
    print(f"\nPlot successfully saved to {output_filename}")
    plt.close(fig) # Close the figure to free up memory


if __name__ == '__main__':
    # List of locations to process.
    locations = [
        'Banjarbaru', 'Batam', 'Bengkulu', 'Bogor', 'Bone_Bolango',
        'Deli_Serdang', 'Jayapura', 'Jembrana', 'Kampar', 'Kupang',
        'Lombok_Barat', 'Mamuju', 'Maros', 'Mempawah', 'Merauke',
        'Minahasa_Utara', 'Muaro_Jambi', 'Nunukan', 'Padang_Pariaman',
        'Palangkaraya', 'Palembang', 'Palu', 'Pesawaran', 'Samarinda',
        'Semarang', 'Seram_Bagian_Barat', 'Sleman', 'Tangerang_Selatan',
        'Ternate'
    ]

    # Loop through each location to generate a plot.
    for location in locations:
        print(f"--- Processing data for {location.replace('_', ' ')} ---")

        # Construct filenames dynamically
        ground_file = f'QC_{location}_2024_flagged.csv'
        cams_file = f'processed_10min_{location}_observed_cloud.csv'
        output_file = f'solar_radiation_comparison_{location}.png'
        
        # Make a nice name for the plot title by replacing underscores
        location_title_name = location.replace('_', ' ')

        # Check if both required files exist before proceeding
        if not os.path.exists(ground_file):
            print(f"Warning: Ground data file not found, skipping {location}: {ground_file}")
            continue
        if not os.path.exists(cams_file):
            print(f"Warning: CAMS data file not found, skipping {location}: {cams_file}")
            continue

        # Call the main function with the dynamic file paths and names
        try:
            analyze_and_plot_solar_data(ground_file, cams_file, location_title_name, output_file)
        except Exception as e:
            print(f"An unexpected error occurred while processing {location}: {e}")

    print("\n--- All locations processed. ---")

