import arcpy
from NaturalHazardUpdaterTool_Functions import addDTField

input_fc = arcpy.GetParameter(0)
field_name = arcpy.GetParameter(1)

addDTField(input_fc, field_name)

