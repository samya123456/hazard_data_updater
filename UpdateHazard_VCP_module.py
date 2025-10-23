from NaturalHazardUpdaterTool_Functions import *

def runVCPHazard(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    ### These variables should not change ###
    download_link = r"https://ordsext.epa.gov/FLA/www3/acres_frs.kmz"
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "VCP"
    hazard_nickname = "Voluntary Cleanup Program"

    default_value = 'N/A'  # missing data is assigned this value

    field_mapping = {
        'Status': 'status_1',
        'ID': 'site_id',
        'ARC_Street': 'address',
        'Name': 'site_name'
    }


    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace,
                                                                                                        hazard_nickname,
                                                                                                        today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    try:
        # start Chrome
        chrome_options = webdriver.ChromeOptions()  # create chrome options object
        prefs = {
            'download.default_directory': other_data_folder}  # dictionary pointing to new update workspace for downloads
        chrome_options.add_experimental_option('prefs', prefs)
        chrome_options.add_argument("--start-maximized")
        driver = webdriver.Chrome(chrome_driver_path,
                                  chrome_options=chrome_options)  # run chrome from the driver path with the new options

        # go to address
        driver.get(download_link)
        time.sleep(30)  # allow plenty of time for the download to complete

        #download the file
        downloaded_kmz = os.listdir(other_data_folder)[0]
        downloaded_kmz_path = os.path.join(other_data_folder, downloaded_kmz)

        vcp_gdb_name = "VCP_data"
        vcp_gdb_path = os.path.join(gis_data_folder, vcp_gdb_name + ".gdb")
        arcpy.KMLToLayer_conversion(downloaded_kmz_path, gis_data_folder, vcp_gdb_name, "NO_GROUNDOVERLAY")

        # process the data
        feature_dataset = os.path.join(vcp_gdb_path, 'Placemarks')
        arcpy.env.workspace = feature_dataset

        fc = arcpy.ListFeatureClasses("*")[0]

        output_sr = arcpy.SpatialReference(output_sr_wkid)
        projected_fc = os.path.join(processing_gdb, "projected_fc")
        arcpy.Project_management(fc, projected_fc, output_sr)

        # add required fields
        required_fields = [k for k in field_mapping.keys()]

        current_fields = [f.name for f in arcpy.ListFields(projected_fc)]

        field_check, m = checkMissingFields(required_fields, current_fields)

        if field_check is False:
            writeMessages(log_file_path, m, True, "warning")

            m = "Assigning Missing Data to [{}]".format(default_value)
            writeMessages(log_file_path, m, True, "warning")

            missing_fields = [v for k,v in field_mapping.items() if k not in current_fields]
            for field in missing_fields:
                arcpy.AddField_management(projected_fc, field, "TEXT", field_length=255)
                arcpy.CalculateField_management(projected_fc, field, "'{}'".format(default_value), "PYTHON_9.3")

        for field in field_mapping:
            if field in current_fields:
                output_field = field_mapping[field]
                arcpy.AlterField_management(projected_fc, field, output_field, output_field)

        addDTField(projected_fc)

        final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
        arcpy.CopyFeatures_management(projected_fc, final_natural_hazard_layer)

        m = "\tSUCCESS\n"
        writeMessages(log_file_path, m)
        driver.quit()
        return final_natural_hazard_layer

    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        driver.quit()
        return None






