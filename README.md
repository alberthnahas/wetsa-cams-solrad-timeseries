# WETSA WP1: CAMS Solar Radiation Validation Toolkit

A collection of tools for downloading, processing, and validating CAMS solar radiation data against ground-based measurements as part of the WETSA project.


## Description

This repository contains Python scripts developed for **Work Package 1 (WP1) - Gridded Solar Observations and Nowcasts** of the **Weather for Energy Transition in Southeast Asia (WETSA)** project. The WETSA project is a collaborative effort between Indonesia's **Meteorology, Climatology, and Geophysics Agency (BMKG)** and the **Australian Bureau of Meteorology (BoM)**, aimed at building capacity to support improved energy system planning and management in the region.

The primary goal of these tools is to validate satellite-derived solar irradiance data from the Copernicus Atmosphere Monitoring Service (CAMS) against high-quality ground observations from BMKG's surface monitoring network. This validation is a key step in developing a robust, bias-corrected solar observation system for Indonesia.

### Features

* **`codes/get-cams-solrad-ts.py`**: Downloads 1-minute resolution solar radiation time-series data (GHI, DHI, BNI) from the [CAMS](https://ads.atmosphere.copernicus.eu/cdsapp#!/dataset/cams-solar-radiation-timeseries) dataset for a list of specified locations. It automatically aggregates the data to 10-minute averages and archives the raw downloads.
* **`codes/solrad-compare.py`**: Performs a detailed comparison between the processed 10-minute CAMS data and quality-controlled ground-based pyranometer data. It generates a comprehensive set of visualizations and statistical analyses to assess the performance of the CAMS model.


## Badges

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg?style=for-the-badge)](https://www.python.org/downloads/)


## Visuals

The `solrad-compare.py` script generates a multi-panel plot for each location, providing a comprehensive visual analysis. An example output file would be `solar_radiation_comparison_Tangerang_Selatan.png`.

The plot includes:
* **Bias Time-Series**: Shows the difference (CAMS - Ground) over time for GHI, DHI, and DNI.
* **Scatter Comparison**: Compares CAMS vs. Ground measurements for each component, including a 1:1 line and a linear regression fit with R² value.
* **Bias vs. Cloud Coverage**: Investigates the impact of cloud cover (from CAMS) on GHI bias.
* **GHI/DHI Ratio**: Plots the ratio of ground-measured GHI to DHI over time.

<img src="solar_radiation_comparison_Padang_Pariaman.png" alt="Sample Comparison Plot" width="800"/>

## Installation

### Requirements

  * Python 3.9+
  * A Copernicus Climate Data Store (CDS) API key.
  * The required Python packages are listed in `requirements.txt`.

### Steps

1.  **Clone the repository:**

    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```

2.  **Set up a virtual environment (recommended):**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

    The `requirements.txt` file should contain:

    ```
    cdsapi
    pandas
    numpy
    matplotlib
    scipy
    ```

4.  **Configure your CDS API key:**
    Create a file named `.cdsapirc` in your home directory with your CDS URL and API key. Follow the instructions from the [CDS API documentation](https://cds.climate.copernicus.eu/api-how-to).


## Usage

### 1\. Prepare Input Files

  * **Locations CSV**: Populate the `input/asrs_location.csv` file with the ground stations you want to process. It must contain the columns: `latitude`, `longitude`, `elevation`, and `station`.
  * **Ground Data**: Place your quality-controlled, flagged ground measurement CSV files in the project's root directory. The comparison script expects filenames in the format `QC_{location}_2024_flagged.csv`, where `{location}` matches a `station` name from your input CSV.

### 2\. Download CAMS Data

Run the download script from the root directory. It will read the locations from `input/asrs_location.csv` and save outputs to a new `solar_data_output/` directory.

```bash
python codes/get-cams-solrad-ts.py
```

### 3\. Run Comparison and Generate Plots

Execute the comparison script. It will automatically find the matching CAMS and ground data files, perform the analysis, and save the output plots in the root directory.

```bash
python codes/solrad-compare.py
```


## Support

* For bugs, questions, or feature requests, please **open an issue** on the Github issue tracker.
* For inquiries related to this repository, please contact **Alberth Nahas** (alberth.nahas@bmkg.go.id).
* For specific inquiries about the WETSA project, you may contact **Vincent Villani** (vincent.villani@bom.gov.au).


## Roadmap

This toolkit is an initial component of WETSA WP1. Future development will focus on the key project outcomes:

* **GSO System Integration**: Updating the Bureau of Meteorology's Gridded Solar Observations (GSO) system to run over the Indonesian domain;
* **Bias Correction**: Using the validation results from this toolkit to train and update a bias correction model for Indonesia;
* **Historical Data Processing**: Generating a historical GSO dataset for Indonesia to support further analysis;
* **Software Handover**: Delivering the updated GSO software, documentation, and training guides to BMKG to build operational capacity.


## Contributing

Contributions are welcome! This project is a collaborative effort between BoM and BMKG.

If you wish to contribute, please follow these steps:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes.
4.  Submit a merge request with a clear description of your changes.
5.  For major changes, please open an issue first to discuss what you would like to change.


## Authors and Acknowledgment

This work is a product of the **WETSA (Weather for Energy Transition in Southeast Asia)** project.

* **Implementing Agencies**:
    * Bureau of Meteorology (BoM), Australia
    * Badan Meteorologi, Klimatologi, dan Geofisika (BMKG), Indonesia

* **Funding**: This project is supported by the Australian Government's Department of Foreign Affairs and Trade (DFAT).


## License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.


## Project Status

**Active**. This project is currently in the technical delivery phase (Phase 4), which is scheduled from **March to December 2025**.

## Repository

Click [here](https://cews.bmkg.go.id/tempatirk/WETSA/SOLAR_OBS/COMPARED_CAMS/) to access the generated plots.
