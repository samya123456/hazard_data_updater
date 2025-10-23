from NaturalHazardUpdaterTool_Functions import *

def runStatePriorityList(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb, spl_excel_file):
    # https://www.envirostor.dtsc.ca.gov/public/search?cmd=search&site_type=&corrective_action=True&reporttitle=Facilities+With+Corrective+Actions ---> "Export to Excel"
    """
    GO TO:
    https://www.envirostor.dtsc.ca.gov/public/search?cmd=search&site_type=&corrective_action=True&reporttitle=Facilities+With+Corrective+Actions

    Click "EXPORT TO EXCEL"
    """

    input_sr_wkid = 4326  # WGS84
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "State_Priority_List"
    hazard_nickname = "State Priority List"

    lat_field, long_field = "LATITUDE",	"LONGITUDE"

    # Used to convert the input fields to the current version of the table. If the fields are the same, not mapping is performed
    field_mappings = {   # Required Fields = Project_Name, Address, Site_Type, Status
        "SITE / FACILITY NAME": "Project_Name",
        "ADDRESS DESCRIPTION": "Address",
        "PROGRAM TYPE": "Site_Type",
        "STATUS": "Status"
    }

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))


    try:


        # create csv
        table_csv_name = "SPL_Table"
        table_csv = os.path.join(other_data_folder, table_csv_name + ".csv")

        m = "Converted Excel File to CSV..."
        writeMessages(log_file_path, m, False)

        # Read in the Excel Data (it's actually Tab delineated with the wrong extension)
        with open(spl_excel_file) as excel_obj:
            data = csv.reader(excel_obj)
            spl_data = [d[0].split('\t') for d in data]
            header = spl_data[0]
            # replace the header with the expected fields
            for i, field_name in enumerate(header):
                if field_name in field_mappings:
                    header[i] = field_mappings[field_name]
            spl_data[0] = header


            #write each row to a csv so it can be converted
            with open(table_csv, 'wb') as f:   # open('a_file.csv', 'w', newline="") for python 3
                c = csv.writer(f)
                for row in spl_data:
                    row_vals_encoded = [unicode(r).encode("utf-8") for r in row]
                    c.writerow(row_vals_encoded)

        # convert to FGDB table
        spl_temp_table = os.path.join(processing_gdb, table_csv_name)
        arcpy.TableToTable_conversion(table_csv, processing_gdb, table_csv_name)

        # convert to features
        m = "Creating XY Features..."
        writeMessages(log_file_path, m, False)

        input_sr = arcpy.SpatialReference(input_sr_wkid)  # WGS84
        output_sr = arcpy.SpatialReference(output_sr_wkid)  # WGS_1984_Web_Mercator_Auxiliary_Sphere

        layer_view = "layer_view"
        arcpy.MakeXYEventLayer_management(spl_temp_table, long_field, lat_field, layer_view, input_sr)
        spl_feature_name = "{}_wkid{}".format(output_name, input_sr_wkid)
        spl_features = os.path.join(processing_gdb, spl_feature_name)
        arcpy.CopyFeatures_management(layer_view, spl_features)

        # project data
        m = "Projecting Data..."
        writeMessages(log_file_path, m, False)

        final_output = os.path.join(final_gdb, output_name)
        arcpy.Project_management(spl_features, final_output, output_sr)

        #add the last_update field
        addDTField(final_output)

        final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
        arcpy.CopyFeatures_management(final_output, final_natural_hazard_layer)

        m = "\tSUCCESS\n"
        writeMessages(log_file_path, m)
        return final_natural_hazard_layer
    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None
