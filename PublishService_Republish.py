### Work in Progress, non functional. automates the republishing of map services that are required after data updates

import arcpy
import os

environment = "TEST"  # TEST or PROD
service_config = {
    "AHS Residential" : {
        'test_map_document': r"C:\TestMXDs\T_AHSHomeAware.mxd",
        'prod_map_document': r"C:\ProdMXDs\AHSHomeAware.mxd",
        'test_service_name': 'T_AHSHomeAware',
        'prod_service_name': 'AHSHomeAware',
        'folder_name': "AHSHomeAware",
        'summary': 'AHS Service',
        'tags': 'AHS, NHD'
    }
}

for service in service_config

# static
staging_folder = r"C:/Users/Administrator/AppData/Local/ESRI/Desktop10.2/Staging/AHS Services"
connection_file = r"C:/Users/Administrator/AppData/Roaming/ESRI/Desktop10.2/ArcCatalog/AHS Services.ags"

""" MAIN """
service_definition_draft = os.path.join(staging_folder, service_name + ".sddraft")
service_definition = os.path.join(staging_folder, service_name + ".sd")

# Create SD Draft
arcpy.mapping.CreateMapSDDraft(map_document, service_definition_draft, service_name, "ARCGIS_SERVER", connection_file, False, folder_name, summary, tags)

# Stage Service
arcpy.StageService_server(service_definition_draft, service_definition)

# Upload service
arcpy.UploadServiceDefinition_server(service_definition, connection_file, in_service_name="#",in_cluster="#",in_folder_type="FROM_SERVICE_DEFINITION", in_folder="#",in_startupType="STARTED",in_override="USE_DEFINITION", in_my_contents="NO_SHARE_ONLINE",in_public="PRIVATE", in_organization="NO_SHARE_ORGANIZATION",in_groups="#")


arcpy.AddMessage("Publishing T_DDS_HazardsMar2019...")
arcpy.StageService_server(in_service_definition_draft="C:/Users/Administrator/AppData/Local/ESRI/Desktop10.2/Staging/AHS Services/T_DDS_HazardsMar2019.sddraft",out_service_definition="C:/Users/Administrator/AppData/Local/ESRI/Desktop10.2/Staging/AHS Services/T_DDS_HazardsMar2019.sd")
arcpy.UploadServiceDefinition_server(in_sd_file="C:/Users/Administrator/AppData/Local/ESRI/Desktop10.2/Staging/AHS Services/T_DDS_HazardsMar2019.sd",in_server="C:/Users/Administrator/AppData/Roaming/ESRI/Desktop10.2/ArcCatalog/AHS Services.ags",in_service_name="#",in_cluster="#",in_folder_type="FROM_SERVICE_DEFINITION",in_folder="#",in_startupType="STARTED",in_override="USE_DEFINITION",in_my_contents="NO_SHARE_ONLINE",in_public="PRIVATE",in_organization="NO_SHARE_ORGANIZATION",in_groups="#")

arcpy.AddMessage("Publishing T_ComNatHaz232_Feb19...")
arcpy.StageService_server(in_service_definition_draft="C:/Users/Administrator/AppData/Local/ESRI/Desktop10.2/Staging/AHS Services/T_ComNatHaz232_Feb19.sddraft",out_service_definition="C:/Users/Administrator/AppData/Local/ESRI/Desktop10.2/Staging/AHS Services/T_ComNatHaz232_Feb19.sd")
arcpy.UploadServiceDefinition_server(in_sd_file="C:/Users/Administrator/AppData/Local/ESRI/Desktop10.2/Staging/AHS Services/T_ComNatHaz232_Feb19.sd",in_server="C:/Users/Administrator/AppData/Roaming/ESRI/Desktop10.2/ArcCatalog/AHS Services.ags",in_service_name="#",in_cluster="#",in_folder_type="FROM_SERVICE_DEFINITION",in_folder="#",in_startupType="STARTED",in_override="USE_DEFINITION",in_my_contents="NO_SHARE_ONLINE",in_public="PRIVATE",in_organization="NO_SHARE_ORGANIZATION",in_groups="#")

arcpy.AddMessage("Publishing T_Hazards032019...")
arcpy.StageService_server(in_service_definition_draft="C:/Users/Administrator/AppData/Local/ESRI/Desktop10.2/Staging/AHS Services/T_Hazards032019.sddraft",out_service_definition="C:/Users/Administrator/AppData/Local/ESRI/Desktop10.2/Staging/AHS Services/T_Hazards032019.sd")
arcpy.UploadServiceDefinition_server(in_sd_file="C:/Users/Administrator/AppData/Local/ESRI/Desktop10.2/Staging/AHS Services/T_Hazards032019.sd",in_server="C:/Users/Administrator/AppData/Roaming/ESRI/Desktop10.2/ArcCatalog/AHS Services.ags",in_service_name="#",in_cluster="#",in_folder_type="FROM_SERVICE_DEFINITION",in_folder="#",in_startupType="STARTED",in_override="USE_DEFINITION",in_my_contents="NO_SHARE_ONLINE",in_public="PRIVATE",in_organization="NO_SHARE_ORGANIZATION",in_groups="#")
