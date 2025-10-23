# backup_updates_module.py

import os
import sys

# Try ArcPy; fall back to open-source stack
try:
    import arcpy  # type: ignore
    ARCPY_AVAILABLE = True
except Exception:
    arcpy = None  # type: ignore
    ARCPY_AVAILABLE = False


# ------------------------ Logging helpers ------------------------
def add_msg(msg: str) -> None:
    if ARCPY_AVAILABLE:
        arcpy.AddMessage(msg)  # type: ignore
    else:
        print(msg)

def add_warn(msg: str) -> None:
    if ARCPY_AVAILABLE:
        arcpy.AddWarning(msg)  # type: ignore
    else:
        print(f"[WARN] {msg}")

def add_err(msg: str) -> None:
    if ARCPY_AVAILABLE:
        arcpy.AddError(msg)  # type: ignore
    else:
        print(f"[ERROR] {msg}", file=sys.stderr)


# ------------------------ Layer listing ------------------------
def list_layers(workspace_path: str):
    """
    Returns a list of feature class / layer names in a workspace.

    ArcPy:    arcpy.ListFeatureClasses()
    Open-src: fiona.listlayers() for GDB/GPKG; scans *.shp in a folder
    """
    if ARCPY_AVAILABLE:
        arcpy.env.workspace = workspace_path  # type: ignore
        fcs = arcpy.ListFeatureClasses() or []  # type: ignore
        return fcs

    # Open-source route
    try:
        import fiona
    except Exception as e:
        add_err(f"Fiona is required in open-source mode: {e}")
        return []

    if os.path.isdir(workspace_path):
        # Directory of shapefiles
        return [
            os.path.splitext(f)[0]
            for f in os.listdir(workspace_path)
            if f.lower().endswith(".shp")
        ]

    try:
        return list(fiona.listlayers(workspace_path))
    except Exception as e:
        add_err(f"Unable to list layers for {workspace_path}: {e}")
        return []


# ------------------------ Backup logic ------------------------
def backup_workspace(src_workspace: str, featureclass_list, destination_path: str) -> None:
    """
    Back up any FCs from 'src_workspace' whose names match those in 'featureclass_list'
    into the destination workspace.

    ArcPy:     destination is a FileGDB; uses Copy_management.
    Open-src:  destination is a GeoPackage (.gpkg); uses GeoPandas to copy layers.
    """
    # What exists in the source workspace?
    src_layers = set(list_layers(src_workspace))
    missing = [fc for fc in featureclass_list if fc not in src_layers]
    backup = [fc for fc in featureclass_list if fc in src_layers]

    if missing:
        add_warn(
            "The following feature classes were not found in the source (no backup created):\n\t"
            + "\n\t".join(missing)
        )

    if not backup:
        add_warn("No matching feature classes to back up.")
        return

    if ARCPY_AVAILABLE:
        # ArcPy copy to FileGDB
        for fc in backup:
            in_data = os.path.join(src_workspace, fc)
            out_data = os.path.join(destination_path, fc)
            arcpy.Copy_management(in_data, out_data)  # type: ignore
            add_msg(f"Backed up {fc} -> {out_data}")
        return

    # Open-source: copy to GeoPackage (.gpkg), one layer per FC name
    try:
        import geopandas as gp
    except Exception as e:
        add_err(f"GeoPandas is required in open-source mode: {e}")
        return

    for fc in backup:
        try:
            gdf = gp.read_file(src_workspace, layer=fc)
            gdf.to_file(destination_path, layer=fc, driver="GPKG")
            add_msg(f"Backed up {fc} -> {destination_path}#{fc}")
        except Exception as e:
            add_warn(f"Failed to back up {fc}: {e}")


# ------------------------ Orchestrator ------------------------
def run_backup(
    updates_workspace: str,
    backup_TEST: bool,
    backup_PROD: bool,
    backup_name: str,
    backup_workspace: str,
    TEST_database: str = r'C:\workspace\20220525_HazardUpdaterTool\NEW_DATA\hazardsAll_TEST.gdb',
    PROD_database: str = r'C:\workspace\20220525_HazardUpdaterTool\NEW_DATA\hazardsAll_Prod.gdb',
) -> None:
    """
    Orchestrates backups for TEST/PROD.

    - Collects FC names from 'updates_workspace'
    - Creates backup folder
      - ArcPy: TEST.gdb / PROD.gdb
      - Open-src: TEST.gpkg / PROD.gpkg
    - Copies matching FCs from TEST/PROD source DBs into the backup workspace

    Returns None (logs progress/errors via add_msg/add_warn/add_err).
    """
    if not (backup_TEST or backup_PROD):
        add_err("\nNO ENVIRONMENT SELECTED FOR BACKUP. NO BACKUP CREATED\n")
        return

    # Gather the list of FCs (by name) from the updates workspace
    featureclass_list = list_layers(updates_workspace)

    # Create backup folder
    backup_dir = os.path.join(backup_workspace, backup_name)
    os.makedirs(backup_dir, exist_ok=True)

    # TEST backup
    if backup_TEST:
        add_msg("\nCreating TEST Database Backup...")
        if ARCPY_AVAILABLE:
            test_name = "TEST"
            arcpy.CreateFileGDB_management(backup_dir, test_name)  # type: ignore
            test_dest = os.path.join(backup_dir, f"{test_name}.gdb")
        else:
            test_dest = os.path.join(backup_dir, "TEST.gpkg")
            if os.path.exists(test_dest):
                os.remove(test_dest)
            open(test_dest, "ab").close()
        backup_workspace(TEST_database, featureclass_list, test_dest)

    # PROD backup
    if backup_PROD:
        add_msg("\nCreating PROD Database Backup...")
        if ARCPY_AVAILABLE:
            prod_name = "PROD"
            arcpy.CreateFileGDB_management(backup_dir, prod_name)  # type: ignore
            prod_dest = os.path.join(backup_dir, f"{prod_name}.gdb")
        else:
            prod_dest = os.path.join(backup_dir, "PROD.gpkg")
            if os.path.exists(prod_dest):
                os.remove(prod_dest)
            open(prod_dest, "ab").close()
        backup_workspace(PROD_database, featureclass_list, prod_dest)

    add_msg("\nBackups Created Successfully\n")


# ------------------------ Optional wrapper for ArcGIS tool ------------------------
def run_from_arcpy_params() -> None:
    """
    If you’re calling this file as an ArcGIS Script Tool, call this function.
    It reads the parameters via arcpy.GetParameter* and forwards to run_backup().
    This function is NOT auto-executed.
    """
    if not ARCPY_AVAILABLE:
        add_err("ArcPy is not available; use run_backup(...) directly from Python.")
        return

    updates_workspace = arcpy.GetParameterAsText(0)   # type: ignore
    backup_TEST = bool(arcpy.GetParameter(1))         # type: ignore
    backup_PROD = bool(arcpy.GetParameter(2))         # type: ignore
    backup_name = arcpy.GetParameter(3)               # type: ignore
    backup_workspace = arcpy.GetParameterAsText(4)    # type: ignore

    # Defaults (can be exposed as more tool params if you want)
    TEST_database = r'C:\workspace\20220525_HazardUpdaterTool\NEW_DATA\hazardsAll_TEST.gdb'
    PROD_database = r'C:\workspace\20220525_HazardUpdaterTool\NEW_DATA\hazardsAll_Prod.gdb'

    run_backup(
        updates_workspace=updates_workspace,
        backup_TEST=backup_TEST,
        backup_PROD=backup_PROD,
        backup_name=backup_name,
        backup_workspace=backup_workspace,
        TEST_database=TEST_database,
        PROD_database=PROD_database,
    )
