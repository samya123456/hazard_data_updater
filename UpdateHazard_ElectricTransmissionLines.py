from NaturalHazardUpdaterTool_Functions import *

def runElectricTransmissionLines(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    ### These variables should not change ###
    # https://data.cnra.ca.gov/dataset/california-electric-transmission-lines --> Shapefile Download
    download_link = r"https://cecgis-caenergy.opendata.arcgis.com/datasets/CAEnergy::california-electric-transmission-lines.zip?outSR=%7B%22latestWkid%22%3A3857%2C%22wkid%22%3A102100%7D"
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "Electric_Transmission_Lines"
    hazard_nickname = "Major Electric Transmission Lines"

    field_mapping = {
        'kV': 'Voltage_CL'
    }

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
            zip_reader.extractall(other_data_folder)

        # get the extracted zip folder
        download_folder_contents = os.listdir(other_data_folder)

        shp_file = [f for f in download_folder_contents if f.endswith(('.shp'))][0]
        shp_file_path = os.path.join(other_data_folder, shp_file)

        # copy to processing GDB
        featureclass = os.path.join(processing_gdb, output_name)
        arcpy.FeatureClassToFeatureClass_conversion(shp_file_path, processing_gdb, output_name)

        # map fields
        current_fields = [f.name for f in arcpy.ListFields(featureclass)]
        expected_fields = field_mapping.keys()

        field_check, m = checkMissingFields(expected_fields, current_fields)

        if field_check is False:
            writeMessages(log_file_path, m, True, "warning")
            return None
        else:

            for field in field_mapping:
                output_field = field_mapping[field]
                arcpy.AlterField_management(featureclass, field, output_field, output_field)

            addDTField(featureclass)

            final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
            arcpy.CopyFeatures_management(featureclass, final_natural_hazard_layer)

            m = "\tSUCCESS\n"
            writeMessages(log_file_path, m)
            return final_natural_hazard_layer
    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None






