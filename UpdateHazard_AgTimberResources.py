from NaturalHazardUpdaterTool_Functions import *

def runAgTimberResources(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    ### These variables should not change ###
    script_path = os.path.dirname(os.path.abspath(__file__))
    mxd_path = os.path.join(script_path, r"templates\FeatureService_Layers.mxd")
    ag_mxd_layer_name = "General Plan Resource Agriculture"
    timber_mxd_layer_name = "Resource Timber"

    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    ag_resource_output_name = "AgResourceArea"
    timber_resource_output_name = "TimberResources"

    hazard_nickname = "Agricultural & Timber Resources"

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    try:

        # Open the mxd for getting the feature layer
        mxd = arcpy.mapping.MapDocument(mxd_path)
        df = arcpy.mapping.ListDataFrames(mxd, "")[0]
        m = "Exporting Featureclass from Template MXD"
        writeMessages(log_file_path, m, False)

        ag_fc = exportFeatureServiceLayer(mxd, df, ag_mxd_layer_name, processing_gdb, ag_resource_output_name)
        timber_fc = exportFeatureServiceLayer(mxd, df, timber_mxd_layer_name, processing_gdb, timber_resource_output_name)

        output_sr = arcpy.SpatialReference(output_sr_wkid)

        final_natural_hazard_layers = list()
        for fc in [ag_fc, timber_fc]:
            fc_name = os.path.basename(fc)
            projected_fc = os.path.join(final_gdb, fc_name)
            arcpy.Project_management(fc, projected_fc, output_sr)
            addDTField(projected_fc)
            final_natural_hazard_layer = os.path.join(naturalhazards_gdb, fc_name)
            arcpy.CopyFeatures_management(projected_fc, final_natural_hazard_layer)
            final_natural_hazard_layers.append(final_natural_hazard_layer)

        m = "\tSUCCESS\n"
        writeMessages(log_file_path, m)
        return final_natural_hazard_layers
    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None






