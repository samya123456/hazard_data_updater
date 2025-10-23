from NaturalHazardUpdaterTool_Functions import *

def runMiningOperations(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    ### These variables should not change ###
    # get the map document that contains links to the feature services
    script_path = os.path.dirname(os.path.abspath(__file__))
    mxd_path = os.path.join(script_path, r"templates\FeatureService_Layers.mxd")
    mxd_layer_name = "MOL.DOC.allmines84"  # the service layer name
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "Mining_Operations"  # the name of the dataset in out database
    hazard_nickname = "Mining Operations"

    # This comm fields need to be included (the hazardDef table is fucked up for HE so cannot be trusted)
    commercial_report_fields = {
        'Rec_Status': 'Reclamatio'
    }

    # report fields (found in RES hazardDef on right and input fields on left)
    field_mapping = {
        'MineName': 'Mine_Name',
        'MineStatus': 'Mine_Status',
        'Operator': 'Operator',
        'Rec_Status': 'Reclamation_Status'
    }

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    try:
        # Open the mxd for getting the feature layer
        mxd = arcpy.mapping.MapDocument(mxd_path)
        df = arcpy.mapping.ListDataFrames(mxd, "")[0]
        m = "Exporting Featureclass from Template MXD"
        writeMessages(log_file_path, m, False)
        fc = exportFeatureServiceLayer(mxd, df, mxd_layer_name, processing_gdb, output_name)

        current_fields = [f.name for f in arcpy.ListFields(fc)]
        expected_fields = field_mapping.keys()
        missing_fields = list()
        for f in expected_fields:
            if f not in current_fields:
                missing_fields.append(f)

        if len(missing_fields) > 0:
            m = "\n!!! ERROR !!!\nThe following fields do not exist in the Mining Operation Hazard Layer:\n{}\n".format(missing_fields)
            writeMessages(log_file_path, m, msg_type='warning')
        else:
            # map fields
            for input_field, output_field in commercial_report_fields.items():
                arcpy.AddField_management(fc, output_field, "TEXT", field_length=255)
                arcpy.CalculateField_management(fc, output_field, "!{}!".format(input_field), "PYTHON_9.3")

            for input_field, output_field in field_mapping.items():
                if input_field != output_field:
                    arcpy.AlterField_management(fc, input_field, output_field, output_field)

            addDTField(fc)

            final_natural_hazard_layer_path = os.path.join(naturalhazards_gdb, output_name)
            final_natural_hazard_layer = arcpy.Copy_management(fc, final_natural_hazard_layer_path)

            m = "\tSUCCESS\n"
            writeMessages(log_file_path, m)

            return final_natural_hazard_layer

    except:
        "\n!!! ERROR !!!\nSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None

