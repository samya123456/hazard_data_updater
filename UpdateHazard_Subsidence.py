""" To update Susidence, The tiff must first be extracted manually.
- The image service must be added to ArcGIS Pro
('https://gis.water.ca.gov/arcgisimg/rest/services/SAR/Vertical_Displacement_TRE_ALTAMIRA_Total_Since_20150613_20220701/ImageServer')
- Set the Raster processing Method to None (single band symbolization)
- Export Raster
    NoData=-999
    cell size=500
    coordsys=CA Teale Albers (3310)
    type=32 bit float

and the processing template (properties) are set to 'None' export to NAD 1983 California (Teale) Albers (Meters) (WKID 3310) and set pixel size to 500 meters"""

from NaturalHazardUpdaterTool_Functions import *

def runSubsidence(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb, input_tif):
    ### These variables should not change ###
    # get the map document that contains links to the feature services
    script_path = os.path.dirname(os.path.abspath(__file__))
    mxd_path = os.path.join(script_path, r"templates\FeatureService_Layers.mxd")
    mxd_layer_name = "Subsidence_Vertical_Displacement_TRE_ALTAMIRA_Total"  # the service layer name
    output_name = "SubsidenceAreas"  # the name of the dataset in out database
    hazard_nickname = "Subsidence"

    # Used for setting NA/no data features
    ca_polygon = r'C:\workspace\__BaseData\Corrected_Jurisdictions.gdb\CA_Jurisdictions'
    no_data_value = -999

    input_sr_wkid = 3310  # NAD 1983 California (Teale) Albers (Meters)
    output_sr_wkid = 3857  # WGS 1984 Web Mercator (auxiliary sphere)

    root_services_url = r'https://gis.water.ca.gov/arcgisimg/rest/services/SAR'

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace,
                                                                                                        hazard_nickname,
                                                                                                        today_string)

    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))

    try:
        """
        # I have not found a method to export the imageServer layer, here is the code to locate the newest layer
        
        # Get the most recent subsidence layer
        # get available layers from service folder
        response = urllib2.urlopen(root_services_url + '?f=pjson')
        json_string = response.read()
        data = json.loads(json_string)

        layers = [layer['name'] for layer in data["services"] if "Total_Since" in layer['name']]

        layer_prefix = 'Vertical_Displacement_TRE_ALTAMIRA_Total_Since_20150613_'

        dates = [int(layer.split('_')[-1]) for layer in layers if layer.split('_')[-1].isnumeric()]
        last_date = max(dates)

        latest_layer_url = "{}/{}{}/ImageServer".format(root_services_url,layer_prefix,last_date)

        m = "Latest Image Service:\n{}\n".format(latest_layer_url)
        writeMessages(log_file_path, m, False)



        # Open the mxd for getting the feature layer
        mxd = arcpy.mapping.MapDocument(mxd_path)
        df = arcpy.mapping.ListDataFrames(mxd, "")[0]
        m = "Exporting Featureclass from Template MXD"
        writeMessages(log_file_path, m, False)

        layer_obj = arcpy.mapping.ListLayers(mxd, mxd_layer_name, df)[0]

        current_datasource = layer_obj.dataSource
        layer_workspace = os.path.dirname(current_datasource)
        layer_dataset_name = os.path.basename(current_datasource)
        layer_full_path = os.path.join(layer_workspace, layer_dataset_name)
        
        """

        # Get input Raster properties
        input_raster = arcpy.Raster(input_tif)
        lowerLeft = arcpy.Point(input_raster.extent.XMin,input_raster.extent.YMin)
        cellSize = input_raster.meanCellWidth

        # Convert Raster to numpy array
        np_array = arcpy.RasterToNumPyArray(input_raster, nodata_to_value=no_data_value)

        # multiply by 100
        new_array = np_array * 100

        # convert to int
        int_array = new_array.astype(int)

        #Convert Array to raster (keep the origin and cellsize the same as the input)
        new_raster = arcpy.NumPyArrayToRaster(int_array, lowerLeft, cellSize, value_to_nodata=no_data_value*100)

        new_raster_path = os.path.join(processing_gdb, "subsidence_temp_raster")
        new_raster.save(new_raster_path)

        subsidence_fc = os.path.join(processing_gdb, output_name)

        arcpy.RasterToPolygon_conversion(new_raster_path, subsidence_fc, simplify='NO_SIMPLIFY')

        arcpy.DefineProjection_management(subsidence_fc, arcpy.SpatialReference(input_sr_wkid))

        numeric_field = "VerticalDisplacement"
        desc_field = "VerticalDisplacement_Desc"
        zone_field = "Zone"

        arcpy.AddField_management(subsidence_fc, numeric_field, "DOUBLE")
        arcpy.AddField_management(subsidence_fc, desc_field, "TEXT", field_length=50)
        arcpy.AddField_management(subsidence_fc, zone_field, "TEXT", field_length=10)

        cursor_fields = ["gridcode", numeric_field, desc_field, zone_field]

        with arcpy.da.UpdateCursor(subsidence_fc, cursor_fields) as update_cursor:
            for row in update_cursor:
                raw_value = row[0]
                numeric_value = float(raw_value) / 100.0
                displacement_text = "{} Feet".format(str(round(numeric_value, 2)))
                zone = 'IN'
                updated_record = [raw_value, numeric_value, displacement_text, zone]
                update_cursor.updateRow(updated_record)

        #create No data feature with subsidence areas removed
        ca_polygon_erase = os.path.join(processing_gdb, 'ca_erase')
        arcpy.Erase_analysis(ca_polygon, subsidence_fc, ca_polygon_erase)

        arcpy.AddField_management(ca_polygon_erase, zone_field, "TEXT", field_length=10)
        arcpy.CalculateField_management(ca_polygon_erase, zone_field, "'NA'", "PYTHON_9.3")

        ca_polygon_erase_sp = arcpy.MultipartToSinglepart_management(ca_polygon_erase, "in_memory/ca_erase_singlepart")

        arcpy.Append_management(ca_polygon_erase_sp, subsidence_fc, "NO_TEST")

        addDTField(subsidence_fc)

        arcpy.Delete_management(new_raster)
        del np_array, new_array, int_array, new_raster

        projected_fc_path = os.path.join(processing_gdb, 'subsidence_project')
        projected_fc = arcpy.Project_management(subsidence_fc, projected_fc_path, output_sr_wkid)

        final_natural_hazard_layer_path = os.path.join(naturalhazards_gdb, output_name)
        final_natural_hazard_layer = arcpy.Copy_management(projected_fc, final_natural_hazard_layer_path)

        m = "\tSUCCESS\n"
        writeMessages(log_file_path, m)

        return final_natural_hazard_layer

    except:
        m = "\n!!! ERROR !!!\nSomething Went Wrong"
        writeMessages(log_file_path, m, msg_type='warning')
        return None


