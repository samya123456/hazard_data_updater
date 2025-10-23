from NaturalHazardUpdaterTool_Functions import *

def runSolidWasteFacilities(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    ### These variables should not change ###
    web_address = r"https://www2.calrecycle.ca.gov/SolidWaste/Site/DataExport"
    input_sr_wkid = 4326  # GCS_WGS_1984
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "Solid_Waste_Facilities"
    hazard_nickname = "Solid Waste Facilities"

    ### Input <--> Output Fields ###

    sitename_output_field = 'SITENAME'
    sitename_input_fields = ['Name', 'Site_Operational_Status']

    location_output_field = 'LOCATION'
    location_input_fields = ['Street_Address', 'City', 'State', 'ZIP_Code']

    field_mappings = {
        'SWIS_Number':'SWISNO',
        'Incorporated_City': 'PLACENAME',
        }

    missing_fields = {  # these are expected to be in the data, but currently do not exist, they get placeholder values
        'ACTIVITY': 'N/A',
        'OPERATOR': 'N/A'
    }

    latitude_field = 'Latitude'
    longitude_field = 'Longitude'

    ### Input <--> Output Fields ###

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname,today_string)

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
        time.sleep(5)

        # Check "Site" for Site Data Export Parameter
        site_selection_xpath = '//*[@id="SelectedDataFile_1"]'
        site_selection = driver.find_element_by_xpath(site_selection_xpath)
        site_selection.click()

        # Check "CSV" for Site Data Export Parameter
        data_format_selection_xpath = '//*[@id="SelectedFileFormat_2"]'
        data_format_selection = driver.find_element_by_xpath(data_format_selection_xpath)
        data_format_selection.click()
        time.sleep(3)

        # download the file
        download_button_xpath = '//*[@id="DownloadButton"]'
        download_button = driver.find_element_by_xpath(download_button_xpath)
        download_button.click()

        # download the file
        time.sleep(3)
        waiting = True
        downloaded_files = os.listdir(other_data_folder)
        downloaded_file_count = len(downloaded_files)
        while waiting:
            time.sleep(0.1)
            downloaded_file_count = len(os.listdir(other_data_folder))
            if downloaded_file_count > 0:
                waiting = False

        downloaded_csv = os.listdir(other_data_folder)[0]
        downloaded_csv_path = os.path.join(other_data_folder, downloaded_csv)

        with open(downloaded_csv_path, "r") as file_obj:
            reader = file_obj.readlines()
            raw_data = [r.replace('\x00', '').rstrip(',\r\n') for r in reader]

        original_header = raw_data.pop(0).split(',')
        header = [h.strip().replace(' ', '_') for h in original_header]
        data = [r.lstrip('"').rstrip('",').split('","') for r in raw_data]

        m = "Converting To Point Featureclass..."
        writeMessages(log_file_path, m, False)

        temp_fc, missed_records = tableToPoints(header, data, latitude_field, longitude_field, input_sr_wkid, processing_gdb, "{}_temp".format(output_name))

        if len(missed_records) > 0:
            m = "Warning, {} records could not be processed due to unknow error:\n".format(len(missed_records))
            for missed_record_i, missed_record in enumerate(missed_records):
                if missed_record_i < 20:
                    m += "\t{}\n".format(missed_record)
                else:
                    m += "\t..."
                    break
            writeMessages(log_file_path, m, msg_type='warning')

        #Sitename field
        sitename_field_mapping_errors = False
        for field in sitename_input_fields:
            if field not in header:
                sitename_field_mapping_errors = True
                m = "Error! The [{}] Component Field [{}] was not found in the input data\n".format(sitename_output_field, field)
                writeMessages(log_file_path, m, msg_type='warning')

        if not sitename_field_mapping_errors:
            expression = "!{}! + '- (' + !{}! +')'".format(sitename_input_fields[0], sitename_input_fields[1])
            arcpy.AddField_management(temp_fc, sitename_output_field, "TEXT", field_length=255)
            arcpy.CalculateField_management(temp_fc, sitename_output_field, expression, "PYTHON_9.3")

        #location/address field
        location_field_mapping_errors = False
        for field in location_input_fields:
            if field not in header:
                location_field_mapping_errors = True
                m = "Error! The [{}] Component Field [{}] was not found in the input data\n".format(location_output_field, field)
                writeMessages(log_file_path, m, msg_type='warning')

        if not location_field_mapping_errors:
            expression = "!" + "! + ' ' + !".join(location_input_fields) + "!.strip().replace('  ',' ')"
            arcpy.AddField_management(temp_fc, location_output_field, "TEXT", field_length=255)
            arcpy.CalculateField_management(temp_fc, location_output_field, expression, "PYTHON_9.3")

        # mapped fields
        field_mapping_errors = False
        for field in field_mappings.keys():
            if field not in header:
                field_mapping_errors = True
                m = "Error! The  Field [{}] was not found in the input data\n".format(field)
                writeMessages(log_file_path, m, msg_type='warning')

        if not field_mapping_errors:
            for input_field, output_field in field_mappings.items():
                arcpy.AlterField_management(temp_fc, input_field, output_field, output_field)

        if not any([sitename_field_mapping_errors, location_field_mapping_errors, field_mapping_errors]):
            m = "All Fields Mapping Successfully"
            writeMessages(log_file_path, m, False)

            # add any missing fields
            if len(missing_fields) > 0:
                for field, value in missing_fields.items():
                    arcpy.AddField_management(temp_fc, field, "TEXT", field_length=len(value))
                    arcpy.CalculateField_management(temp_fc, field, "'{}'".format(value), "PYTHON_9.3")

            # project data
            m = "Projecting..."
            writeMessages(log_file_path, m, False)
            output_sr = arcpy.SpatialReference(output_sr_wkid)
            projected_fc = os.path.join(final_gdb, output_name)
            arcpy.Project_management(temp_fc, projected_fc, output_sr)
            addDTField(projected_fc)

            final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
            arcpy.CopyFeatures_management(projected_fc, final_natural_hazard_layer)

            m = "\tSUCCESS\n"
            writeMessages(log_file_path, m)
            driver.quit()
            return final_natural_hazard_layer
    except:
        m = "\t!!! ERROR !!!\nSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        driver.quit()
        return None




