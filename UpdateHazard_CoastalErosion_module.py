from NaturalHazardUpdaterTool_Functions import *

def runCoastalBluffsErosion(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    ### These variables should not change ###
    download_link = r"https://www.pacinst.org/reports/sea_level_rise_data/Erosion_hz_yr2100.zip"
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "CA_Coastal_Bluffs"
    hazard_nickname = "Coastal Bluffs and Erosion"

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    try:

        # Get zip file
        filedata = urllib2.urlopen(download_link)
        the_data = filedata.read()

        download_zip_path = os.path.join(other_data_folder, "WebsiteDownload.zip")
        with open(download_zip_path, 'wb') as f:
            f.write(the_data)

        # extract the zip file
        with ZipFile(download_zip_path, "r") as zip_reader:
            zip_reader.extractall(gis_data_folder)

        arcpy.env.workspace = gis_data_folder

        shapefile = arcpy.ListFeatureClasses("*")[0]

        # no data contained in table, but there are erroneious fields. delete any not required field
        drop_fields = [f.name for f in arcpy.ListFields(shapefile) if not f.required]

        # add dummy field
        arcpy.AddField_management(shapefile, "ID", "SHORT")

        for field in drop_fields:
            arcpy.DeleteField_management(shapefile, field)

        projected_fc = os.path.join(processing_gdb, "{}_projected".format(output_name))
        arcpy.Project_management(shapefile, projected_fc, arcpy.SpatialReference(output_sr_wkid))

        addDTField(projected_fc)

        final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
        arcpy.CopyFeatures_management(projected_fc, final_natural_hazard_layer)

        m = "\tSUCCESS\n"
        writeMessages(log_file_path, m)
        return final_natural_hazard_layer
    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None






