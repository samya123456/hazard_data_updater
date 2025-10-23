""" Updates the NEW TRI dataset from California EPA """

from NaturalHazardUpdaterTool_Functions import *


def runTRI(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    def copyFC(layer_name, message):
        """
        copies layer via wildcard search
        :param layer_name:
        :param message:
        :return:
        """
        input_name = layer_name[0]
        if len(arcpy.ListFeatureClasses(input_name)) == 1:
            temp_fc = os.path.join(processing_gdb, layer_name[1])
            arcpy.CopyFeatures_management(input_name, temp_fc)
        else:
            message += "ERROR, UNABLE TO FIND [{}] in GDB\n".format(input_name)
        return temp_fc, message

    def copyFieldsOver(fc, field_config):
        field_types = {"String": "TEXT",
                       "Double": "DOUBLE",
                       "Integer": "LONG",
                       "Date": "DATE"}

        for field in field_config:
            input_field = field[0]
            output_field = field[1]

            if input_field in [f.name for f in arcpy.ListFields(fc)]:
                if input_field == output_field:
                    pass  # no need to do anything, just checks that the field exists
                else:
                    field_type = field_types[[f.type for f in arcpy.ListFields(fc, input_field)][0]]

                    if field_type == 'TEXT':
                        field_len = [f.length for f in arcpy.ListFields(fc, input_field)][0]
                    else:
                        field_len = None

                    arcpy.AddField_management(fc, output_field, field_type, field_length=field_len)

                    with arcpy.da.UpdateCursor(fc, [input_field, output_field]) as cursor:
                        for row in cursor:
                            update_record = (row[0], row[0])
                            cursor.updateRow(update_record)
            else:
                print "ERROR, FIELD [{}] DOES NOT EXIST".format(input_field)

    ### These variables should not change ###
    download_link = r"https://edg.epa.gov/data/public/OEI/FRS/FRS_Interests_Download.zip"
    hazard_nickname = "Toxic Release Inventory"

    # [original_name, NHD_hazard_name]
    tri_layer_name = ["TRI", "Toxics_Release_Inventory"]

    tri_fields = [['facility_n', 'FACILITY'], ['url', 'Report_URL']]
    tri_dummy_field = 'CHEMICAL'

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    try:
        # Download the file
        m = "Downloading latest EPA Hazards Geodatabase..."
        writeMessages(log_file_path, m, False)

        filedata = urllib2.urlopen(download_link)
        the_data = filedata.read()

        m = "Done. Creating Zip File File..."
        writeMessages(log_file_path, m, False)

        download_zip_path = os.path.join(other_data_folder, "epa_hazard_gdb.zip")
        with open(download_zip_path, 'wb') as f:
            f.write(the_data)

        m = "Done. Unzipping..."
        writeMessages(log_file_path, m, False)

        # extract the zip file
        with ZipFile(download_zip_path, "r") as zip_reader:
            zip_reader.extractall(other_data_folder)

        m = "Done."
        writeMessages(log_file_path, m, False)

        # get the extracted zip folder
        download_folder = os.listdir(other_data_folder)[0]
        download_folder_path = os.path.join(other_data_folder, download_folder)

        # get the gdb
        epa_gdb_path = None
        for file in os.listdir(other_data_folder):
            if file.endswith(".gdb"):
                epa_gdb_path = os.path.join(other_data_folder, file)

        if epa_gdb_path is None:
            m = "ERROR, UNABLE TO FIND GEODATABASE IN ZIP FOLDER:\n\t{}".format(download_folder_path)
            writeMessages(log_file_path, m, msg_type='warning')
        else:
            # find each layer of interest and copy to the processing workspace
            arcpy.env.workspace = epa_gdb_path
            copy_message = str()

            tri_temp_fc, copy_message = copyFC(tri_layer_name, copy_message)
            sems_temp_fc, copy_message = copyFC(sems_layer_name, copy_message)
            npl_temp_fc, copy_message = copyFC(npl_layer_name, copy_message)

            # normalize the fields
            m ="Normalizing Fields..."
            writeMessages(log_file_path, m, False)
            # normalize the fields
            m = "\t{} ...".format(os.path.basename(tri_temp_fc))
            writeMessages(log_file_path, m, False)
            copyFieldsOver(tri_temp_fc, tri_fields)

            #Add unknown tri chemical name
            arcpy.AddField_management(tri_temp_fc, tri_dummy_field, "TEXT")
            with arcpy.da.UpdateCursor(tri_temp_fc, [tri_dummy_field]) as update_cursor:
                for row in update_cursor:
                    record = ["Not Available"]
                    update_cursor.updateRow(record)

            # create web address link for the TRI featureclass
            arcpy.AddField_management(tri_temp_fc, tri_webaddress_field['name'], tri_webaddress_field['type'], field_length=tri_webaddress_field['length'])
            arcpy.CalculateField_management(tri_temp_fc, tri_webaddress_field['name'], "'{}' + str(!{}!)".format(tri_webaddress_field['base_url'], tri_webaddress_field['id_field']), "PYTHON_9.3")

            m = "\t{} ...".format(os.path.basename(sems_temp_fc))
            writeMessages(log_file_path, m, False)
            copyFieldsOver(sems_temp_fc, sems_fields)

            m = "\t{} ...".format(os.path.basename(npl_temp_fc))
            writeMessages(log_file_path, m, False)
            copyFieldsOver(npl_temp_fc, npl_fields)
            final_fcs = list()

            if len(copy_message) > 0:
                m = "ERROR: \n{}".format(copy_message)
                writeMessages(log_file_path, m, msg_type='warning')
            else:
                # proceed to process data, all data is available...

                # Process each layer
                m = "Subsetting and Projecting..."
                writeMessages(log_file_path, m, False)
                for fc in [tri_temp_fc, sems_temp_fc, npl_temp_fc]:
                    fc_name = os.path.basename(fc)
                    m = "\t{}...".format(fc_name)
                    writeMessages(log_file_path, m, False)
                    query = "STATE_CODE <> 'CA'"
                    feature_layer = "feature_layer"
                    arcpy.MakeFeatureLayer_management(fc, feature_layer, query)  # delete records outside california
                    arcpy.DeleteFeatures_management(feature_layer)
                    arcpy.Delete_management(feature_layer)
                    del feature_layer

                    final_fc_path = os.path.join(naturalhazards_gdb, fc_name)
                    final_fc = arcpy.Project_management(fc, final_fc_path, out_sr)
                    addDTField(final_fc)

                    final_fcs.append(final_fc)

                m = "\tSUCCESS\n"
                writeMessages(log_file_path, m)
                return final_fcs

    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None
