from NaturalHazardUpdaterTool_Functions import *

def runCAFireDistricts(workspace, chrome_driver_path, log_file_path, ancillary_gdb):
    """
    data is from  CA Natural Resources Agency GIS
    https://gis.data.cnra.ca.gov/datasets/CALFIRE-Forestry::california-local-fire-districts/about
    https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/California_Local_Fire_Districts/FeatureServer/0

    :param workspace:
    :param chrome_driver_path:
    :param log_file_path:
    :param ancillary_gdb:
    :return:
    """
    layer_name = 'California Fire Districts'  # As it appears in the template mxd

    corrections = [
        {
            'field': 'Phone',  # the field to be modified
            'query': "Name = Name",  # the condition
            'value': "(858) 974-5999"  # new value getting assigned to 'field'
        }
    ]

    ### These variables should not change ###

    output_name = "California_Fire_Districts"
    hazard_nickname = "CalFire Fire Districts"

    phone_field = 'Phone'
    website_field = 'Website'
    district_name_field = 'Name'
    required_fields = [phone_field, website_field, district_name_field]

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
        writeMessages(log_file_path, "Extracting Fire Districts... ", False)
        districts_fc = exportFeatureServiceLayer(mxd, df, layer_name, processing_gdb,  "output_name")

        available_fields = [f.name for f in arcpy.ListFields(districts_fc)]
        fields_check = False
        m = "Missing Fields: "
        missing_fields = list()
        for required_field in required_fields:
            if required_field not in available_fields:
                missing_fields.append(required_field)

        if len(missing_fields) > 0:
            fields_check = False
            m += ", ".join(missing_fields)
            writeMessages(log_file_path, m)
        else:
            fields_check = True

        if fields_check:
            # perform any corrections
            recordCorrector(districts_fc, corrections)

            # fix phone numbers
            number_chars = [str(n) for n in range(10)]
            with arcpy.da.UpdateCursor(districts_fc, [phone_field]) as update_cursor:
                for row in update_cursor:
                    phone_raw = row[0]
                    phone_formatted = str()
                    if phone_raw is None or phone_raw.strip() == '':
                        phone_formatted = "Not-Provided"
                    else:
                        phone_digits = "".join([c for c in phone_raw if c in number_chars])
                        phone_formatted = "({}) {}-{}".format(phone_digits[:3], phone_digits[3:6], phone_digits[6:])
                    new_record = [phone_formatted]
                    update_cursor.updateRow(new_record)

            # change missing website to "Not-Provided
            with arcpy.da.UpdateCursor(districts_fc, [website_field]) as update_cursor:
                for row in update_cursor:
                    website_raw = row[0]
                    website_formatted = str()
                    if website_raw is None or website_raw.strip() == '':
                        website_formatted = "Not-Provided"
                    else:
                        website_formatted = website_raw.strip()
                    new_record = [website_formatted]
                    update_cursor.updateRow(new_record)

            addDTField(districts_fc)

            final_layer = os.path.join(ancillary_gdb, output_name)
            arcpy.CopyFeatures_management(districts_fc, final_layer)

            m = "\tSUCCESS\n"
            writeMessages(log_file_path, m)
            return final_layer
        else:
            m = "\tERROR Processing {}\n".format(layer_name)
            writeMessages(log_file_path, m)
            return None

    except Exception as e:
        writeMessages(log_file_path, e, msg_type='warning')
        return None
