from NaturalHazardUpdaterTool_Functions import *

def runERNSHazard(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):

    def convertCoordToDec(deg, min, sec):
        decimal_deg = float(deg) + (float(min) + (float(sec)/60.0))/60.0
        return decimal_deg

    ### These variables should not change ###
    download_link = r"https://nrc.uscg.mil/FOIAFiles/Current.xlsx"
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "ERNS"
    hazard_nickname = "Emergency Response Notification System"

    excel_sheet_name = "INCIDENT_COMMONS"  # sheet name as appears in the XLSX spreadsheet

    address_component_fields = ['LOCATION_ADDRESS', 'LOCATION_NEAREST_CITY', 'LOCATION_STATE', 'LOCATION_ZIP']
    latitude_fields = ['LAT_DEG', 'LAT_MIN', 'LAT_SEC']  # lat/long fields, The quad field has errors so assuming everything is N + W
    longitude_fields = ['LONG_DEG', 'LONG_MIN', 'LONG_SEC']

    subset_query = "LOCATION_STATE = 'CA'"

    default_value = 'N/A'  # missing data is assigned this value

    field_mapping = {
        'SEQNOS': 'SEQNOS',
        'DESCRIPTION_OF_INCIDENT': 'Description'
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
        driver = webdriver.Chrome(chrome_driver_path, chrome_options=chrome_options)  # run chrome from the driver path with the new options

        # go to address
        driver.get(download_link)
        time.sleep(30)  # allow plenty of time for the download to complete

        #download the file
        downloaded_xlsx = os.listdir(other_data_folder)[0]
        downloaded_xlsx_path = os.path.join(other_data_folder, downloaded_xlsx)

        erns_table = os.path.join(processing_gdb, "erns_table")
        arcpy.ExcelToTable_conversion(downloaded_xlsx_path, erns_table, excel_sheet_name)

        erns_subset_table = os.path.join(processing_gdb, "erns_subset")
        arcpy.TableSelect_analysis(erns_table, erns_subset_table, subset_query)

        record_count = int(arcpy.GetCount_management(erns_subset_table).getOutput(0))
        failed_locations = 0  # stores addresses that could not be geocoded

        lat_field = 'LATITUDE'
        long_field = 'LONGITUDE'
        arcpy.AddField_management(erns_subset_table, lat_field, 'DOUBLE')
        arcpy.AddField_management(erns_subset_table, long_field, 'DOUBLE')

        cursor_fields = address_component_fields + latitude_fields + longitude_fields + [lat_field, long_field]

        with arcpy.da.UpdateCursor(erns_subset_table, cursor_fields) as update_cursor:
            for row in update_cursor:
                try:  # test if latitude is available (any strings that are numeric)
                    lat_deg, lat_min, lat_sec = [float(row[cursor_fields.index(field)]) for field in latitude_fields]
                    long_deg, long_min, long_sec = [float(row[cursor_fields.index(field)]) for field in longitude_fields]
                    decimal_lat = convertCoordToDec(lat_deg, lat_min, lat_sec)
                    decimal_long = convertCoordToDec(-long_deg, long_min, long_sec)  # !!! NOTE: THIS IS ASSUMED TO BE WEST !!!
                except ValueError:
                    # if lat long is not available, geocode
                    address_complete = " ".join(
                        [row[i] for i in [cursor_fields.index(f) for f in address_component_fields]]).strip()
                    decimal_lat, decimal_long = forwardGeocode(address_complete)
                    if decimal_lat is None:
                        failed_locations += 1

                row[cursor_fields.index(lat_field)] = decimal_lat
                row[cursor_fields.index(long_field)] = decimal_long
                update_cursor.updateRow(row)

        failed_percent = round(float(failed_locations)/float(record_count), 1)
        m = "{} ({}%) Of The Records Had Invalid Location Information".format(failed_locations, failed_percent)
        writeMessages(log_file_path, m, True, "warning")

        # covert to Featureclass
        event_layer = "erns_event_layer"
        arcpy.MakeXYEventLayer_management(erns_subset_table, long_field, lat_field, event_layer, arcpy.SpatialReference(4326))

        erns_fc = os.path.join(processing_gdb, "{}_points".format(output_name))
        arcpy.CopyFeatures_management(event_layer,erns_fc)

        projected_fc = os.path.join(processing_gdb, output_name)
        output_sr = arcpy.SpatialReference(output_sr_wkid)
        arcpy.Project_management(erns_fc, projected_fc, output_sr)

        # add required fields
        required_fields = [k for k in field_mapping.keys()]

        current_fields = [f.name for f in arcpy.ListFields(projected_fc)]

        field_check, m = checkMissingFields(required_fields, current_fields)

        if field_check is False:
            writeMessages(log_file_path, m, True, "warning")

            m = "Assigning Missing Data to [{}]".format(default_value)
            writeMessages(log_file_path, m, True, "warning")

            missing_fields = [v for k, v in field_mapping.items() if k not in current_fields]
            for field in missing_fields:
                arcpy.AddField_management(projected_fc, field, "TEXT", field_length=255)
                arcpy.CalculateField_management(projected_fc, field, "'{}'".format(default_value), "PYTHON_9.3")

        for field in field_mapping:
            if field in current_fields:
                output_field = field_mapping[field]
                if output_field == field:
                    pass
                else:
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






