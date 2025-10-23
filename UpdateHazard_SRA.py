from NaturalHazardUpdaterTool_Functions import *

def runSRA(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb, jurisdictions_fc):
    """
    GO TO:
    https://osfm.fire.ca.gov/what-we-do/community-wildfire-preparedness-and-mitigation/fire-hazard-severity-zones

    Click "SRA FHSZ Data Effective April 1, 2024" (https://34c031f8-c9fd-4018-8c5a-4159cdff6b0d-cdn-endpoint.azureedge.net/-/media/osfm-website/what-we-do/community-wildfire-preparedness-and-mitigation/fire-hazard-severity-zones/fhszsra233gdb.zip?rev=2d584712566846bbbf87b169585b4705&hash=6BEC25A31025690E411872D44DBCA8F6)
    """
    sra_url = r'https://osfm.fire.ca.gov/what-we-do/community-wildfire-preparedness-and-mitigation/fire-hazard-severity-zones'
    input_sr_wkid = 4326  # WGS84
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    zone_field = "ZONE"
    jurisdiction_fields = ["CITY_Spatial", "COUNTY_Spatial"]
    output_name = "State_Responsibility_Area_Fire"
    hazard_nickname = "State Responsibility Area"


    # Used to convert the input fields to the current version of the table. If the fields are the same, not mapping is performed
    field_mappings = {
        "FHSZ_Description": "HAZ_CLASS"
    }

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

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

        driver.get(sra_url)
        time.sleep(5)

        xpath = '//*[@id="main-content"]/div[2]/div/div/div/div[5]/div[2]/div/ul[1]/li/a'
        download_element = driver.find_element_by_xpath(xpath)

        # scroll the screen so that the download button is in view
        actions = ActionChains(driver)
        actions.move_to_element(download_element).perform()
        time.sleep(1)

        clickToDownloadFile(download_element, other_data_folder)

        sra_zip = os.listdir(other_data_folder)[0]
        sra_zip_path = os.path.join(other_data_folder, sra_zip)

        with ZipFile(sra_zip_path, "r") as zip_reader:
            zip_reader.extractall(other_data_folder)

        sra_gdb = None
        for the_file in os.listdir(other_data_folder):
            if the_file.endswith(".gdb"):
                sra_gdb = os.path.join(other_data_folder, the_file)

        if sra_gdb is None:
            driver.close()
            m = "Error, Unable to Locate the SRA Geodatabase. No Update Performed".format(
                gis_data_folder)
            writeMessages(log_file_path, m, msg_type='warning')
            driver.close()
            return None

        else:
            arcpy.env.workspace = sra_gdb
            arcpy.env.overwriteOutput = True
            sra_features = arcpy.ListFeatureClasses()[0]
            output_sr = arcpy.SpatialReference(output_sr_wkid)  # WGS_1984_Web_Mercator_Auxiliary_Sphere

            # project data
            m = "Projecting Data..."
            writeMessages(log_file_path, m, False)

            sra_projected = os.path.join(final_gdb, output_name)
            arcpy.Project_management(sra_features, sra_projected, output_sr)

            # map fields
            for input_field, output_field in field_mappings.items():
                arcpy.AlterField_management(sra_projected, input_field, output_field, output_field)

            arcpy.AddField_management(sra_projected, zone_field, "TEXT", field_length=3)
            arcpy.CalculateField_management(sra_projected, zone_field, "'IN'", "PYTHON_9.3")

            # get all fields from SRA so we can preserver them later
            sra_fields = [f.name for f in arcpy.ListFields(sra_projected) if not f.required]

            # intersect sra and jurisdictions
            sra_jurisdiction_intersect = arcpy.Intersect_analysis([sra_projected, jurisdictions_fc], os.path.join(processing_gdb, "SRA_Jurisdiction_Intersect"))

            # dissolve...
            dissolve_fields = sra_fields + jurisdiction_fields
            final_output = arcpy.Dissolve_management(sra_jurisdiction_intersect, os.path.join(final_gdb, output_name), dissolve_fields)

            # add the last_update field
            addDTField(final_output)

            final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
            arcpy.CopyFeatures_management(final_output, final_natural_hazard_layer)

            m = "\tSUCCESS\n"
            writeMessages(log_file_path, m)
            driver.close()
            return final_natural_hazard_layer
    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None
