from NaturalHazardUpdaterTool_Functions import *

def runFlood(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb, flood_zip_file_path):
    ### These variables should not change ###
    # FEMA Flood Map Service Center: Search All Products
    fema_flood_address = r"https://msc.fema.gov/portal/advanceSearch"
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    hazard_nickname = "Special Flood Hazard Layer"
    output_name = "CA_Flood"

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    """ FUNCTIONS """


    # create workspaces

    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    try:
        with ZipFile(flood_zip_file_path, "r") as zip_reader:
            zip_reader.extractall(gis_data_folder)

        file_name = os.path.basename(flood_zip_file_path).replace(".zip","")
        flood_hazard_gdb = os.path.join(gis_data_folder, file_name + ".gdb")

        # process the GIS data
        arcpy.env.workspace = flood_hazard_gdb
        arcpy.env.overwriteOutput = True

        flood_fc_name = "S_FLD_HAZ_AR"
        lomr_fc_name = "S_LOMR"


        try:
            flood_fc = arcpy.ListFeatureClasses(flood_fc_name)[0]

            have_gis_data = True
        except:
            have_gis_data = False
            m = "Error locating [{}] and/or [{}]Review Data in [{}] and update code\n\n------------ END LOG ------------".format(
                flood_fc_name, lomr_fc_name, flood_hazard_gdb)
            writeMessages(log_file_path, m)

        if have_gis_data is True:
            lomr_name = "LetterOfMapChange"
            # currently, we are only processing the Special Flood Hazard Area because the letter of map revisions are not available in a useful format

            # project data
            m = "Projecting..."
            writeMessages(log_file_path, m, False)
            out_sr = arcpy.SpatialReference(output_sr_wkid)
            final_flood_fc = os.path.join(final_gdb, output_name)
            arcpy.Project_management(flood_fc, final_flood_fc, out_sr)

            addDTField(final_flood_fc)

            flood_required_field = "SFHA_TF"
            if flood_required_field not in [f.name for f in arcpy.ListFields(final_flood_fc)]:
                m = "\n\n[{}] field not in Special Flood Hazard Layer!!!\nThis is a required field\n".format(
                    flood_required_field)
                writeMessages(log_file_path, m, msg_type='warning')

            final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
            arcpy.CopyFeatures_management(final_flood_fc, final_natural_hazard_layer)
            m = "\tSUCCESS\n"
            writeMessages(log_file_path, m)



            return final_natural_hazard_layer
    except Exception as e:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong: {}.\nLine number: {}".format(e.args[0], traceback.extract_stack()[-1][1])
        writeMessages(log_file_path, m, msg_type='warning')
        return None

