# NaturalHazardUpdaterTool_crossplatform_harvester.py

from NaturalHazardUpdaterTool_Functions import *  # ARCPY_AVAILABLE, writeMessages, etc.

# Hazard modules (unchanged imports)
from UpdateHazard_SpecialFloodHazard_module import runFlood
from UpdateHazard_DamInundation_module import runDamInundation
from UpdateHazard_CGSLayers_module import runCGS
from UpdateHazard_RightToFarm_module import runFarmland
from UpdateHazard_SolidWasteFac_module import runSolidWasteFacilities
from UpdateHazard_EPALayers_module import runEPALayers
from UpdateHazard_MiningOperations_module import runMiningOperations
from UpdateHazard_StatePriorityList_module import runStatePriorityList
from UpdateHazard_LUST_module import runLUST
from UpdateHazard_UST_module import runUST
from UpdateHazard_FUDS_module import runFUDs
from UpdateHazard_GeothermalWells_module import runGeothermalWells
from UpdateHazard_CAWells_module import runAllWells
from UpdateHazard_ElectricTransmissionLines import runElectricTransmissionLines
from UpdateHazard_Railroads import runRailroads
from UpdateHazard_AgTimberResources import runAgTimberResources
from UpdateHazard_CriticalHabitat import runCriticalHabitat
from UpdateHazard_TsunamiInundation import runTsunamiInundaiton
from UpdateHazard_VCP_module import runVCPHazard
from UpdateHazard_ERNS_module import runERNSHazard
from UpdateHazard_ClandestineLabs_module import runClandestineLabs
from UpdateHazard_CoastalErosion_module import runCoastalBluffsErosion
from UpdateHazard_Subsidence import runSubsidence
from UpdateHazard_SRA import runSRA
from UpdateAncillaryData_CAJurisdictions_module import runCAJurisdictions
from UpdateAncillaryData_CAFireDistricts import runCAFireDistricts

import os
import datetime

# ========= CONFIG =========
# "gpkg" -> same file on Win & Mac (recommended)
# "gdb"  -> Windows-only; Mac will still fall back to gpkg.
UNIFIED_FORMAT = "gpkg"

# If some legacy modules REQUIRE a GDB path as their target (ArcPy-heavy),
# keep this True so we let them write into a temp GDB on Windows and then mirror to GPKG.
ALLOW_TEMP_GDB_WHEN_ARCPY = True
# ==========================


# ------------------------------------------------------------
# Helper: run a module and never crash the whole pipeline
# ------------------------------------------------------------
def safe_call(name, func, *params):
    try:
        res = func(*params)
        if res is None:
            writeMessages(log_file_path, f"{name}: returned no result (None)", msg_type="warning")
        else:
            writeMessages(log_file_path, f"{name}: completed", False)
        return res
    except Exception as e:
        writeMessages(log_file_path, f"{name}: failed or skipped — {e}", msg_type="warning")
        return None


def create_workspace_paths(base_dir, today_string, ticket_suffix):
    """
    Returns:
      work_folder, updates_target, ancillary_target, final_publish_path
    Logic:
      - If ArcPy available and ALLOW_TEMP_GDB_WHEN_ARCPY, create a temp *.gdb for processing AND publish later to *.gpkg.
      - If ArcPy not available, create *.gpkg targets directly.
    """
    # Run workspace folder
    work_folder = os.path.join(base_dir, f"Natural_Hazard_Updates_{today_string}{ticket_suffix}")
    os.makedirs(work_folder, exist_ok=True)

    # Base names (without extensions)
    hazards_base   = f"Natural_Hazard_Updates_{today_string.split('_')[0]}{ticket_suffix}"
    ancillary_base = f"AncillaryData_{today_string.split('_')[0]}{ticket_suffix}"

    # Final publish path (same across platforms when UNIFIED_FORMAT='gpkg')
    if UNIFIED_FORMAT.lower() == "gdb" and ARCPY_AVAILABLE:
        final_publish = os.path.join(work_folder, f"{hazards_base}.gdb")
    else:
        final_publish = os.path.join(work_folder, f"{hazards_base}.gpkg")
        # create later as needed; harmless to touch here
        open(final_publish, "ab").close()

    # Processing targets (what we pass to modules)
    if ARCPY_AVAILABLE and ALLOW_TEMP_GDB_WHEN_ARCPY:
        # Use GDB for module compatibility, mirror later if needed
        updates_target = os.path.join(work_folder, f"{hazards_base}.gdb")
        ancillary_target = os.path.join(work_folder, f"{ancillary_base}.gdb")
        arcpy.CreateFileGDB_management(work_folder, f"{hazards_base}.gdb")      # type: ignore
        arcpy.CreateFileGDB_management(work_folder, f"{ancillary_base}.gdb")    # type: ignore
    else:
        # Use GPKG on Mac or when we want exact parity
        updates_target = os.path.join(work_folder, f"{hazards_base}.gpkg")
        ancillary_target = os.path.join(work_folder, f"{ancillary_base}.gpkg")
        open(updates_target, "ab").close()
        open(ancillary_target, "ab").close()

    return work_folder, updates_target, ancillary_target, final_publish


def list_layers_any(workspace_path):
    """
    Lists layers in a GDB/GPKG (cross-platform using Fiona if ArcPy not available).
    """
    if ARCPY_AVAILABLE and workspace_path.lower().endswith(".gdb"):
        arcpy.env.workspace = workspace_path  # type: ignore
        fcs = arcpy.ListFeatureClasses() or []  # type: ignore
        return fcs

    try:
        import fiona
        return list(fiona.listlayers(workspace_path))
    except Exception:
        return []


def mirror_to_gpkg_if_needed(process_workspace_path, publish_gpkg_path):
    """
    Mirror a GDB (process) into a final GPKG publish file, or from GPKG to GPKG (noop).
    Used to ensure the final artifact is consistent across Win/Mac.
    """
    if process_workspace_path.lower().endswith(".gpkg"):
        # Already in gpkg; ensure publish path exists; if different, copy layers over
        if os.path.abspath(process_workspace_path) == os.path.abspath(publish_gpkg_path):
            return

    writeMessages(log_file_path, f"Normalizing outputs → {publish_gpkg_path}", False)

    try:
        import geopandas as gp
    except Exception as e:
        writeMessages(log_file_path, f"GeoPandas required to publish GPKG: {e}", msg_type="warning")
        return

    # Start fresh publish file
    if os.path.exists(publish_gpkg_path):
        os.remove(publish_gpkg_path)
    open(publish_gpkg_path, "ab").close()

    layers = list_layers_any(process_workspace_path)
    if not layers:
        writeMessages(log_file_path, "No layers found to publish.", msg_type="warning")
        return

    for lyr in layers:
        try:
            gdf = gp.read_file(process_workspace_path, layer=lyr)
            gdf.to_file(publish_gpkg_path, layer=lyr, driver="GPKG")
        except Exception as e:
            writeMessages(log_file_path, f"Failed to export layer '{lyr}' to GPKG: {e}", msg_type="warning")


def harvest_any_vectors_to_gpkg(search_root: str, publish_gpkg_path: str):
    """
    Cross-platform harvester (Windows/mac/Linux).
    - Finds SHP, GPKG, and FileGDBs under search_root
    - Copies all layers into publish_gpkg_path (GPKG)
    Skips self-import (won't re-import publish_gpkg_path into itself).
    """
    # Try fast path (pyogrio); fall back to geopandas+fiona
    try:
        import pyogrio
        use_pyogrio = True
    except Exception:
        use_pyogrio = False

    try:
        import geopandas as gp
        import fiona
    except Exception as e:
        writeMessages(log_file_path, f"Harvester requires GeoPandas/Fiona (or add an ogr2ogr fallback). {e}", msg_type="warning")
        return

    # Ensure target file exists
    if not os.path.exists(publish_gpkg_path):
        open(publish_gpkg_path, "ab").close()

    pub_abs = os.path.abspath(publish_gpkg_path)

    def import_gpkg_layers(src_gpkg):
        src_abs = os.path.abspath(src_gpkg)
        if src_abs == pub_abs:
            return  # don't import into itself
        try:
            layers = list(fiona.listlayers(src_gpkg))
        except Exception as e:
            writeMessages(log_file_path, f"Cannot list layers in {src_gpkg}: {e}", msg_type="warning")
            return
        for lyr in layers:
            try:
                if use_pyogrio:
                    df = pyogrio.read_dataframe(src_gpkg, layer=lyr)
                    pyogrio.write_dataframe(df, publish_gpkg_path, layer=lyr, driver="GPKG")
                else:
                    gp.read_file(src_gpkg, layer=lyr).to_file(publish_gpkg_path, layer=lyr, driver="GPKG")
                writeMessages(log_file_path, f"Harvested {lyr} from {os.path.basename(src_gpkg)}", False)
            except Exception as e:
                writeMessages(log_file_path, f"Failed harvesting {lyr} from {src_gpkg}: {e}", msg_type="warning")

    def import_gdb_layers(src_gdb):
        try:
            layers = list(fiona.listlayers(src_gdb))  # uses OpenFileGDB driver (read-only)
        except Exception as e:
            writeMessages(log_file_path, f"Cannot list {src_gdb}: {e}", msg_type="warning")
            return
        for lyr in layers:
            try:
                if use_pyogrio:
                    df = pyogrio.read_dataframe(src_gdb, layer=lyr)
                    pyogrio.write_dataframe(df, publish_gpkg_path, layer=lyr, driver="GPKG")
                else:
                    gp.read_file(src_gdb, layer=lyr).to_file(publish_gpkg_path, layer=lyr, driver="GPKG")
                writeMessages(log_file_path, f"Harvested {lyr} from {os.path.basename(src_gdb)}", False)
            except Exception as e:
                writeMessages(log_file_path, f"Failed harvesting {lyr} from {src_gdb}: {e}", msg_type="warning")

    def import_shapefile(shp_path):
        try:
            layer_name = os.path.splitext(os.path.basename(shp_path))[0]
            if use_pyogrio:
                df = pyogrio.read_dataframe(shp_path)
                pyogrio.write_dataframe(df, publish_gpkg_path, layer=layer_name, driver="GPKG")
            else:
                gp.read_file(shp_path).to_file(publish_gpkg_path, layer=layer_name, driver="GPKG")
            writeMessages(log_file_path, f"Harvested {layer_name} from {os.path.basename(shp_path)}", False)
        except Exception as e:
            writeMessages(log_file_path, f"Failed harvesting {shp_path}: {e}", msg_type="warning")

    # Harvest SHP & GPKG files
    for root, _, files in os.walk(search_root):
        for f in files:
            path = os.path.join(root, f)
            fl = f.lower()
            if fl.endswith(".shp"):
                import_shapefile(path)
            elif fl.endswith(".gpkg"):
                import_gpkg_layers(path)

    # Harvest FileGDBs (directories)
    for root, dirs, _ in os.walk(search_root):
        for d in dirs:
            if d.lower().endswith(".gdb"):
                import_gdb_layers(os.path.join(root, d))


def log_layers(path, label):
    try:
        import fiona
        layers = list(fiona.listlayers(path))
        writeMessages(log_file_path, f"{label}: {os.path.basename(path)} has {len(layers)} layer(s): {layers}", False)
    except Exception as e:
        writeMessages(log_file_path, f"{label}: cannot inspect {path} — {e}", msg_type="warning")


# =================== USER TOGGLES & INPUTS ===================
update_hazards = []
ancillary_data_updates = []

### Natural Hazards ###
run_flood = 1
flood_zip = r"C:\Users\elowe\Downloads\NFHL_06_20241112.zip"
run_sra = 0
run_dam_inundation = 0
dam_inundation_zip = r"C:\Users\elowe\Downloads\Approved_InundationBoundaries.zip"
run_CGS_hazards = 1

### Supplemental Hazards ###
run_farmland = 0
run_mining_operations = 0
run_electric_transmission_lines = 0
run_criticalhabitat = 1
criticalhabitat_zip = r"C:\Users\elowe\Downloads\gis_com(1).zip"
forestservice_zip = r"C:\Users\elowe\Downloads\crithab_all_layers(1).zip"
run_tsunami_inundation = 0
supplimental_flood_fc = r'C:\workspace\ARE-10103_HazardUpdates\SuppFlood_20221208.gdb\Supplemental_Flood_Hazards'
run_coastalerosion = 0
run_fuds = 0
run_subsidence = 0
subsidence_tif = r'C:\workspace\__HazardUpdates\ARE-12797_Subsidence\Subsidence_20150613_20240701_wNoData.tif'
run_clandestine = 0
run_railroads = 0
run_agtimber_resources = 0

### Environmental Hazards ###
run_solid_waste = 1
run_epa_hazards = 1
run_state_priority_list = 1
spl_sites = r"C:\Users\elowe\Downloads\export(2).xls"
run_lust = 1
run_allwells = 1
run_ust = 0
run_geothermalwells = 0
run_vcp = 0
run_erns = 0

### Ancillary Data ###
run_jurisdictions = 0
run_firedistricts = 0

### workspace ###
workspace_dir = r'C:\workspace\__HazardUpdates'
current_jurisdictions_fc_path = r"C:\workspace\__BaseData\Corrected_Jurisdictions.gdb\CA_Jurisdictions"
ticket = 'ARE-12872'
# Windows example; on mac you can leave it unused/None (modules that use Selenium should handle it)
chrome_driver_path = r"C:\Program Files (x86)\Google\Chrome\chromedriver.exe"

# ========================== MAIN ==========================
today = datetime.datetime.now()
today_string = today.strftime("%Y%m%d_%H%M")
ticket_suffix = f"_{ticket.strip()}" if ticket.strip() else ""

# Create run workspace + output targets
workspace, updates_target, ancillary_target, final_publish_path = create_workspace_paths(
    base_dir=workspace_dir,
    today_string=today_string,
    ticket_suffix=ticket_suffix
)

log_file_path = os.path.join(workspace, f"NaturalHazardUpdate_{today_string}_log.txt")
writeMessages(log_file_path, f"Update Data Log File\nDate: {today_string}\n", False)

# Log selected modules
if run_flood: update_hazards.append("\t- Special Flood Hazard\n")
if run_sra: update_hazards.append("\t- State Responsibility Area (CalFire)\n")
if run_dam_inundation: update_hazards.append("\t- Dam Inundation\n")
if run_CGS_hazards: update_hazards.append("\t- Alquist-Priolo Fault Rupture\n\t- California Geological Survey Landslide Zone\n\t- California Geological Survey Liquefaction Zone\n")
if run_farmland: update_hazards.append("\t- FMMP Farmland\n")
if run_solid_waste: update_hazards.append("\t- Solid Waste Facilities (SWIS)\n")
if run_epa_hazards: update_hazards.append("\t- NPL\n\t- SEMS (CERCLIS)\n\t- Toxic Release Inventory\n")
if run_mining_operations: update_hazards.append("\t- Mining Operations\n")
if run_state_priority_list: update_hazards.append("\t- State Priority List\n")
if run_lust: update_hazards.append("\t- Leaking Underground Storage Tanks\n")
if run_ust: update_hazards.append("\t- Underground Storage Tanks\n")
if run_fuds: update_hazards.append("\t- Formerly Used Defense Sites\n")
if run_geothermalwells: update_hazards.append("\t- Geothermal Wells\n")
if run_allwells: update_hazards.append("\t- Gas/Oil/Geothermal\n")
if run_electric_transmission_lines: update_hazards.append("\t- Major Electric Transmission Lines\n")
if run_railroads: update_hazards.append("\t- Railroads\n")
if run_agtimber_resources: update_hazards.append("\t- Agricultural Resource Areas\n\t- Timber Resource Areas\n")
if run_criticalhabitat: update_hazards.append("\t- Critical Habitat\n")
if run_tsunami_inundation: update_hazards.append("\t- Supplemental Flood (Tsunami Inundation)\n")
if run_vcp: update_hazards.append("\t- Voluntary Cleanup Program\n")
if run_erns: update_hazards.append("\t- Emergency Response Notification System\n")
if run_clandestine: update_hazards.append("\t- Clandestine Drug Laboratories\n")
if run_coastalerosion: update_hazards.append("\t- Coastal Erosion (Bluffs & Dunes)\n")
if run_subsidence: update_hazards.append("\t- Subsidence\n")
if run_jurisdictions: ancillary_data_updates.append("\t- City/County Jurisdictions\n")
if run_firedistricts: ancillary_data_updates.append("\t- CalFire Districts\n")

writeMessages(log_file_path, f"### Hazard Update Log File ###\n\nDate/Time: {today_string}\n", False)
hazard_list_string = "".join(update_hazards) if update_hazards else " --- No Hazards Selected ---"
writeMessages(log_file_path, f"\nThe following hazards have been selected for updating:\n{hazard_list_string}\n")
ancillary_list_string = "".join(ancillary_data_updates) if ancillary_data_updates else " --- No Ancillary Datasets Selected ---"
writeMessages(log_file_path, f"\nThe following ancillary datasets have been selected for updating:\n{ancillary_list_string}\n")

# Build the param arrays that modules expect: [workspace, chrome_driver_path, log_file_path, target_db]
hazard_params   = [workspace, chrome_driver_path, log_file_path, updates_target]
ancillary_params= [workspace, chrome_driver_path, log_file_path, ancillary_target]

# Execute selections safely
hazard_results = []
if update_hazards:
    if run_flood:
        hazard_results.append(safe_call("Special Flood Hazard", runFlood, *(hazard_params + [flood_zip])))
    if run_dam_inundation:
        hazard_results.append(safe_call("Dam Inundation", runDamInundation, *(hazard_params + [dam_inundation_zip])))
    if run_CGS_hazards:
        hazard_results.append(safe_call("CGS Layers", runCGS, *hazard_params))
    if run_farmland:
        hazard_results.append(safe_call("Right To Farm", runFarmland, *hazard_params))
    if run_solid_waste:
        hazard_results.append(safe_call("Solid Waste Facilities (SWIS)", runSolidWasteFacilities, *hazard_params))
    if run_epa_hazards:
        hazard_results.append(safe_call("EPA Layers", runEPALayers, *hazard_params))
    if run_mining_operations:
        hazard_results.append(safe_call("Mining Operations", runMiningOperations, *hazard_params))
    if run_state_priority_list:
        hazard_results.append(safe_call("State Priority List", runStatePriorityList, *(hazard_params + [spl_sites])))
    if run_lust:
        hazard_results.append(safe_call("LUST", runLUST, *hazard_params))
    if run_ust:
        hazard_results.append(safe_call("UST", runUST, *hazard_params))
    if run_fuds:
        hazard_results.append(safe_call("FUDS", runFUDs, *hazard_params))
    if run_geothermalwells:
        hazard_results.append(safe_call("Geothermal Wells", runGeothermalWells, *hazard_params))
    if run_allwells:
        hazard_results.append(safe_call("All Wells", runAllWells, *hazard_params))
    if run_electric_transmission_lines:
        hazard_results.append(safe_call("Electric Transmission Lines", runElectricTransmissionLines, *hazard_params))
    if run_railroads:
        hazard_results.append(safe_call("Railroads", runRailroads, *hazard_params))
    if run_agtimber_resources:
        hazard_results.append(safe_call("Ag/Timber Resources", runAgTimberResources, *hazard_params))
    if run_criticalhabitat:
        hazard_results.append(safe_call("Critical Habitat", runCriticalHabitat, *(hazard_params + [criticalhabitat_zip, forestservice_zip])))
    if run_tsunami_inundation:
        hazard_results.append(safe_call("Tsunami Inundation", runTsunamiInundaiton, *(hazard_params + [supplimental_flood_fc])))
    if run_vcp:
        hazard_results.append(safe_call("VCP", runVCPHazard, *hazard_params))
    if run_erns:
        hazard_results.append(safe_call("ERNS", runERNSHazard, *hazard_params))
    if run_clandestine:
        hazard_results.append(safe_call("Clandestine Labs", runClandestineLabs, *hazard_params))
    if run_coastalerosion:
        hazard_results.append(safe_call("Coastal Erosion", runCoastalBluffsErosion, *hazard_params))
    if run_subsidence:
        hazard_results.append(safe_call("Subsidence", runSubsidence, *(hazard_params + [subsidence_tif])))

# SRA belongs with natural hazards (keep behavior consistent)
if run_sra:
    hazard_results.append(safe_call("SRA", runSRA, *(hazard_params + [current_jurisdictions_fc_path])))

# Ancillary datasets
if ancillary_data_updates:
    if run_jurisdictions:
        hazard_results.append(safe_call("CA Jurisdictions", runCAJurisdictions, *ancillary_params))
    if run_firedistricts:
        hazard_results.append(safe_call("CA Fire Districts", runCAFireDistricts, *ancillary_params))

# -------- Publish normalization (same final result Win/Mac) --------
if UNIFIED_FORMAT.lower() == "gpkg":
    # If we processed in a GDB on Windows, mirror to GPKG so the final artifact is identical to mac.
    mirror_to_gpkg_if_needed(updates_target, final_publish_path)
else:
    # User chose gdb as final. If we processed in gpkg (mac), we already wrote gpkg.
    # Optionally: attempt to build a gdb if ArcPy exists; else leave as gpkg and log.
    if not (ARCPY_AVAILABLE and final_publish_path.lower().endswith(".gdb")):
        writeMessages(
            log_file_path,
            "Requested final 'gdb' but ArcPy not available; leaving outputs in GeoPackage.",
            msg_type="warning"
        )

# -------- Harvest anything modules wrote elsewhere into the final GPKG --------
if UNIFIED_FORMAT.lower() == "gpkg":
    harvest_any_vectors_to_gpkg(workspace, final_publish_path)
    log_layers(final_publish_path, "FINAL")
else:
    # If someone insisted on final GDB, you could add a symmetric GDB harvester with ArcPy here.
    pass

# Final log
writeMessages(
    log_file_path,
    f"\n\n ------------ Script Complete ------------"
    f"\n\n\tUpdates Saved Here:\n\t\t{workspace}"
    f"\n\n\tFinal Published Output:\n\t\t{final_publish_path}"
    f"\n\n\tUpdate Details:\n\t\t{log_file_path}"
    f"\n\n -------------    End Log     ------------"
)
