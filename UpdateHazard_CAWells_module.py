""" Updates the Gas + Oil Wells found in Commercial Reports (HE) """

from NaturalHazardUpdaterTool_Functions import *

def runAllWells(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    ### These variables should not change ###
    web_address = r"https://gis.conservation.ca.gov/portal/home/item.html?id=335e036c6a4f4cc39148ca2a9e0389c7"
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "Wells"
    hazard_nickname = "All Wells"

    expected_fields = ['API', 'WellStatus', 'OperatorNa']

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    # start Chrome
    chrome_options = webdriver.ChromeOptions()  # create chrome options object
    prefs = {
        'download.default_directory': other_data_folder}  # dictionary pointing to new update workspace for downloads
    chrome_options.add_experimental_option('prefs', prefs)
    chrome_options.add_argument("--start-maximized")
    driver = webdriver.Chrome(chrome_driver_path,
                              chrome_options=chrome_options)  # run chrome from the driver path with the new options

    try:

        # go to address
        driver.get(web_address)
        time.sleep(60)

        m = "Locating Download on page"
        writeMessages(log_file_path, m, False)

        download_button_xpath = '//*[@id="main-content-area"]/div[1]/aside/div/button[6]'
        download_button = driver.find_element_by_xpath(download_button_xpath)

        m = "Dowloading file"
        writeMessages(log_file_path, m, False)
        download_button.click()
        time.sleep(20) # the download should take less than 20 seconds

        download_zip = os.listdir(other_data_folder)[0]
        download_zip_path = os.path.join(other_data_folder, download_zip)

        m = "Extrating contents from zip file"
        writeMessages(log_file_path, m, False)

        # extract the zip file
        with ZipFile(download_zip_path, "r") as zip_reader:
            zip_reader.extractall(gis_data_folder)

        # get the extracted zip folder
        download_folder_contents = os.listdir(gis_data_folder)

        arcpy.env.workspace = gis_data_folder
        geothermal_shp = arcpy.ListFeatureClasses("*")[0]

        m = "Processing Data"
        writeMessages(log_file_path, m, False)

        output_fc = os.path.join(final_gdb, output_name)
        arcpy.Project_management(geothermal_shp, output_fc, arcpy.SpatialReference(output_sr_wkid))

        # map fields
        available_fields = [f.name for f in arcpy.ListFields(output_fc)]

        field_check, m = checkMissingFields(expected_fields, available_fields)

        if field_check is False:
            writeMessages(log_file_path, m, True, "warning")
            return None
        else:

            addDTField(output_fc)

            final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
            arcpy.CopyFeatures_management(output_fc, final_natural_hazard_layer)

            m = "\tSUCCESS\n"
            writeMessages(log_file_path, m)
            driver.quit()
            return final_natural_hazard_layer
    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        driver.quit()
        return None

