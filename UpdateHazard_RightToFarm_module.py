import os
import re
import time
import datetime

# Selenium 4 imports (modern)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.chrome.service import Service as ChromeService

from zipfile import ZipFile

# Pull in helpers + ARCPY_AVAILABLE flag + clickToDownloadFile, createWorkspaces, writeMessages, addDTField
from NaturalHazardUpdaterTool_Functions import *

try:
    import arcpy  # type: ignore
except Exception:
    arcpy = None  # type: ignore

def runFarmland(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    """
    Right-to-Farm updater.

    ArcPy mode (ArcGIS Pro/Server detected):
      - Downloads county ZIPs via Selenium, extracts shapefiles
      - Picks the most recent year per county
      - Merges, projects to EPSG:3857, stamps fields
      - Writes to processing/final FGDBs and then copies to `naturalhazards_gdb` (.gdb)

    Open-source mode (no ArcPy):
      - Same download/extract
      - Uses GeoPandas to merge & project
      - Writes GeoPackage (.gpkg) into final folder; also writes/creates a .gpkg near `naturalhazards_gdb` if a .gdb path was given

    Returns:
      ArcPy mode    → arcpy result of final Copy_management
      Open-source   → string path like "gpkg:/path/naturalhazards.gpkg#Farmland"
    """

    # DLRP Data Downloads
    web_address = r"https://gis.conservation.ca.gov/portal/home/group.html?id=b1494c705cb34d01acf78f4927a75b8f&view=list&showFilters=true&start=1&num=100#content"
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "Farmland"
    zone_field = "ZONE"
    land_type_field = 'polygon_ty'
    county_name_field = 'county_nam'
    hazard_nickname = "Right To Farm"

    county_exclude_list = ['statewide']  # counties to exclude from processing keying

    land_type_flags = {
        "G": "IN",   # Grazing Land
        "L": "IN",   # Farmland of Local Importance
        "LP": "IN",
        "P": "IN",   # Prime Farmland
        "S": "IN",   # Farmland of Statewide Importance
        "U": "IN",   # Unique Farmland
        "Cl": "OUT", # Confined Animal Agriculture (exceptions below)
        "D": "OUT",  # Urban and Built-up Land
        "nv": "OUT", # Nonagricultural or Natural Vegetation
        "R": "OUT",  # Rural Residential Land
        "sAC": "OUT",# Semi-Agricultural and Rural Commercial Land
        "V": "OUT",  # Vacant or Disturbed Land
        "W": "OUT",  # Water
        "X": "OUT",  # Other Land
        "Z": "OUT"
    }

    # Counties where "Cl" (Confined Animal Agriculture) counts as farmland (IN)
    confined_animal_agriculture_counties = ['fre', 'kin', 'pla', 'riv', 'sac', 'sjq', 'srv', 'tul']

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(
        workspace, hazard_nickname, today_string
    )

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    # -------------- Launch Chrome (Selenium 4) --------------
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_experimental_option('prefs', {'download.default_directory': other_data_folder})
    chrome_options.add_argument("--start-maximized")

    # New Selenium 4 style
    service = ChromeService(executable_path=chrome_driver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # go to listing page
        driver.get(web_address)

        # Wait for content tiles/links to appear and collect "download" links
        # First wait for any anchor to render
        WebDriverWait(driver, 60).until(
            ec.presence_of_all_elements_located((By.TAG_NAME, "a"))
        )

        # Now pick anchors with "download" in href
        downloads = driver.find_elements(By.XPATH, "//a[contains(@href, 'download')]")
        download_count = len(downloads)

        if download_count == 0:
            # Sometimes content is paginated / lazy—small extra wait and re-query
            time.sleep(5)
            downloads = driver.find_elements(By.XPATH, "//a[contains(@href, 'download')]")
            download_count = len(downloads)

        m = "Downloading {} Files...".format(download_count)
        writeMessages(log_file_path, m, False)

        # Click each "download" and wait for completion using the helper
        i = 1
        for download in downloads:
            m = "\nFile {}/{}".format(i, download_count)
            writeMessages(log_file_path, m, False)
            clickToDownloadFile(download, other_data_folder)  # blocks until size stabilizes
            i += 1

        m = "\n{} Files Successfully Downloaded".format(download_count)
        writeMessages(log_file_path, m, False)

        # -------------- Extract ZIPs --------------
        zip_files = [f for f in os.listdir(other_data_folder) if f.lower().endswith(".zip")]

        if len(zip_files) != download_count:
            m = "ERROR: Only {} of {} files were downloaded".format(len(zip_files), download_count)
            writeMessages(log_file_path, m, msg_type='warning')

        m = "Extracting Data..."
        writeMessages(log_file_path, m, False)

        for zip_file in zip_files:
            m = "\t{}...".format(zip_file)
            writeMessages(log_file_path, m, False)
            zip_file_path = os.path.join(other_data_folder, zip_file)
            with ZipFile(zip_file_path, "r") as zip_reader:
                zip_reader.extractall(gis_data_folder)

        m = "Done\n"
        writeMessages(log_file_path, m, False)

        # -------------- Build per-county latest-year selection --------------
        # Collect shapefiles
        shp_files = []
        for root, _, files in os.walk(gis_data_folder):
            for f in files:
                if f.lower().endswith(".shp"):
                    shp_files.append(os.path.join(root, f))

        # Parse county+year from filename: e.g., "<county><YYYY>.shp" or "<county>_<YYYY>.shp"
        # We’ll search for the first digit index and treat prefix as the county key.
        shapefile_dict = {}  # county_key -> {'year': int, 'file': path}
        for shp in shp_files:
            base = os.path.splitext(os.path.basename(shp))[0]
            m_d = re.search(r"\d", base)
            if not m_d:
                continue  # skip if no trailing year
            digit_index = m_d.start()
            county_key = base[:digit_index].strip().lower().replace("-", "_")
            # Skip excluded counties
            if county_key in county_exclude_list:
                continue
            # Parse year (robustly, last 4-digit year in name)
            m_year = re.search(r"(\d{4})", base[digit_index:])
            if not m_year:
                continue
            year = int(m_year.group(1))

            if county_key not in shapefile_dict or year > shapefile_dict[county_key]['year']:
                shapefile_dict[county_key] = {'year': year, 'file': shp}

        writeMessages(log_file_path, "Copying Most Recent Data...", False)

        # --------- ArcPy mode ----------
        if ARCPY_AVAILABLE:
            arcpy.env.overwriteOutput = True  # type: ignore

            # copy latest per-county to processing_gdb
            for county_key, info in shapefile_dict.items():
                year = info['year']; most_recent_file = info['file']
                out_file_name = "{}_{}".format(county_key, year)
                out_file_path = os.path.join(processing_gdb, out_file_name)
                writeMessages(log_file_path, f"\t{county_key} ({year})", False)
                arcpy.CopyFeatures_management(most_recent_file, out_file_path)  # type: ignore

            # merge & project
            arcpy.env.workspace = processing_gdb  # type: ignore
            merge_list = arcpy.ListFeatureClasses()  # type: ignore

            merged_fc = output_name + "_merged"
            arcpy.Merge_management(merge_list, merged_fc)  # type: ignore

            projected_fc = os.path.join(final_gdb, output_name)
            arcpy.Project_management(merged_fc, projected_fc, arcpy.SpatialReference(output_sr_wkid))  # type: ignore

            # add fields and stamp
            if zone_field not in [f.name for f in arcpy.ListFields(projected_fc)]:  # type: ignore
                arcpy.AddField_management(projected_fc, zone_field, "TEXT", field_length=3)  # type: ignore

            addDTField(projected_fc)  # uses ArcPy path

            unknown_land_types = []

            cursor_fields = [land_type_field, county_name_field, zone_field]
            with arcpy.da.UpdateCursor(projected_fc, cursor_fields) as update_cursor:  # type: ignore
                for row in update_cursor:
                    land_type = row[0]
                    county_val = row[1]
                    if land_type in land_type_flags:
                        if land_type == 'Cl' and (county_val and str(county_val).strip().lower() in confined_animal_agriculture_counties):
                            zone = 'IN'
                        else:
                            zone = land_type_flags[land_type]
                    else:
                        if land_type not in unknown_land_types:
                            unknown_land_types.append(land_type)
                        zone = 'OUT'
                    update_cursor.updateRow((land_type, county_val, zone))

            if len(unknown_land_types) > 0:
                m = ("The following landcover codes were not defined: ({}). "
                     "They were defaulted to 'OUT'").format(unknown_land_types)
                writeMessages(log_file_path, m, msg_type='warning')

            # write to natural hazards gdb (.gdb expected)
            final_natural_hazard_layer_path = os.path.join(naturalhazards_gdb, output_name)
            final_natural_hazard_layer = arcpy.Copy_management(projected_fc, final_natural_hazard_layer_path)  # type: ignore

            driver.quit()
            writeMessages(log_file_path, "\tSUCCESS\n")
            return final_natural_hazard_layer

        # --------- Open-source mode ----------
        # GeoPandas pipeline
        gp, sh, pj, io_driver = _lazy_import_gis()
        import pandas as pd

        gdfs = []
        for county_key, info in shapefile_dict.items():
            year = info['year']; shp_path = info['file']
            writeMessages(log_file_path, f"\t{county_key} ({year})", False)
            gdf = gp.read_file(shp_path)
            gdf["__src_year"] = year
            gdf["__county_key"] = county_key
            gdfs.append(gdf)

        if not gdfs:
            driver.quit()
            writeMessages(log_file_path, "No shapefiles found to process.", msg_type="warning")
            return None

        merged_gdf = pd.concat(gdfs, ignore_index=True)

        # Project to target CRS (EPSG:3857)
        if merged_gdf.crs is None:
            # best-effort: a lot of FMMP data is EPSG:3310 or 4326; if unknown, assume 4326
            merged_gdf.set_crs("EPSG:4326", inplace=True)
        proj_gdf = merged_gdf.to_crs(epsg=int(output_sr_wkid))

        # Add zone + timestamp
        proj_gdf[zone_field] = "OUT"
        stamp = today
        proj_gdf["last_updated"] = stamp

        # Compute zone using rules
        lt = proj_gdf.get(land_type_field)
        cn = proj_gdf.get(county_name_field)

        # normalize helper
        def _norm(x):
            return str(x).strip().lower() if x is not None else ""

        unknown_land_types = set()

        def _zone_for_row(land_type_val, county_val):
            lt_code = str(land_type_val) if land_type_val is not None else ""
            if lt_code in land_type_flags:
                if lt_code == "Cl":
                    # use county name/code as provided; normalize to lowercase
                    if _norm(county_val) in confined_animal_agriculture_counties:
                        return "IN"
                    return land_type_flags[lt_code]  # OUT
                return land_type_flags[lt_code]
            else:
                if lt_code != "":
                    unknown_land_types.add(lt_code)
                return "OUT"

        proj_gdf[zone_field] = [
            _zone_for_row(lt.iloc[i] if lt is not None else None,
                          cn.iloc[i] if cn is not None else None)
            for i in range(len(proj_gdf))
        ]

        if unknown_land_types:
            writeMessages(
                log_file_path,
                f"Unknown landcover codes defaulted to 'OUT': {sorted(unknown_land_types)}",
                msg_type="warning"
            )

        # Write to a GeoPackage in the final folder
        final_gpkg = os.path.join(final_gdb if os.path.isdir(final_gdb) else os.path.dirname(final_gdb),
                                  f"{output_name}_{today_string}.gpkg")
        if os.path.exists(final_gpkg):
            os.remove(final_gpkg)
        proj_gdf.to_file(final_gpkg, layer=output_name, driver="GPKG")

        # Also write to the natural hazards target:
        if naturalhazards_gdb.lower().endswith(".gpkg"):
            nat_gpkg = naturalhazards_gdb
        elif naturalhazards_gdb.lower().endswith(".gdb"):
            # Can't write FileGDB without ArcPy: write sibling GPKG
            nat_gpkg = os.path.splitext(naturalhazards_gdb)[0] + ".gpkg"
            writeMessages(
                log_file_path,
                f"ArcPy not available; writing GeoPackage instead of FileGDB: {nat_gpkg}",
                msg_type="warning"
            )
        else:
            # If folder, drop a default gpkg there; else treat as file path (ensure .gpkg)
            if os.path.isdir(naturalhazards_gdb):
                nat_gpkg = os.path.join(naturalhazards_gdb, "naturalhazards.gpkg")
            else:
                root, ext = os.path.splitext(naturalhazards_gdb)
                nat_gpkg = naturalhazards_gdb if ext.lower() == ".gpkg" else f"{root}.gpkg"

        if os.path.exists(nat_gpkg):
            os.remove(nat_gpkg)
        proj_gdf.to_file(nat_gpkg, layer=output_name, driver="GPKG")

        driver.quit()
        writeMessages(log_file_path, "\tSUCCESS\n")
        return f"gpkg:{nat_gpkg}#{output_name}"

    except Exception as e:
        try:
            driver.quit()
        except Exception:
            pass
        writeMessages(log_file_path, f"\t!!! ERROR !!!\n\t{e}", msg_type='warning')
        return None
