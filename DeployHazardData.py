import os
import arcpy

#from arcgis.gis import GIS
#import arcgis.gis.admin

""" INPUTS """
# gdb containing new hazard updates
updates_workspace = arcpy.GetParameterAsText(0)

# contains TEST/PROD Data
database_name = arcpy.GetParameterAsText(1)

# ArcGIS Services
services = {
    "TEST" : [],
    "PROD" : []
}


""" MAIN """

if database_name == "TEST":
    database = r'C:\workspace\20220525_HazardUpdaterTool\NEW_DATA\hazardsAll_TEST.gdb'
else:
    database = r'C:\workspace\20220525_HazardUpdaterTool\NEW_DATA\hazardsAll_Prod.gdb'


# check that all updates exists in database
arcpy.env.workspace = updates_workspace
update_fcs = arcpy.ListFeatureClasses()

arcpy.env.workspace = database
database_fcs = arcpy.ListFeatureClasses()

run_updates = True  # if set to False the update process will not begin

missing_data = list()

for fc in update_fcs:
    if fc not in database_fcs:
        run_updates = False
        missing_data.append(fc)

if len(missing_data) > 0:
    missing_data_string = "\n\t".join(d for d in missing_data)
    m = "\nThe following Update Featureclasses where not found in the {} Database:\n\t{}".format(database_name, missing_data_string)
    arcpy.AddError(m)

### Pause Services HERE



###

if run_updates == True:
    # Delete old data
    arcpy.AddMessage('\nDeleting Current {} Data...'.format(database_name))
    for fc in update_fcs:
        arcpy.AddMessage("\t{}".format(fc))
        fc_path = os.path.join(database, fc)
        arcpy.Delete_management(fc_path)

    arcpy.AddMessage('\nCopying New Data to {}...'.format(database_name))
    for fc in update_fcs:
        arcpy.AddMessage("\t{}".format(fc))
        in_data = os.path.join(updates_workspace, fc)
        out_data = os.path.join(database, fc)
        arcpy.Copy_management(in_data, out_data)

    # Republish Services