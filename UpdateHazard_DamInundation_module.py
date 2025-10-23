from NaturalHazardUpdaterTool_Functions import *


def runDamInundation(workspace, chrome_driver_path, log_file_path, naturalhazards_gdb, dam_inundation_zip_file_path):
    dam_inundation_web_address = r"https://fmds.water.ca.gov/webgis/?appid=dam_prototype_v2"
    hazard_nickname = "Dam Inundation"
    dam_name_field = ['DamName', 'dam_name']
    dam_id_field = ['NID', 'CA_ID']
    state_id_field = ['StateID', 'Dam_ID']
    dam_structure_field = 'FailedStr'  # ie main dam, spillway etc

    non_required_fields = ["Scenario", "LoadingScn", "PubDate"]

    dam_zone_field = 'Zone'  # output dam zone field
    dam_dataset_field = 'Dataset'  # flags all dams as Dataset=Update, helps in finding new dams

    output_name = "Dam_Inundation"
    output_sr_wkid = 3857  # WGS_1984_Web_Mercator_Auxiliary_Sphere

    """ Functions """

    def expand_shadow_element(driver_obj, element):
        shadow_root = driver_obj.execute_script('return arguments[0].shadowRoot', element)
        return shadow_root

    def fixID(s):
        """ fixes the CA dam ID """
        parts = s.split(".")
        prefix = int(parts[0])
        suffix = int(parts[1])
        new_s = "{}-{}".format(prefix, suffix)
        return new_s

    arcpy.env.overwriteOutput = True

    today = datetime.datetime.now()
    today_string = today.strftime("%Y%m%d_%H%M")

    # Create workspaces
    processing_folder, gis_data_folder, other_data_folder, processing_gdb, final_gdb = createWorkspaces(workspace, hazard_nickname, today_string)

    # Create log file
    writeMessages(log_file_path, "### {} UPDATE ###\n".format(hazard_nickname.upper()))


    try:
        with ZipFile(dam_inundation_zip_file_path, "r") as zip_reader:
            zip_reader.extractall(gis_data_folder)

        arcpy.env.workspace = gis_data_folder
        arcpy.env.overwriteOutput = True
        fcs = arcpy.ListFeatureClasses()
        if len(fcs) != 1:
            m = "Error, Unable to located the Unzipped Features in {}\nExpected a single shapefile".format(gis_data_folder)
            writeMessages(log_file_path, m, msg_type='warning')
            return None
            driver.quit()  # close chrome
        else:
            dam_inundation_shp = fcs[0]

            dam_inundation_fc = os.path.join(final_gdb, output_name)
            out_sr = arcpy.SpatialReference(output_sr_wkid)
            out_sr_name = " ".join(out_sr.name.split("_"))

            m = "Projecting to {}".format(out_sr_name)
            writeMessages(log_file_path, m, False)
            arcpy.Project_management(dam_inundation_shp, dam_inundation_fc, out_sr)

            # correct the fields:
            state_id_field_old = state_id_field[0]
            state_id_field_new = state_id_field[1]
            dam_name_field_old = dam_name_field[0]
            dam_name_field_new = dam_name_field[1]
            dam_id_field_old = dam_id_field[0]
            dam_id_field_new = dam_id_field[1]

            m = "Adding Required Fields...\n"
            writeMessages(log_file_path, m, False)
            arcpy.AddField_management(dam_inundation_fc, state_id_field_new, "TEXT", field_length=10)
            arcpy.AddField_management(dam_inundation_fc,dam_name_field_new, "TEXT", field_length=255)
            arcpy.AddField_management(dam_inundation_fc, dam_id_field_new, "TEXT", field_length=10)
            arcpy.AddField_management(dam_inundation_fc, dam_zone_field, "TEXT", field_length=3)
            arcpy.AddField_management(dam_inundation_fc, dam_dataset_field, "TEXT", field_length=50)


            cursor_fields = [state_id_field_old,
                             state_id_field_new,
                             dam_name_field_old,
                             dam_name_field_new,
                             dam_structure_field,
                             dam_id_field_old,
                             dam_id_field_new,
                             dam_zone_field,
                             dam_dataset_field
            ]

            with arcpy.da.UpdateCursor(dam_inundation_fc, cursor_fields) as update_cursor:
                for row in update_cursor:
                    # correct_dam_id
                    old_state_id = row[0]
                    new_state_id = fixID(old_state_id)
                    dam_prefix = row[2]
                    dam_suffix = row[4]
                    new_dam_name = "{} - {}".format(dam_prefix, dam_suffix)
                    old_dam_id = row[5]
                    new_dam_id = old_dam_id
                    dam_zone = 'IN'
                    dam_dataset = 'Update'
                    updated_record = [old_state_id, new_state_id, dam_prefix, new_dam_name, dam_suffix, old_dam_id, new_dam_id, dam_zone, dam_dataset]
                    update_cursor.updateRow(updated_record)

            drop_fields = [state_id_field_old, dam_name_field_old, dam_id_field_old, dam_structure_field] + non_required_fields
            arcpy.DeleteField_management(dam_inundation_fc, drop_fields)

            addDTField(dam_inundation_fc)

            final_natural_hazard_layer = os.path.join(naturalhazards_gdb, output_name)
            arcpy.CopyFeatures_management(dam_inundation_fc, final_natural_hazard_layer)

            m = "\tSUCCESS\n"
            writeMessages(log_file_path, m)
            return final_natural_hazard_layer


    except:
        m = "\t!!! ERROR !!!\n\tSomething Went Wrong: {}.\nLine number: {}".format(e.args[0], traceback.extract_stack()[-1][1])
        writeMessages(log_file_path, m, msg_type='warning')
        return None





