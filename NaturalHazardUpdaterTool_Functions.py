from __future__ import annotations
import os
import sys
import csv
import glob
import json
import time
import math
import random
import shutil
import logging
import datetime
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# HTTP & utilities
import requests
from urllib.parse import urlencode
from urllib.request import urlopen
from fnmatch import fnmatch

# Selenium (as in your original)
from selenium import webdriver
from selenium.common import exceptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as ec

# Optional GIS stack (fallback if ArcPy is unavailable)
ARCPY_AVAILABLE = False
try:
    import arcpy  # type: ignore
    ARCPY_AVAILABLE = True
except Exception:
    arcpy = None  # type: ignore

# Lazy imports for open-source GIS (only if needed)
def _lazy_import_gis():
    import importlib
    gp = importlib.import_module("geopandas")
    sh = importlib.import_module("shapely")
    pj = importlib.import_module("pyproj")
    try:
        # Prefer pyogrio (fast I/O)
        importlib.import_module("pyogrio")
        io_driver = "pyogrio"
    except Exception:
        # Fallback to Fiona
        importlib.import_module("fiona")
        io_driver = "fiona"
    return gp, sh, pj, io_driver

def _lazy_import_esridump():
    import importlib
    return importlib.import_module("esridump")

def _lazy_import_geopy():
    import importlib
    return importlib.import_module("geopy")


# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logger = logging.getLogger("hazard_tools")
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("[%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# ------------------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------------------
def writeMessages(log_path: str, message: str, print_bool: bool = True, msg_type: str = "info") -> None:
    """Write to a flat log file and show message through ArcPy (if available)."""
    os.makedirs(os.path.dirname(log_path or "."), exist_ok=True)
    with open(log_path, "a+", encoding="utf-8") as log_writer:
        log_writer.write(message + ("\n" if not message.endswith("\n") else ""))
    if msg_type == "info":
        logger.info(message) if print_bool else None
        if ARCPY_AVAILABLE:
            arcpy.AddMessage(message)  # type: ignore
    elif msg_type == "warning":
        logger.warning(message)
        if ARCPY_AVAILABLE:
            arcpy.AddWarning(message)  # type: ignore
    else:
        logger.error(message)
        if ARCPY_AVAILABLE:
            arcpy.AddError(message)  # type: ignore


# ------------------------------------------------------------------------------
# ArcPy helpers (with open-source fallbacks)
# ------------------------------------------------------------------------------
def addDTField(fc: str, field_name: str = "last_updated") -> None:
    """Add/update a DATE field with the current timestamp. ArcPy mode only."""
    now = datetime.datetime.now()
    if ARCPY_AVAILABLE:
        # Ensure field exists
        existing = [f.name for f in arcpy.ListFields(fc)]  # type: ignore
        if field_name not in existing:
            arcpy.AddField_management(fc, field_name, "DATE")  # type: ignore
        with arcpy.da.UpdateCursor(fc, [field_name]) as cur:  # type: ignore
            for _ in cur:
                cur.updateRow([now])
    else:
        raise RuntimeError("addDTField requires ArcPy. (Open-source path: manage timestamps in GeoDataFrame.)")


def createWorkspaces(workspace: str, hazard_nickname: str, today_string: str) -> Tuple[str, str, str, str, str]:
    """
    Creates processing/final folders and (ArcPy) FileGDBs OR (fallback) just folders.
    Returns: processing_folder, gis_data_folder, other_data_folder, processing_gdb_or_folder, final_gdb_or_folder
    """
    hazard_update_folder = os.path.join(workspace, hazard_nickname)

    processing_folder = os.path.join(hazard_update_folder, 'processing')
    final_folder = os.path.join(hazard_update_folder, 'final')
    gis_data_folder = os.path.join(processing_folder, 'gis_data')
    other_data_folder = os.path.join(processing_folder, 'other_data')

    for p in (processing_folder, final_folder, gis_data_folder, other_data_folder):
        os.makedirs(p, exist_ok=True)

    if ARCPY_AVAILABLE:
        processing_gdb_name = f"{hazard_nickname}_processing.gdb"
        processing_gdb = os.path.join(gis_data_folder, processing_gdb_name)
        if os.path.exists(processing_gdb):
            shutil.rmtree(processing_gdb)
        arcpy.CreateFileGDB_management(gis_data_folder, processing_gdb_name)  # type: ignore

        final_gdb_name = f"{hazard_nickname}_{today_string}.gdb"
        final_gdb = os.path.join(final_folder, final_gdb_name)
        if os.path.exists(final_gdb):
            shutil.rmtree(final_gdb)
        arcpy.CreateFileGDB_management(final_folder, final_gdb_name)  # type: ignore
        return processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb
    else:
        # Open-source: no FGDB, return folders; you can write .gpkg there.
        return processing_folder, gis_data_folder, other_data_folder, gis_data_folder, final_folder


def exportFeatureServiceLayer(mxd_or_aprx: str, df_or_map: Any, layer_name: str, output_gdb: str, out_layer_name: str) -> str:
    """
    ArcPy-only utility to copy a map layer into a FGDB.
    Supports:
      - ArcMap (arcpy.mapping)
      - ArcGIS Pro (arcpy.mp)
    """
    if not ARCPY_AVAILABLE:
        raise RuntimeError("exportFeatureServiceLayer requires ArcPy. Use extractGeoJson() open-source path instead.")

    try:
        # ArcGIS Pro path (arcpy.mp)
        import arcpy.mp as mp  # type: ignore
        aprx = mp.ArcGISProject(mxd_or_aprx)  # type: ignore
        m = aprx.listMaps(df_or_map)[0] if isinstance(df_or_map, str) else aprx.listMaps()[0]
        lyr = [l for l in m.listLayers() if l.name == layer_name][0]
        arcpy.CopyFeatures_management(lyr, os.path.join(output_gdb, out_layer_name))  # type: ignore
        return os.path.join(output_gdb, out_layer_name)
    except Exception:
        # ArcMap path (arcpy.mapping)
        layer_obj = arcpy.mapping.ListLayers(mxd_or_aprx, layer_name, df_or_map)[0]  # type: ignore
        feature_layer = "feature_layer_tmp"
        arcpy.MakeFeatureLayer_management(layer_obj, feature_layer)  # type: ignore
        out_path = os.path.join(output_gdb, out_layer_name)
        arcpy.CopyFeatures_management(feature_layer, out_path)  # type: ignore
        arcpy.Delete_management(feature_layer)  # type: ignore
        return out_path


# ------------------------------------------------------------------------------
# ArcGIS REST → features
# ------------------------------------------------------------------------------
def _divide_chunks(seq: Sequence[Any], n: int) -> Iterable[Sequence[Any]]:
    for i in range(0, len(seq), n):
        yield seq[i:i+n]


def extractGeoJson(
    layer_url: str,
    output_name: str,
    download_folder: str,
    sr_wkid: str | int = "3857",
    wait_time: Tuple[float, float] = (3, 2),
    out_format: str = "gdb_or_gpkg",
) -> Optional[str]:
    """
    Download an ArcGIS Feature Service layer into a local dataset.

    ArcPy mode:
      - Queries in chunks and merges into FileGDB feature class.

    Open-source mode:
      - Uses `esridump` to dump to GeoJSON, then GeoPandas to write a GeoPackage (.gpkg).

    Returns path to the final dataset, or None on error.
    """
    os.makedirs(download_folder, exist_ok=True)
    if ARCPY_AVAILABLE:
        # ----- ArcPy path (your original flow, slightly hardened) -----
        try:
            meta = requests.get(layer_url, params={"f": "json"}, timeout=60).json()
        except Exception as e:
            logger.error(f"Failed to reach layer metadata: {e}")
            return None

        if "error" in meta:
            logger.error(f"Layer error: {meta['error']}")
            return None

        geometry_type = meta.get("geometryType", "esriGeometryPolygon")
        fc_geometry_type = geometry_type.replace('esriGeometry', '') + 's'

        q_params = {'f': 'json', 'outFields': '*', 'returnIdsOnly': 'true', 'where': '1=1'}
        data = requests.get(f"{layer_url}/query", params=q_params, timeout=120).json()
        if "error" in data:
            logger.error(data["error"])
            return None

        object_ids = data.get("objectIds") or []
        logger.info(f"{len(object_ids):,} Features Found")
        feature_classes = []

        for i, chunk in enumerate(_divide_chunks(object_ids, 100)):
            time.sleep(wait_time[0] + random.random() * wait_time[1])
            out_json = f"{output_name}_{i}.json"
            out_json_path = os.path.join(download_folder, out_json)
            logger.info(f"Processing Subset {i+1}...")
            oid_list = ",".join(map(str, chunk))
            params = {
                'f': 'json',
                'returnGeometry': 'true',
                'geometryType': geometry_type,
                'returnDistinctValues': 'false',
                'returnIdsOnly': 'false',
                'returnCountOnly': 'false',
                'outFields': '*',
                'where': '1=1',
                'outSR': sr_wkid,
                'objectIds': oid_list
            }
            resp = requests.get(f"{layer_url}/query", params=params, timeout=300)
            resp.raise_for_status()
            with open(out_json_path, "wb") as f:
                f.write(resp.content)
            json_fc = arcpy.JSONToFeatures_conversion(out_json_path, rf"in_memory\subset_{i}")  # type: ignore
            feature_classes.append(json_fc)

        final_gdb_name = f"{output_name}_{fc_geometry_type}.gdb"
        final_gdb = os.path.join(download_folder, final_gdb_name)
        if os.path.exists(final_gdb):
            shutil.rmtree(final_gdb)
        arcpy.CreateFileGDB_management(download_folder, final_gdb_name)  # type: ignore

        sr = arcpy.SpatialReference(int(sr_wkid))  # type: ignore
        arcpy.CreateFeatureclass_management(final_gdb, output_name, spatial_reference=sr)  # type: ignore
        out_fc = os.path.join(final_gdb, output_name)
        arcpy.Merge_management(feature_classes, out_fc)  # type: ignore

        for fc in feature_classes:
            arcpy.Delete_management(fc)  # type: ignore

        logger.info(f"Done. Output: {out_fc}")
        return out_fc

    # ----- Open-source path -----
    gp, sh, pj, io_driver = _lazy_import_gis()
    esridump = _lazy_import_esridump()

    # Dump to GeoJSON
    geojson_path = os.path.join(download_folder, f"{output_name}.geojson")
    if os.path.exists(geojson_path):
        os.remove(geojson_path)

    # esridump handles pagination, geometry conversion to GeoJSON
    logger.info("Dumping features with esridump...")
    with open(geojson_path, "w", encoding="utf-8") as f:
        for feature in esridump.search(layer_url, where="1=1", outSR=sr_wkid):
            f.write(json.dumps(feature) + "\n")  # newline-delimited GeoJSON Features

    # Read NDJSON into GeoDataFrame
    logger.info("Loading GeoJSON into GeoPandas...")
    # Build a proper FeatureCollection in-memory
    with open(geojson_path, "r", encoding="utf-8") as f:
        feats = [json.loads(line) for line in f if line.strip()]
    fc = {"type": "FeatureCollection", "features": feats}
    gdf = gp.GeoDataFrame.from_features(fc, crs=f"EPSG:{int(sr_wkid)}")

    # Write to GeoPackage
    out_gpkg = os.path.join(download_folder, f"{output_name}.gpkg")
    if os.path.exists(out_gpkg):
        os.remove(out_gpkg)
    gdf.to_file(out_gpkg, layer=output_name, driver="GPKG")
    logger.info(f"Done. Output: {out_gpkg}")
    return out_gpkg


# ------------------------------------------------------------------------------
# Table → Points (ArcPy or GeoPandas)
# ------------------------------------------------------------------------------
def tableToPoints(
    input_header: List[str],
    data: List[List[str]],
    lat_field: str,
    long_field: str,
    sr_wkid: int | str,
    processing_target: str,
    out_name: str,
    open_source_output: Optional[str] = None
) -> Tuple[str, List[List[str]]]:
    """
    Create a point dataset from tabular rows.

    ArcPy mode:
      - Writes a feature class into `processing_target` (a FileGDB path).

    Open-source mode:
      - Writes a GeoPackage (or Shapefile) to `open_source_output` (path to .gpkg).
      - Returns that path.
    """
    # Normalize headers (no leading digit)
    header = [("_" + h) if h and h[0].isdigit() else h for h in input_header]
    header_size = len(header)

    # Pad short rows, track max field lengths (for ArcPy TEXT sizes)
    max_lens: Dict[str, int] = {}
    for row in data:
        while len(row) < header_size:
            row.append("")
        for i, v in enumerate(row[:header_size]):
            ml = max_lens.get(header[i], 0)
            max_lens[header[i]] = max(ml, len(v) + 1)

    lat_idx = header.index(lat_field)
    lon_idx = header.index(long_field)

    missed: List[List[str]] = []

    if ARCPY_AVAILABLE:
        temp_fc = os.path.join(processing_target, out_name)
        sr = arcpy.SpatialReference(int(sr_wkid))  # type: ignore
        arcpy.CreateFeatureclass_management(processing_target, out_name, "POINT", spatial_reference=sr)  # type: ignore
        for fld, flen in max_lens.items():
            arcpy.AddField_management(temp_fc, fld, "TEXT", field_length=min(flen, 255))  # type: ignore

        with arcpy.da.InsertCursor(temp_fc, header + ['SHAPE@X', 'SHAPE@Y']) as cur:  # type: ignore
            for row in data:
                try:
                    if row[lat_idx] != "" and row[lon_idx] != "":
                        lat = float(row[lat_idx]); lon = float(row[lon_idx])
                        cur.insertRow(row[:header_size] + [lon, lat])
                except Exception:
                    missed.append(row)
        return temp_fc, missed

    # Open-source path
    if not open_source_output:
        raise RuntimeError("open_source_output (.gpkg) path is required when ArcPy is not available.")

    gp, sh, pj, io_driver = _lazy_import_gis()
    import pandas as pd

    df = pd.DataFrame([r[:header_size] for r in data], columns=header)
    def _to_float(x):
        try:
            return float(x)
        except Exception:
            return None
    df["_lat"] = df[lat_field].map(_to_float)
    df["_lon"] = df[long_field].map(_to_float)

    bad = df[df["_lat"].isna() | df["_lon"].isna()]
    if not bad.empty:
        missed = bad[header].values.tolist()
    good = df.dropna(subset=["_lat", "_lon"])
    gdf = gp.GeoDataFrame(good, geometry=gp.points_from_xy(good["_lon"], good["_lat"]), crs=f"EPSG:{int(sr_wkid)}")

    # Write or append layer
    if open_source_output.lower().endswith(".gpkg"):
        mode = "w"
        if os.path.exists(open_source_output):
            os.remove(open_source_output)
        gdf.to_file(open_source_output, layer=out_name, driver="GPKG")
        return open_source_output, missed
    else:
        # default to shapefile folder
        shp_path = open_source_output if open_source_output.lower().endswith(".shp") else f"{open_source_output}.shp"
        gdf.to_file(shp_path)
        return shp_path, missed


# ------------------------------------------------------------------------------
# Field checks
# ------------------------------------------------------------------------------
def checkMissingFields(expected_fields: Sequence[str], available_fields: Sequence[str]) -> Tuple[bool, str]:
    missing = [f for f in expected_fields if f not in available_fields]
    if missing:
        return False, f"{len(missing)} Missing Fields in Input Data:\n\t" + "\n\t".join(missing)
    return True, ""


# ------------------------------------------------------------------------------
# Geocoding (HERE v7 by default, with Nominatim fallback)
# ------------------------------------------------------------------------------
def forwardGeocode(full_address: str, here_api_key: Optional[str] = None, provider: str = "here") -> Tuple[Optional[float], Optional[float]]:
    """
    Geocode an address.
    provider="here" (v7; recommended) or "nominatim" (open)
    """
    provider = provider.lower()
    if provider == "here":
        api_key = here_api_key or os.getenv("HERE_API_KEY")
        if not api_key:
            # fallback to nominatim
            provider = "nominatim"
        else:
            # HERE v7 endpoint
            url = "https://geocode.search.hereapi.com/v1/geocode"
            params = {"q": full_address, "apiKey": api_key}
            try:
                r = requests.get(url, params=params, timeout=30)
                r.raise_for_status()
                js = r.json()
                items = js.get("items") or []
                if not items:
                    return None, None
                pos = items[0]["position"]
                return pos.get("lat"), pos.get("lng")
            except Exception as e:
                logger.warning(f"HERE geocoding failed ({e}), falling back to Nominatim.")
                provider = "nominatim"

    # Nominatim fallback (respect usage policy; set a UA)
    try:
        from geopy.geocoders import Nominatim  # type: ignore
    except Exception:
        _lazy_import_geopy()
        from geopy.geocoders import Nominatim  # type: ignore

    geolocator = Nominatim(user_agent="hazard-tools/1.0")
    try:
        loc = geolocator.geocode(full_address, timeout=30)
        if not loc:
            return None, None
        return loc.latitude, loc.longitude
    except Exception:
        logger.info(f"Unable to geocode [{full_address}]")
        return None, None


# ------------------------------------------------------------------------------
# Selenium download waiter (unchanged logic, cleaned a bit)
# ------------------------------------------------------------------------------
def clickToDownloadFile(download_button: WebElement, output_download_folder: str) -> None:
    """Click a download button and block until the file is present and stable in size."""
    download_button.click()
    time.sleep(1.5)

    # Wait for any file to appear
    for _ in range(600):  # up to ~60s
        if os.listdir(output_download_folder):
            break
        time.sleep(0.1)

    # Wait for temp files to disappear
    temp_ext = (".crdownload", ".tmp", ".part")
    while True:
        names = os.listdir(output_download_folder)
        if names and not any(n.endswith(temp_ext) for n in names):
            break
        time.sleep(0.2)

    # Wait for size to stabilize
    file_path = os.path.join(output_download_folder, os.listdir(output_download_folder)[0])
    prev = -1
    while True:
        size = os.path.getsize(file_path)
        if size == prev:
            break
        prev = size
        print(".", end="", flush=True)
        time.sleep(0.5)
    print("")


# ------------------------------------------------------------------------------
# Record correction (ArcPy only)
# ------------------------------------------------------------------------------
def recordCorrector(fc: str, corrections_list: List[Dict[str, str]]) -> None:
    """
    Apply simple field updates via attribute query. ArcPy only.
    corrections_list = [
        {"field": "Phone", "query": "Name = 'SAN DIEGO COUNTY FPD'", "value": "(858) 974-5999"},
        ...
    ]
    """
    if not ARCPY_AVAILABLE:
        raise RuntimeError("recordCorrector requires ArcPy. For open-source, update a GeoDataFrame and rewrite file.")

    for c in corrections_list:
        field = c["field"]; query = c["query"]; value = c["value"]
        initial = int(arcpy.GetCount_management(fc).getOutput(0))  # type: ignore
        layer = "feature_layer_corr"
        arcpy.MakeFeatureLayer_management(fc, layer)  # type: ignore
        arcpy.SelectLayerByAttribute_management(layer, "NEW_SELECTION", query)  # type: ignore
        selected = int(arcpy.GetCount_management(layer).getOutput(0))  # type: ignore
        if selected == 0:
            logger.warning(f"No records matched: {query}")
        else:
            logger.info(f"Setting [{field}] to [{value}] for {selected} record(s)")
            with arcpy.da.UpdateCursor(layer, [field]) as cur:  # type: ignore
                for _ in cur:
                    cur.updateRow([value])
        arcpy.Delete_management(layer)  # type: ignore
