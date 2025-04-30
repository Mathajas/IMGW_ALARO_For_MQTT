from datetime import datetime, timedelta, timezone
import os
import requests
import xarray as xr
import json

# === Configuration constants ===
LAT = 51.0630  # Latitude of target location (Nadolice Małe)
LON = 17.1930  # Longitude of target location (Nadolice Małe)
DOWNLOAD_DIR = "./downloads"  # Directory for GRIB files
BASE_URL = "https://danepubliczne.imgw.pl/datastore/getfiledown/Oper/ALADIN/ALARO_pub/"  # GRIB file base URL
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PyIMGW/1.0)"}  # Required header to access IMGW data
OUTPUT_JSON = "forecast_result.json"  # Output JSON file for precipitation results
TEST_MODE = True  # If True, skip actual downloading
VERBOSE = False  # Print all log messages if True, only errors/warnings if False


def get_filename(prefix, step):
    return f"{prefix}+{step:03d}gl"


def log(msg, force=False):
    if VERBOSE or force:
        print(msg)


def download_file(filename):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    local_path = os.path.join(DOWNLOAD_DIR, filename)

    if os.path.exists(local_path):
        log(f"✅ Using existing file: {filename}")
        return local_path

    if TEST_MODE:
        log(f"❌ Missing file for test: {filename}", force=True)
        return None

    url = BASE_URL + filename
    try:
        r = requests.get(url, headers=HEADERS)
        content_type = r.headers.get("Content-Type", "")
        if r.status_code == 200 and content_type.startswith("application"):
            if len(r.content) > 1000:
                with open(local_path, 'wb') as f:
                    f.write(r.content)
                log(f"⬇️  Downloaded: {filename}")
                return local_path
            else:
                log(f"⚠️  Too small — probably HTML error page: {filename}", force=True)
        else:
            log(f"⚠️  Invalid content-type or response: {filename} ({content_type})", force=True)
    except Exception as e:
        log(f"❌ Request error: {e}", force=True)
    return None


def inspect_file_variables(file_path):
    # Debug tool for inspecting GRIB contents
    try:
        ds = xr.open_dataset(file_path, engine="cfgrib")
        print(f"\n📊 Variables and levels in {file_path}:")
        for var in ds.variables:
            print(f"- {var}")
        print(f"\n🔍 Available attributes:")
        for key in ds.attrs:
            print(f"  {key}: {ds.attrs[key]}")
        print(f"\n🧪 Coordinates:")
        for coord in ds.coords:
            print(f"- {coord}")
    except Exception as e:
        print(f"❌ Failed to open raw dataset: {e}")


def read_precipitation(file_path, lat, lon):
    # Extract convective and large-scale precipitation from GRIB file for nearest grid point
    try:
        ds1 = xr.open_dataset(file_path, engine="cfgrib", backend_kwargs={
            "filter_by_keys": {"typeOfLevel": "surface", "shortName": "acpcp"}
        })
        acpcp = ds1['acpcp'].sel(latitude=lat, longitude=lon, method='nearest').values
    except Exception:
        acpcp = 0.0

    try:
        ds2 = xr.open_dataset(file_path, engine="cfgrib", backend_kwargs={
            "filter_by_keys": {"typeOfLevel": "surface", "shortName": "lsp"}
        })
        lsp = ds2['lsp'].sel(latitude=lat, longitude=lon, method='nearest').values
        time = str(ds2.coords['valid_time'].values)
    except Exception:
        lsp = 0.0
        time = None

    total = float(acpcp) + float(lsp)
    return float(acpcp), float(lsp), total, time


def find_valid_prefix():
    # Look for the newest available forecast prefix
    today = datetime.now(timezone.utc).date()
    for delta in range(0, 5):
        check_date = today - timedelta(days=delta)
        for hour in [12, 0]:
            prefix = check_date.strftime(f"fc%Y%m%d_{hour:02d}")
            test_file = get_filename(prefix, 0)
            log(f"🔍 Testing: {test_file}")
            if download_file(test_file):
                return prefix
    print("❌ No valid forecast found.")
    return None


def cleanup_download_dir():
    # Remove GRIB files older than 24 hours
    if not TEST_MODE:
        if os.path.exists(DOWNLOAD_DIR):
            now = datetime.now()
            for f in os.listdir(DOWNLOAD_DIR):
                fpath = os.path.join(DOWNLOAD_DIR, f)
                if os.path.isfile(fpath):
                    age = now - datetime.fromtimestamp(os.path.getmtime(fpath))
                    if age > timedelta(hours=24):
                        os.remove(fpath)
                        log(f"🧹 Deleted old file: {f}")


def main():
    cleanup_download_dir()
    prefix = find_valid_prefix()
    if not prefix:
        return

    print(f"🕒 Using forecast prefix: {prefix}")
    total_precip = 0.0
    new_results = []

    # Process GRIB files in 3-hour steps from 0 to 48
    for step in range(0, 49, 3):
        fname = get_filename(prefix, step)
        fpath = os.path.join(DOWNLOAD_DIR, fname)
        if os.path.exists(fpath):
            log(f"✅ Already exists: {fname}")
        else:
            if not download_file(fname):
                log(f"⏩ Skipping step {step}", force=True)
                continue

        acpcp, lsp, total, timestamp = read_precipitation(fpath, LAT, LON)
        if timestamp:
            log(f"{timestamp[:16]} — conv: {acpcp:.2f} mm, large: {lsp:.2f} mm, total: {total:.2f} mm")
        else:
            log(f"⚠️  Failed to read precipitation at step {step}", force=True)

        new_results.append({
            "step": step,
            "time": timestamp,
            "precip_mm": total,
            "convective": acpcp,
            "large_scale": lsp
        })

        total_precip += total

    print(f"\n🔢 Total 0–48h precipitation: {total_precip:.2f} mm")

    # Load existing forecast result JSON if it exists
    existing = {}
    if os.path.exists(OUTPUT_JSON):
        try:
            with open(OUTPUT_JSON, 'r') as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    # Replace existing forecast if prefix changed, or update step values
    if existing.get("forecast_prefix") != prefix:
        existing = {
            "forecast_prefix": prefix,
            "details": []
        }

    # Merge new results with existing ones by step
    merged = {item["step"]: item for item in existing.get("details", [])}
    for new in new_results:
        merged[new["step"]] = new

    # Sort and update final structure
    details_sorted = [merged[step] for step in sorted(merged)]
    existing["forecast_prefix"] = prefix
    existing["total_precip_mm"] = sum([d["precip_mm"] for d in details_sorted])
    existing["details"] = details_sorted

    with open(OUTPUT_JSON, 'w') as f:
        json.dump(existing, f, indent=2)
        print(f"📂 Saved results to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
