# Rain Forecast Grib

Python script for downloading, parsing, and aggregating short-term precipitation forecasts from IMGW ALARO GRIB data. Designed for integration with home automation systems (e.g. Home Assistant) to support smart irrigation based on predicted rainfall.

## Features

- Downloads 0–48h GRIB forecasts from IMGW (ALARO model)
- Extracts **convective** and **large-scale** precipitation values
- Aggregates forecast into a structured JSON (`forecast_result.json`)
- Automatically skips already downloaded files
- Cleans up GRIB files older than 24h
- Supports verbose/test modes for debugging

## Example Output

```json
{
  "forecast_prefix": "fc20250429_12",
  "total_precip_mm": 3.76,
  "details": [
    {
      "step": 3,
      "time": "2025-04-29T15:00:00.000000000",
      "precip_mm": 0.42,
      "convective": 0.00,
      "large_scale": 0.42
    },
    ...
  ]
}

Usage

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the script
python3 main.py

Configuration

Edit variables at the top of main.py:

    LAT, LON — your forecast location

    TEST_MODE — set False to enable real downloads

    VERBOSE — enable detailed logging to console

Integration Tips

Use the generated forecast_result.json in:

    Home Assistant (e.g. rest sensor)

    MQTT publishing

    Irrigation delay logic based on upcoming rainfall

Notes

    Uses cfgrib + xarray to read GRIB files

    Supports fallback logic if one variable is missing

    Filters out broken HTML "downloads" by checking file size and content-type

License

MIT License
