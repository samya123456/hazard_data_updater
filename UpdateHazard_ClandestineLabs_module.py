from NaturalHazardUpdaterTool_Functions import *

def runClandestineLabs(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    ### These variables should not change ###
    base_url = r"https://www.dea.gov/clan_lab/export/dea_clan_lab_export.csv?state=CA&date=[YEAR]&_wrapper_format=drupal_ajax"  # note the [YEAR] gets swapped out with the years of interest
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "ClandestineLabs"
    hazard_nickname = "Clandestine Labs"
    start_date = 2000  # start date of when Data started becoming available


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


        # go to address
        this_year = today.year

        for year in range(start_date, this_year +1):
            download_link = base_url.replace('[YEAR]', str(year))
            driver.get(download_link)
            time.sleep(5)  # allow plenty of time for the download to complete

        downloaded_csvs = os.listdir(other_data_folder)
        downloaded_csv_paths = [os.path.join(other_data_folder, downloaded_csv) for downloaded_csv in downloaded_csvs]

        # process data
        arcpy.env.workspace = gis_data_folder

        merged_table_name = "dea_table_merge"
        merged_table = os.path.join(processing_gdb, merged_table_name)
        arcpy.Merge_management(downloaded_csv_paths, merged_table)

        arcpy.AlterField_management(merged_table, "address1", "Address", "Address")

        lat_field = 'Latitude'
        long_field = 'Longitude'
        for field in [lat_field, long_field]:
            arcpy.AddField_management(merged_table, field, "DOUBLE")

        with arcpy.da.UpdateCursor(merged_table, ['address', 'city', lat_field, long_field]) as update_cursor:
            for row in update_cursor:
                address = row[0].strip()
                if row[1] is not None:
                    city = row[1].strip()
                else:
                    city = ''
                complete_address = "{}, {}, CA".format(address, city)
                latitude, longitude = forwardGeocode(complete_address)

                updated_row = [address, city, latitude, longitude]
                update_cursor.updateRow(updated_row)

        xy_event_layer = "event_layer"
        arcpy.MakeXYEventLayer_management(merged_table, long_field, lat_field, xy_event_layer, arcpy.SpatialReference(4326))

        featureclass_name = "{}_temp".format(output_name)
        featureclass = os.path.join(processing_gdb, featureclass_name)
        arcpy.FeatureClassToFeatureClass_conversion(xy_event_layer, processing_gdb, featureclass_name)

        output_sr = arcpy.SpatialReference(output_sr_wkid)
        projected_fc = os.path.join(processing_gdb, output_name)
        arcpy.Project_management(featureclass, projected_fc, output_sr)

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
