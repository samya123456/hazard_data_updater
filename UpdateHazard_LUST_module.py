from NaturalHazardUpdaterTool_Functions import *

def runLUST(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb):
    def formatString(s):
        if s is None:
            return ''
        else:
            if isinstance(s, basestring):
                return s.strip()
            else:
                return s
    ### These variables should not change ###
    # https://geotracker.waterboards.ca.gov/datadownload  (Cleanup Sites Data Download) --> http://geotracker.waterboards.ca.gov/data_download/GeoTrackerDownload.zip
    download_link = r"http://geotracker.waterboards.ca.gov/data_download/GeoTrackerDownload.zip"
    file_name = 'sites.txt'  # name of the file from the zipped download

    required_fields = ['GLOBAL_ID', 'BUSINESS_NAME', 'STATUS', 'STREET_NUMBER', 'STREET_NAME', 'CITY', 'STATE', 'ZIP']

    latitude_field = 'LATITUDE'
    longitude_field = 'LONGITUDE'
    address_component_fields = ['STREET_NUMBER', 'STREET_NAME', 'CITY', 'STATE', 'ZIP']
    output_address_field = 'address'



    input_sr_wkid = 4326  # WGS84
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere
    output_name = "Leaking_Underground_Storage_Tanks"
    hazard_nickname = "Leaking Underground Storage Tanks (LUST)"

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    try:
        # Get zip file
        m = "Downloading Data..."
        writeMessages(log_file_path, m, False)

        filedata = urllib2.urlopen(download_link)
        the_data = filedata.read()

        download_zip_path = os.path.join(other_data_folder, "LUST_Sites.zip")
        with open(download_zip_path, 'wb') as f:
            f.write(the_data)

        # extract the zip file
        with ZipFile(download_zip_path, "r") as zip_reader:
            zip_reader.extractall(other_data_folder)

        # get the contents
        download_folder_contents = os.listdir(other_data_folder)
        sites_txt_file = [os.path.join(other_data_folder, f) for f in download_folder_contents if f == file_name][0]

        # Create Feature class
        with codecs.open(sites_txt_file, 'r', encoding='cp1252', errors='replace') as file_obj:
            reader = file_obj.readlines()
            raw_data = [r.rstrip('\r\n').split('\t') for r in reader]

        header = [h.strip().replace(' ','_') for h in raw_data.pop(0)]

        data = [r[:len(header)] for r in raw_data]

        m = "Converting To Point Featureclass..."
        writeMessages(log_file_path, m, False)

        temp_fc, missed_records = tableToPoints(header, data, latitude_field, longitude_field, input_sr_wkid, processing_gdb, "{}_temp".format(output_name))

        if len(missed_records) > 0:
            m = "Warning, {} records could not be processed due to unknow error:\n".format(len(missed_records))
            for missed_record_i, missed_record in enumerate(missed_records):
                if missed_record_i < 20:
                    m += "\t{}\n".format(missed_record)
                else:
                    m += "\t..."
                    break
            writeMessages(log_file_path, m, False)

        # check fields
        current_fields = [f.name for f in arcpy.ListFields(temp_fc)]
        missing_fields = [f for f in required_fields if f not in current_fields]
        if len(missing_fields) > 0:
            for field in missing_fields:
                m = "Error! The  Field [{}] was not found in the input data\n".format(field)
                writeMessages(log_file_path, m, msg_type='warning')

        arcpy.AddField_management(in_table=temp_fc,
                                  field_name=output_address_field,
                                  field_type="TEXT",
                                  field_length="1000")

        cursor_fields = address_component_fields + [output_address_field]
        with arcpy.da.UpdateCursor(temp_fc, cursor_fields) as update_cursor:
            for row in update_cursor:
                try:
                    address_component_values = [formatString(row[i]) for i, field in enumerate(address_component_fields)]
                    address = " ".join(address_component_values)
                    while '  ' in address:
                        address = address.replace('  ', ' ')
                    address = address.strip().rstrip(',')

                except:
                    address = 'N/A'
                new_record = address_component_values + [address]
                update_cursor.updateRow(new_record)

        projected_fc = os.path.join(final_gdb, output_name)
        arcpy.Project_management(temp_fc, projected_fc, arcpy.SpatialReference(output_sr_wkid))
        addDTField(projected_fc)
        final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
        arcpy.CopyFeatures_management(projected_fc, final_natural_hazard_layer)

        m = "\tSUCCESS\n"
        writeMessages(log_file_path, m)
        return final_natural_hazard_layer

    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None

