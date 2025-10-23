from NaturalHazardUpdaterTool_Functions import *

def runCAJurisdictions(workspace, chrome_driver_path, log_file_path, ancillary_gdb):
    ### These variables should not change ###
    last_updated_field = "last_updated"

    output_name = "CA_Jurisdictions"
    hazard_nickname = "City County Jurisdictions"

    spellcheck_dict = {  # Uses Regex
        "Angels*": "Angels Camp",
        "California*": "California City",
        "La Ca*ada Flintridge": "La Canada Flintridge"
    }

    cities_input_city_field = "CITY"
    cities_input_county_field = "COUNTY"
    counties_input_county_field = "COUNTY_NAME"

    city_spatial_field = 'CITY_Spatial'
    county_spatial_field = 'COUNTY_Spatial'

    # get the map document that contains links to the feature services
    script_path = os.path.dirname(os.path.abspath(__file__))
    mxd_path = os.path.join(script_path, r"templates\FeatureService_Layers.mxd")

    """ MAIN """

    mxd = arcpy.mapping.MapDocument(mxd_path)
    df = arcpy.mapping.ListDataFrames(mxd, "")[0]

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    try:

        writeMessages(log_file_path, "Extracting County Boundaries... ", False)
        counties_fc = exportFeatureServiceLayer(mxd, df, "County Boundaries", processing_gdb,  "counties")

        writeMessages(log_file_path, "Extracting City Boundaries... ", False)
        cities_fc = exportFeatureServiceLayer(mxd, df, "City Boundaries", processing_gdb, "cities")

        arcpy.AlterField_management(cities_fc, cities_input_city_field, city_spatial_field, city_spatial_field, "TEXT", "50")
        arcpy.AlterField_management(cities_fc, cities_input_county_field, county_spatial_field, county_spatial_field, "TEXT", "50")
        arcpy.AddField_management(counties_fc, city_spatial_field, "TEXT", field_length="50")
        arcpy.AddField_management(counties_fc, county_spatial_field, "TEXT", field_length="50")
        arcpy.CalculateField_management(counties_fc, county_spatial_field, "!{}!".format(counties_input_county_field), "PYTHON_9.3")

        merged_jurisdictions = os.path.join(processing_gdb, "{}_Merged".format(output_name))
        arcpy.Update_analysis(counties_fc, cities_fc, merged_jurisdictions)

        # correct spelling of some cities to match our naming
        with arcpy.da.UpdateCursor(merged_jurisdictions, [county_spatial_field, city_spatial_field]) as updateCursor:
            for row in updateCursor:
                county = row[0].replace(' County', '')
                city = row[1]
                if city is None:
                    city = 'Unincorporated'
                for search, spelling in spellcheck_dict.iteritems():
                    if fnmatch(city, search):
                        city = spelling
                updated_record = [county, city]
                updateCursor.updateRow(updated_record)

        dissolved_jurisdictions = os.path.join(processing_gdb, "{}_Dissolved".format(output_name))
        arcpy.Dissolve_management(merged_jurisdictions, dissolved_jurisdictions, [county_spatial_field, city_spatial_field], "", "MULTI_PART", "DISSOLVE_LINES")
        addDTField(dissolved_jurisdictions)

        final_layer = os.path.join(ancillary_gdb, output_name)
        arcpy.CopyFeatures_management(dissolved_jurisdictions, final_layer)

        m = "\tSUCCESS\n"
        writeMessages(log_file_path, m)
        return final_layer

    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None
