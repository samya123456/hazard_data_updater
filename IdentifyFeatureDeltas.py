import os
import arcpy
import requests
import datetime
from NaturalHazardUpdaterTool_Functions import writeMessages
""" INPUTS """

"""
new_layer = arcpy.GetParameterAsText(0)
old_layer = arcpy.GetParameterAsText(1)
report_field = arcpy.GetParameterAsText(2)  # field where a change in data is meaningful
query = arcpy.GetParameter(3)  # query to subset data (applies to both layers). String or None
distance = arcpy.GetParameter(4)  # search distance for hazard. Miles

workspace = arcpy.GetParameterAsText(5)
"""
new_layer = r"C:\workspace\20210414_Updates\data.gdb\CA_Flood"
old_layer = r"C:\workspace\20210414_Updates\data.gdb\CA_Flood_OLD"
report_field = "FLD_ZONE"  # field where a change in data is meaningful
query = "SFHA_TF = 'T'"  # query to subset data (applies to both layers). String or None
distance = 0  # search distance for hazard. Miles

workspace = r"C:\workspace\__HazardUpdates"

""" MAIN """

today = datetime.datetime.now()
today_string = today.strftime("%Y%m%d_%H%M")

hazard_name = os.path.basename(new_layer)
workspace_name = "HazardTestCases_{}_{}".format(today_string, hazard_name)
workspace_path = os.path.join(workspace, workspace_name)
os.makedirs(workspace_path)

processing_gdb_name = "{}.gdb".format(hazard_name)
processing_gdb = os.path.join(workspace_path, processing_gdb_name)
arcpy.CreateFileGDB_management(workspace_path, processing_gdb_name)

arcpy.env.workspace = processing_gdb
arcpy.env.overwriteOutput = True

log_file_path = os.path.join(workspace_path, workspace_name)
message = "Identify [{}] Hazard Changes/Test Cases\nDate: {}\n".format(hazard_name, today_string)
writeMessages(log_file_path, message)

# subset each feature
m = "\nMaking Feature Layer...\n"
writeMessages(log_file_path, m)

new_fl = "new_fl"
old_fl = "old_fl"
arcpy.MakeFeatureLayer_management(new_layer, new_fl, query)
arcpy.MakeFeatureLayer_management(old_layer, old_fl, query)

# buffer the feature layers if a distance greater than 0 is specified
if distance > 0:
    m = "\nBuffering Features ({} Miles)...\n".format(distance)
    writeMessages(log_file_path, m)
    new_fl = arcpy.Buffer_analysis(new_fl, "new_fl_buffer", "{} Miles".format(distance))
    old_fl = arcpy.Buffer_analysis(old_fl, "new_fl_buffer", "{} Miles".format(distance))

# perform union
m = "\nPerforming Union...\n"
writeMessages(log_file_path, m)

union = arcpy.Union_analysis([new_fl, old_fl], "union", "ALL", "", "GAPS")

drop_fields = [f.name for f in arcpy.ListFields(union) if not f.required and f.name not in [report_field, "{}_1".format(report_field)]]

arcpy.DeleteField_management(union, drop_fields)

if report_field in ['', None]:
    feature_deltas = arcpy.Copy_management(union, "Feature_Deltas")
else:
    feature_deltas = arcpy.Select_analysis(union, "Feature_Deltas", "{} <> {}_1".format(report_field, report_field))

arcpy.Delete_management(new_fl)
arcpy.Delete_management(old_fl)
del (new_fl, old_fl)

m = "Feature Deltas Created Here:\n\t{}\n\n".format(feature_deltas)
writeMessages(log_file_path, m)


