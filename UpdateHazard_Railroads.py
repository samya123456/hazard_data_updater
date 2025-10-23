# UpdateHazard_Railroads.py (modernized, dual-mode)

import os
import datetime
from NaturalHazardUpdaterTool_Functions import *  # provides ARCPY_AVAILABLE, exportFeatureServiceLayer, extractGeoJson, createWorkspaces, writeMessages, addDTField

try:
    import arcpy  # type: ignore
except Exception:
    arcpy = None  # type: ignore

def runRailroads(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb, layer_url: str = None, output_sr_wkid: int = 3857):
    """
    Railroads updater.

    ArcPy mode:
      - Reads layer "California Rail Network" from templates\\FeatureService_Layers.mxd
      - Adds Fullname field from owner code, stamps last_updated, writes to naturalhazards_gdb (.gdb)

    Open-source mode (no ArcPy):
      - Requires `layer_url` (REST URL to the railroad layer)
      - Downloads features via esridump -> GeoPandas, maps names, writes to GeoPackage (.gpkg)
      - If `naturalhazards_gdb` ends with .gdb, writes a sibling .gpkg instead

    Returns:
      ArcPy: arcpy result object; Open-source: "gpkg:/path/file.gpkg#Railways_2016"
    """

    mxd_layer_name = "California Rail Network"
    output_name    = "Railways_2016"
    hazard_nickname = "RailRoads"
    input_railway_name_field = 'ROW_OWNER'
    railway_name_field       = 'Fullname'
    last_updated_field       = "last_updated"

    # short->long mapping
    railroad_owner_dict = {
        'SCCRTC': 'Santa Cruz County Regional Transportaion Commission',
        'CCT': 'Central California Traction Company',
        'WFS': 'West Isle Line',
        'SSR': 'Sacramento Southern',
        'YW': 'Yreka Western Railroad Company',
        'PRC': 'PRC',
        'RPRC': 'Richmond Pacific Railroad Corporation',
        'QRR': 'Quincy Railroad',
        'SERA': 'Sierra Northern Railway',
        'ARZC': 'Arizona & California Railroad',
        'TRC': 'Trona Railway Company',
        'NCRA': 'Northwestern Pacific',
        'CFNR': 'California Northern Railroad',
        'STE': 'Stockton Terminal and Eastern Railroad',
        'SCBG': 'Santa Cruz, Big Trees & Pacific',
        'FWRY': 'Fillmore & Western Railway',
        'WRM': 'Western Railway Museum',
        'AL': 'AL',
        'CORP': 'Central Oregon & Pacific Railroad',
        'LCR': 'Metro-North Railroad',
        'SMV': 'Santa Maria Valley Railroad',
        'SMART': 'Sonoma-Marin Area Rail Transit',
        'VCRR': 'Ventura County Railroad',
        'BNSF': 'Burlington Nothern Sante Fe',
        'NVRR': 'Napa Valley Railroad',
        'NCRY': 'Niles Canyon Railway',
        'PHL': 'Pacific Harbor Line',
        'UP': 'Union Pacific',
        'SDNR': 'San Diego Northern Railroad',
        'MET': 'Modesto & Empire Traction Company',
        'SCRRA': 'Southern California Regional Rail Authority',
        'OERM': 'Orange Empire Railway Museum',
        'SDMTS': 'San Diego Metropolitan Transit System',
        'ACTA': 'Union Pacific, Burlington Nothern Sante Fe',
        'SJVR': 'San Joaquin Valley Railroad',
        'PCJPB': 'Peninsula Corridor Joint Powers Board',
        'MCR': 'McCloud Railway'
    }

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # workspaces (ArcPy -> FGDBs; open-source -> folders)
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(
        workspace, hazard_nickname, today_string
    )

    writeMessages(log_file_path, f"### {hazard_nickname.upper()} UPDATE ###\n")

    try:
        if ARCPY_AVAILABLE:
            arcpy.env.overwriteOutput = True  # type: ignore

            # open MXD and export layer
            script_path = os.path.dirname(os.path.abspath(__file__))
            mxd_path = os.path.join(script_path, r"templates\FeatureService_Layers.mxd")

            writeMessages(log_file_path, "Exporting feature class from template MXD", False)
            # exportFeatureServiceLayer() supports arcpy.mapping (ArcMap) and arcpy.mp (Pro) in our helper
            fc = exportFeatureServiceLayer(mxd_path, "", mxd_layer_name, processing_gdb, output_name)

            # check required field
            current_fields = [f.name for f in arcpy.ListFields(fc)]  # type: ignore
            if input_railway_name_field not in current_fields:
                msg = f"\n!!! ERROR !!!\nRequired field [{input_railway_name_field}] missing in Railroad layer.\n"
                writeMessages(log_file_path, msg, msg_type='warning')
                return None

            # add Fullname if needed
            if railway_name_field not in current_fields:
                arcpy.AddField_management(fc, railway_name_field, "TEXT", field_length=255)  # type: ignore

            # translate names
            missing_values = set()
            with arcpy.da.UpdateCursor(fc, [input_railway_name_field, railway_name_field]) as ucur:  # type: ignore
                for row in ucur:
                    code = row[0]
                    if code in railroad_owner_dict:
                        long_name = railroad_owner_dict[code]
                    else:
                        long_name = 'N/A'              # <-- fixed from 'N\A'
                        if code not in (None, ''):
                            missing_values.add(code)
                    ucur.updateRow([code, long_name])

            if missing_values:
                m = (
                    "\n!!! WARNING !!!\n"
                    f"Values not found in mapping for field [{input_railway_name_field}]: {sorted(missing_values)}\n"
                    "These records were assigned a value of 'N/A'\n"
                )
                writeMessages(log_file_path, m, msg_type='warning')

            # timestamp field
            addDTField(fc, last_updated_field)

            # (optional) project to output_sr_wkid into final_gdb (kept simple: copy into natural hazards gdb)
            final_natural_hazard_layer_path = os.path.join(naturalhazards_gdb, output_name)
            final_natural_hazard_layer = arcpy.Copy_management(fc, final_natural_hazard_layer_path)  # type: ignore

            writeMessages(log_file_path, "\tSUCCESS\n")
            return final_natural_hazard_layer

        # ---------------- Open-source path ----------------
        if not layer_url:
            writeMessages(
                log_file_path,
                "ArcPy not available. Provide `layer_url` (FeatureServer/MapServer layer REST URL) for open-source path.",
                msg_type='warning'
            )
            return None

        # download layer to gpkg via esridump
        writeMessages(log_file_path, "Downloading railroad layer via REST...", False)
        gpkg_path = extractGeoJson(layer_url, output_name, gis_data_folder, sr_wkid=output_sr_wkid)
        if not gpkg_path:
            writeMessages(log_file_path, "Failed to download railroad layer.", msg_type='warning')
            return None

        # map names with GeoPandas
        gp, sh, pj, io_driver = _lazy_import_gis()
        gdf = gp.read_file(gpkg_path, layer=output_name)

        # add fullname + timestamp
        def map_name(code):
            if code in railroad_owner_dict:
                return railroad_owner_dict[code]
            return 'N/A'

        gdf[railway_name_field] = gdf.get(input_railway_name_field, "").map(map_name)
        gdf[last_updated_field] = today

        # write final gpkg in final folder
        final_gpkg = os.path.join(final_gdb if os.path.isdir(final_gdb) else os.path.dirname(final_gdb),
                                  f"{output_name}_{today_string}.gpkg")
        if os.path.exists(final_gpkg):
            os.remove(final_gpkg)
        gdf.to_file(final_gpkg, layer=output_name, driver="GPKG")

        # also write to the "naturalhazards_gdb" target
        if naturalhazards_gdb.lower().endswith(".gpkg"):
            nat_gpkg = naturalhazards_gdb
        elif naturalhazards_gdb.lower().endswith(".gdb"):
            nat_gpkg = os.path.splitext(naturalhazards_gdb)[0] + ".gpkg"
            writeMessages(log_file_path, f"ArcPy not available; writing GeoPackage instead of FileGDB: {nat_gpkg}", msg_type='warning')
        else:
            if os.path.isdir(naturalhazards_gdb):
                nat_gpkg = os.path.join(naturalhazards_gdb, "naturalhazards.gpkg")
            else:
                root, ext = os.path.splitext(naturalhazards_gdb)
                nat_gpkg = naturalhazards_gdb if ext.lower() == ".gpkg" else f"{root}.gpkg"

        if os.path.exists(nat_gpkg):
            os.remove(nat_gpkg)
        gdf.to_file(nat_gpkg, layer=output_name, driver="GPKG")

        writeMessages(log_file_path, "\tSUCCESS\n")
        return f"gpkg:{nat_gpkg}#{output_name}"

    except Exception as e:
        writeMessages(log_file_path, f"\n!!! ERROR !!!\n{e}", msg_type='warning')
        return None
