from NaturalHazardUpdaterTool_Functions import *

def runUST(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    ### These variables should not change ###
    script_path = os.path.dirname(os.path.abspath(__file__))
    mxd_path = os.path.join(script_path, r"templates\FeatureService_Layers.mxd")
    mxd_layer_name = "Underground Storage Tank (UST) Facilities"  # the service layer name (https://services.arcgis.com/cJ9YHowT8TU7DUyn/ArcGIS/rest/services/UST_Finder_Feature_Layer_2/FeatureServer/0)
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "UST"
    hazard_nickname = "Underground Storage Tanks"

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    field_mapping = {
        'Facility_ID':'site_id',
        'Name':'site_name',
        'Address':'address',
        'Facility_Status':'status_1'
    }

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))
    try:
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
            m = "\n!!! WARNING !!!\nThe following fields do not exist:\n{}\n".format(
                missing_fields)
            writeMessages(log_file_path, m, msg_type='warning')
        else:
            # map fields
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
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None





