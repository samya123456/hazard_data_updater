from NaturalHazardUpdaterTool_Functions import *  # provides ARCPY_AVAILABLE, createWorkspaces, exportFeatureServiceLayer, extractGeoJson, writeMessages, etc.
import os
import datetime
import shutil

def runCGS(
    workspace: str,
    chrome_driver_path: str,               # kept for compatibility (not used here)
    log_file_path: str,
    naturalhazards_gdb: str,
    layer_urls: dict | None = None,        # NEW: required in open-source mode (no ArcPy)
    sr_wkid: int | str = 3857              # output SR (matches your original default)
):
    """
    CGS updater: ArcPy or Open-Source.

    ArcPy mode (ArcGIS Pro/Server detected):
      - Reads layers from templates\\FeatureService_Layers.mxd
      - Writes to FileGDBs created by createWorkspaces()
      - Copies final layers into `naturalhazards_gdb` (must be a .gdb)

    Open-source mode (no ArcPy):
      - Requires REST layer URLs via `layer_urls`:
            {
              "landslide":   "https://.../FeatureServer/###",
              "liquefaction":"https://.../FeatureServer/###",
              "fault":       "https://.../FeatureServer/###",
              "evaluation":  "https://.../FeatureServer/###"
            }
      - Downloads with esridump → GeoJSON → GeoPandas
      - Adds fields and concatenates like ArcPy Merge
      - Writes a GeoPackage (.gpkg) in the final folder and, if possible, to `naturalhazards_gdb`
        * If `naturalhazards_gdb` ends with ".gpkg", writes there
        * If it ends with ".gdb" but ArcPy is unavailable, writes a sibling .gpkg instead and logs a warning

    Returns:
      ArcPy mode   → list of arcpy result objects [fault, landslide, liquefaction]
      Open-source  → list of string layer spec paths like ["gpkg:/path/file.gpkg#Alquist_Priolo_Fault_Rupture", ...]
    """
    # ---- constants
    last_updated_field = "last_updated"
    zone_field = "ZONE"

    landslide_output_name    = "CGS_Landslide_Zone"
    liquifaction_output_name = "CGS_Liquefaction_Zone"
    fault_output_name        = "Alquist_Priolo_Fault_Rupture"
    hazard_nickname          = "CGS Layers"

    # ---- environment prep
    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces (ArcPy → creates .gdbs; Open-source → returns folders to use)
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(
        workspace, hazard_nickname, today_string
    )

    writeMessages(log_file_path, f"### {hazard_nickname.upper()} UPDATE ###")

    try:
        if ARCPY_AVAILABLE:
            # ----------------------------- ArcPy path -----------------------------
            # Use MXD template next to this file (as in your original)
            script_path = os.path.dirname(os.path.abspath(__file__))
            mxd_path = os.path.join(script_path, r"templates\FeatureService_Layers.mxd")

            mxd = arcpy.mapping.MapDocument(mxd_path)  # type: ignore
            df = arcpy.mapping.ListDataFrames(mxd, "")[0]  # type: ignore

            arcpy.env.overwriteOutput = True  # type: ignore

            writeMessages(log_file_path, "Extracting Landslide Zone Data From Template MXD ", False)
            landslide_fc = exportFeatureServiceLayer(mxd_path, df, "Landslide Zones", processing_gdb, "Landslide_Zones")

            writeMessages(log_file_path, "Extracting Liquifaction Zone Data... ", False)
            liquifaction_fc = exportFeatureServiceLayer(mxd_path, df, "Liquefaction Zones", processing_gdb, "Liquefaction_Zones")

            writeMessages(log_file_path, "Extracting Alquist-Priolo Earthquake Fault Zones Data... ", False)
            fault_fc = exportFeatureServiceLayer(mxd_path, df, "Fault_Zones", processing_gdb, "Fault_Zones")

            writeMessages(log_file_path, "Extracting CGS Evaluation Zone Data... ", False)
            cgs_evaluation_fc = exportFeatureServiceLayer(mxd_path, df, "Area Not Evaluated for Liquefaction or Landslides", processing_gdb, "Area_Not_Evaluated")

            writeMessages(log_file_path, "Mapping Data...", False)
            for fc in [landslide_fc, liquifaction_fc, fault_fc, cgs_evaluation_fc]:
                arcpy.AddField_management(fc, last_updated_field, "DATE")                    # type: ignore
                arcpy.AddField_management(fc, zone_field, "TEXT", field_length=10)           # type: ignore
                with arcpy.da.UpdateCursor(fc, [last_updated_field, zone_field]) as ucur:     # type: ignore
                    if fc == cgs_evaluation_fc:
                        update_record = [today, 'NA']  # not evaluated
                    else:
                        update_record = [today, 'IN']  # inside zone
                    for _ in ucur:
                        ucur.updateRow(update_record)

            writeMessages(log_file_path, "Creating Final Outputs...", False)

            final_fault_output_fc = os.path.join(final_gdb, fault_output_name)
            arcpy.CopyFeatures_management(fault_fc, final_fault_output_fc)  # type: ignore

            final_landslide_output_fc = os.path.join(final_gdb, landslide_output_name)
            arcpy.Merge_management([landslide_fc, cgs_evaluation_fc], final_landslide_output_fc)  # type: ignore

            final_liquifaction_output_fc = os.path.join(final_gdb, liquifaction_output_name)
            arcpy.Merge_management([liquifaction_fc, cgs_evaluation_fc], final_liquifaction_output_fc)  # type: ignore

            # publish/overwrite to natural hazards gdb
            final_fault_nat_haz_output = arcpy.CopyFeatures_management(final_fault_output_fc, os.path.join(naturalhazards_gdb, fault_output_name))  # type: ignore
            final_landslide_nat_haz_output = arcpy.CopyFeatures_management(final_landslide_output_fc, os.path.join(naturalhazards_gdb, landslide_output_name))  # type: ignore
            final_liquifaction_nat_haz_output = arcpy.CopyFeatures_management(final_liquifaction_output_fc, os.path.join(naturalhazards_gdb, liquifaction_output_name))  # type: ignore

            writeMessages(log_file_path, "\tSUCCESS")
            return [final_fault_nat_haz_output, final_landslide_nat_haz_output, final_liquifaction_nat_haz_output]

        # ----------------------------- Open-source path -----------------------------
        # Need layer_urls to fetch from REST since we can’t read your MXD without ArcPy
        if not layer_urls or not all(k in layer_urls for k in ("landslide", "liquefaction", "fault", "evaluation")):
            writeMessages(
                log_file_path,
                "Open-source mode requires `layer_urls` with keys: landslide, liquefaction, fault, evaluation.",
                msg_type="warning"
            )
            return None

        gp, sh, pj, io_driver = _lazy_import_gis()

        writeMessages(log_file_path, "Downloading CGS layers via REST...", False)
        # pull each layer (writes a .gpkg with a layer named after output_name)
        landslide_path   = extractGeoJson(layer_urls["landslide"],    "Landslide_Zones",   gis_data_folder, sr_wkid)
        liquifaction_path= extractGeoJson(layer_urls["liquefaction"], "Liquefaction_Zones", gis_data_folder, sr_wkid)
        fault_path       = extractGeoJson(layer_urls["fault"],        "Fault_Zones",       gis_data_folder, sr_wkid)
        eval_path        = extractGeoJson(layer_urls["evaluation"],   "Area_Not_Evaluated", gis_data_folder, sr_wkid)

        if not all([landslide_path, liquifaction_path, fault_path, eval_path]):
            writeMessages(log_file_path, "One or more layer downloads failed.", msg_type="warning")
            return None

        # Load into GeoDataFrames
        def _read_layer(gpkg_path: str, layer_name: str):
            return gp.read_file(gpkg_path, layer=layer_name)

        gdf_land = _read_layer(landslide_path,   "Landslide_Zones")
        gdf_liq  = _read_layer(liquifaction_path,"Liquefaction_Zones")
        gdf_fault= _read_layer(fault_path,       "Fault_Zones")
        gdf_eval = _read_layer(eval_path,        "Area_Not_Evaluated")

        # Add fields & stamps
        stamp = today  # pandas will keep tz-naive timestamp fine
        for gdf, is_eval in [(gdf_land, False), (gdf_liq, False), (gdf_fault, False), (gdf_eval, True)]:
            gdf[last_updated_field] = stamp
            gdf[zone_field] = "NA" if is_eval else "IN"

        writeMessages(log_file_path, "Creating Final Outputs (GeoPackage)...", False)

        # Concatenate (equivalent to ArcPy Merge, no overlay/union)
        import pandas as pd
        final_landslide = pd.concat([gdf_land, gdf_eval], ignore_index=True)
        final_liquif    = pd.concat([gdf_liq,  gdf_eval], ignore_index=True)
        final_fault     = gdf_fault.copy()

        # Decide final GPKG target(s)
        final_gpkg = os.path.join(final_gdb, f"{hazard_nickname.replace(' ', '_')}_{today_string}.gpkg")
        if os.path.exists(final_gpkg):
            os.remove(final_gpkg)

        final_landslide.to_file(final_gpkg, layer=landslide_output_name, driver="GPKG")
        final_liquif.to_file(final_gpkg,    layer=liquifaction_output_name, driver="GPKG")
        final_fault.to_file(final_gpkg,     layer=fault_output_name,        driver="GPKG")

        # Also write to naturalhazards_* target
        nat_outputs: list[str] = []
        if naturalhazards_gdb.lower().endswith(".gpkg"):
            nat_gpkg = naturalhazards_gdb
            # fresh write (overwrite file if exists)
            if os.path.exists(nat_gpkg):
                os.remove(nat_gpkg)
            final_landslide.to_file(nat_gpkg, layer=landslide_output_name,    driver="GPKG")
            final_liquif.to_file(nat_gpkg,    layer=liquifaction_output_name, driver="GPKG")
            final_fault.to_file(nat_gpkg,     layer=fault_output_name,        driver="GPKG")
            nat_outputs = [
                f"gpkg:{nat_gpkg}#{fault_output_name}",
                f"gpkg:{nat_gpkg}#{landslide_output_name}",
                f"gpkg:{nat_gpkg}#{liquifaction_output_name}",
            ]
        elif naturalhazards_gdb.lower().endswith(".gdb"):
            # Can't write FileGDB without ArcPy; place a sibling .gpkg instead.
            sibling_gpkg = os.path.splitext(naturalhazards_gdb)[0] + ".gpkg"
            writeMessages(
                log_file_path,
                f"ArcPy not available; writing GeoPackage instead of FileGDB: {sibling_gpkg}",
                msg_type="warning"
            )
            if os.path.exists(sibling_gpkg):
                os.remove(sibling_gpkg)
            final_landslide.to_file(sibling_gpkg, layer=landslide_output_name,    driver="GPKG")
            final_liquif.to_file(sibling_gpkg,    layer=liquifaction_output_name, driver="GPKG")
            final_fault.to_file(sibling_gpkg,     layer=fault_output_name,        driver="GPKG")
            nat_outputs = [
                f"gpkg:{sibling_gpkg}#{fault_output_name}",
                f"gpkg:{sibling_gpkg}#{landslide_output_name}",
                f"gpkg:{sibling_gpkg}#{liquifaction_output_name}",
            ]
        else:
            # If it's a folder, drop a default GPKG there
            if os.path.isdir(naturalhazards_gdb):
                nat_gpkg = os.path.join(naturalhazards_gdb, "naturalhazards.gpkg")
            else:
                # Treat as file path (ensure .gpkg extension)
                root, ext = os.path.splitext(naturalhazards_gdb)
                nat_gpkg = naturalhazards_gdb if ext.lower() == ".gpkg" else f"{root}.gpkg"

            if os.path.exists(nat_gpkg):
                os.remove(nat_gpkg)
            final_landslide.to_file(nat_gpkg, layer=landslide_output_name,    driver="GPKG")
            final_liquif.to_file(nat_gpkg,    layer=liquifaction_output_name, driver="GPKG")
            final_fault.to_file(nat_gpkg,     layer=fault_output_name,        driver="GPKG")
            nat_outputs = [
                f"gpkg:{nat_gpkg}#{fault_output_name}",
                f"gpkg:{nat_gpkg}#{landslide_output_name}",
                f"gpkg:{nat_gpkg}#{liquifaction_output_name}",
            ]

        writeMessages(log_file_path, "\tSUCCESS")
        return nat_outputs

    except Exception as e:
        writeMessages(log_file_path, f"\t!!! ERROR !!!\n\t{e}", msg_type='warning')
        return None
