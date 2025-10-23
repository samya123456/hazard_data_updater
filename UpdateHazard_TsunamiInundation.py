from NaturalHazardUpdaterTool_Functions import *

def runTsunamiInundaiton(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb, supplemental_flood_fc):
    ### These variables should not change ###
    download_link = r"https://www.conservation.ca.gov/cgs/Documents/Publications/Tsunami-Maps/CGS_Tsunami_Hazard_Area_for_Emergency_Planning.zip"
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "Supplemental_Flood_Hazards"
    hazard_nickname = "Tsunami Inundation"

    source_field = 'Source'
    source = 'California Department of Conservation'

    county_field = 'County'
    zone_field = 'Zone'

    # query for subsetting and Supp flood hazard layer
    flood_hazard_field = 'Flooding_Hazard'
    tsunami_hazard_type = 'Tsunami'

    input_tsunami_query = "Label = 'Yes, Tsunami Hazard Area'"  # only these records from the input tsunami layer are added to supplimental flood

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
        driver.get(download_link)
        time.sleep(30)  # allow plenty of time for the download to complete

        downloaded_zip = os.listdir(other_data_folder)[0]
        downloaded_zip_path = os.path.join(other_data_folder, downloaded_zip)

        # extract the zip file
        with ZipFile(downloaded_zip_path, "r") as zip_reader:
            zip_reader.extractall(gis_data_folder)

        unzipped_folder = os.path.join(gis_data_folder, downloaded_zip.rstrip('.zip'))

        # process data
        arcpy.env.workspace = unzipped_folder

        shapefile = arcpy.ListFeatureClasses("*Area*", "Polygon")[0]

        arcpy.DeleteField_management(shapefile, "OBJECTID")

        output_sr = arcpy.SpatialReference(output_sr_wkid)
        projected_tsunami_fc = os.path.join(processing_gdb, "projected_tsunami_fc")
        arcpy.Project_management(shapefile, projected_tsunami_fc, output_sr)

        # remove current tsunami features from supp flood
        subset_supplemental_flood_fc = os.path.join(processing_gdb, "suppflood_noTsnunami")
        arcpy.CopyFeatures_management(supplemental_flood_fc, subset_supplemental_flood_fc)

        suppflood_fl = "suppflood_fl"
        supp_flood_query = "{} = '{}'".format(flood_hazard_field, tsunami_hazard_type)
        arcpy.MakeFeatureLayer_management(subset_supplemental_flood_fc, suppflood_fl)
        arcpy.SelectLayerByAttribute_management(suppflood_fl, "NEW_SELECTION", supp_flood_query)
        arcpy.DeleteFeatures_management(suppflood_fl)

        # subset input to query specified
        subset_tsunami_features = os.path.join(processing_gdb, "tsunami_fc")
        arcpy.Select_analysis(projected_tsunami_fc, subset_tsunami_features, input_tsunami_query)

        # add required fields

        required_fields = ['County', zone_field, source_field, flood_hazard_field, 'last_updated']

        if county_field.upper() == "COUNTY":
            pass
        else:
            arcpy.AlterField_management(subset_tsunami_features, county_field, "County", "County")

        arcpy.AddField_management(subset_tsunami_features, zone_field, "TEXT", field_length=5)
        arcpy.CalculateField_management(subset_tsunami_features, zone_field, "'IN'", "PYTHON_9.3")

        arcpy.AddField_management(subset_tsunami_features, source_field, "TEXT", field_length=60)
        arcpy.CalculateField_management(subset_tsunami_features, source_field, "'{}'".format(source), "PYTHON_9.3")

        arcpy.AddField_management(subset_tsunami_features, flood_hazard_field, "TEXT", field_length=100)
        arcpy.CalculateField_management(subset_tsunami_features, flood_hazard_field, "'{}'".format(tsunami_hazard_type), "PYTHON_9.3")

        addDTField(subset_tsunami_features)

        # delete unwanted fields from new tsunami fc
        drop_fields = [f.name for f in arcpy.ListFields(subset_tsunami_features) if f.name not in required_fields and not f.required]
        arcpy.DeleteField_management(subset_tsunami_features, drop_fields)

        merged_fc = os.path.join(final_gdb, output_name)
        merge_fc_list = [subset_tsunami_features,subset_supplemental_flood_fc]
        arcpy.Merge_management(merge_fc_list, merged_fc)

        final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
        arcpy.CopyFeatures_management(merged_fc, final_natural_hazard_layer)

        m = "\tSUCCESS\n"
        writeMessages(log_file_path, m)
        driver.quit()
        return final_natural_hazard_layer
    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        driver.quit()
        return None






