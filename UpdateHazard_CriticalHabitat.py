from NaturalHazardUpdaterTool_Functions import *

def runCriticalHabitat(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb, cnndb_zip, fs_zip_file):
    ### These variables should not change ###
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "CA_Critical_Habitat_Animals"
    hazard_nickname = "Critical Animal Habitat (CNNDB)"

    output_common_name_field = 'COMNAME'
    output_description_field = 'DESCRIPTIO'

    # layer is made of two parts. CNNDB and FWS
    cnndb_name = ["cnndb", "California Department of Fish and Wildlife"]  # shortname, long name
    cnndb_query = "FEDLIST = 'Endangered' AND ((Symbology BETWEEN 200 AND 299) OR (Symbology BETWEEN 300 AND 399) OR (Symbology BETWEEN 800 AND 899) OR(Symbology BETWEEN 900 AND 999))"

    cnndb_field_mapping = {
        'CNAME': output_common_name_field
    }

    fws_name = ["fws", "US Fish and Wildlife Service"]  # shortname, long name

    # https://ecos.fws.gov/ecp/report/critical-habitat

    fws_service_layer_name = 'Critical Habitat - Polygon Features - Final'
    #fws_query = "listing_status = 'Endangered'"  # featureclass sql
    fws_query = "listing_st = 'Endangered'"  # shapefile sql

    fws_field_mapping = {
        'comname': output_common_name_field
    }

    """
    # get the map document that contains links to the feature services
    script_path = os.path.dirname(os.path.abspath(__file__))
    mxd_path = os.path.join(script_path, r"templates\FeatureService_Layers.mxd")

    mxd = arcpy.mapping.MapDocument(mxd_path)
    df = arcpy.mapping.ListDataFrames(mxd, "")[0]
    """

    """ FUNCTIONS """

    def processCriticalHabitatLayer(fc, query, field_mapping, name):
        short_name = name[0]
        source = name[1]
        # subset to query specified
        subset_features = os.path.join(processing_gdb, output_name + "_{}".format(short_name))
        arcpy.Select_analysis(fc, subset_features, query)

        current_fields = [f.name for f in arcpy.ListFields(subset_features)]
        expected_fields = field_mapping.keys()

        field_check, m = checkMissingFields(expected_fields, current_fields)

        if field_check is False:
            writeMessages(log_file_path, m, True, "warning")
            return None
        else:
            # Map data
            for input_field, output_field in field_mapping.items():
                if input_field.upper() == output_field.upper():
                    pass
                else:
                    arcpy.AlterField_management(subset_features, input_field, output_field, output_field)

            # populate description field the source of the data
            arcpy.AddField_management(subset_features, output_description_field, "TEXT", field_length=100)
            arcpy.CalculateField_management(subset_features, output_description_field, "'{}'".format(source), "PYTHON_9.3")

            # add required fields
            zone_field = 'ZONE'
            arcpy.AddField_management(subset_features, zone_field, "TEXT", field_length=5)
            arcpy.CalculateField_management(subset_features, zone_field, "'IN'", "PYTHON_9.3")

            addDTField(subset_features)

        return subset_features

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))


    try:
        # CNNDB piece
        # extract the zip file

        with ZipFile(cnndb_zip, "r") as zip_reader:
            zip_reader.extractall(other_data_folder)

        # process data
        arcpy.env.workspace = other_data_folder

        shapefile = arcpy.ListFeatureClasses("*cnddb*", "Polygon")[0]

        output_sr = arcpy.SpatialReference(output_sr_wkid)
        cnndb_projected_fc = os.path.join(processing_gdb, "cnddb_projected_fc")
        arcpy.Project_management(shapefile, cnndb_projected_fc, output_sr)

        cnndb_fc = processCriticalHabitatLayer(cnndb_projected_fc, cnndb_query, cnndb_field_mapping, cnndb_name)

        # FWS piece
        with ZipFile(fs_zip_file, "r") as zip_reader:
            zip_reader.extractall(other_data_folder)

        fws_fc = arcpy.ListFeatureClasses("*crithab_poly*", "Polygon")[0]

        #fws_fc = exportFeatureServiceLayer(mxd, df, fws_service_layer_name, processing_gdb, "fws_crithab")

        fws_projected_fc = os.path.join(processing_gdb, "fws_projected_fc")

        arcpy.Project_management(fws_fc, fws_projected_fc, output_sr)

        fws_fc = processCriticalHabitatLayer(fws_projected_fc, fws_query, fws_field_mapping, fws_name)

        # merge the two results
        #merged_features = arcpy.Merge_management([fws_fc, cnndb_fc], os.path.join(final_gdb, output_name))
        merged_features = arcpy.Merge_management([fws_fc, cnndb_fc], os.path.join(processing_gdb, "Merged_Features"))

        dissolve_fields = ['COMNAME','DESCRIPTIO','last_updated','ZONE']
        dissolved_features = arcpy.management.Dissolve(merged_features, os.path.join(final_gdb, output_name), dissolve_fields, None, "SINGLE_PART", "DISSOLVE_LINES")
        final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
        arcpy.CopyFeatures_management(dissolved_features, final_natural_hazard_layer)

        m = "\tSUCCESS\n"
        writeMessages(log_file_path, m)
        return final_natural_hazard_layer
    except Exception as error:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong:\n{}\n".format(error)
        writeMessages(log_file_path, m, msg_type='warning')
        return None






