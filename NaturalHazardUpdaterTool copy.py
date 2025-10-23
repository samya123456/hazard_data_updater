from NaturalHazardUpdaterTool_Functions import *
from UpdateHazard_SpecialFloodHazard_module import runFlood
from UpdateHazard_DamInundation_module import runDamInundation
from UpdateHazard_CGSLayers_module import runCGS
from UpdateHazard_RightToFarm_module import runFarmland
from UpdateHazard_SolidWasteFac_module import runSolidWasteFacilities
from UpdateHazard_EPALayers_module import runEPALayers
from UpdateHazard_MiningOperations_module import runMiningOperations
from UpdateHazard_StatePriorityList_module import runStatePriorityList
from UpdateHazard_LUST_module import runLUST
from UpdateHazard_UST_module import runUST
from UpdateHazard_FUDS_module import runFUDs
from UpdateHazard_GeothermalWells_module import runGeothermalWells
from UpdateHazard_CAWells_module import runAllWells
from UpdateHazard_ElectricTransmissionLines import runElectricTransmissionLines
from UpdateHazard_Railroads import runRailroads
from UpdateHazard_AgTimberResources import runAgTimberResources
from UpdateHazard_CriticalHabitat import runCriticalHabitat
from UpdateHazard_TsunamiInundation import runTsunamiInundaiton
from UpdateHazard_VCP_module import runVCPHazard
from UpdateHazard_ERNS_module import runERNSHazard
from UpdateHazard_ClandestineLabs_module import runClandestineLabs
from UpdateHazard_CoastalErosion_module import runCoastalBluffsErosion
from UpdateHazard_Subsidence import runSubsidence
from UpdateHazard_SRA import runSRA
from UpdateAncillaryData_CAJurisdictions_module import runCAJurisdictions
from UpdateAncillaryData_CAFireDistricts import runCAFireDistricts

update_hazards = list()
ancillary_data_updates = list()

### Natural Hazards ###
run_flood = 1
# https://msc.fema.gov/portal/advanceSearch#searchresultsanchor
flood_zip = r"C:\Users\elowe\Downloads\NFHL_06_20241112.zip"
run_sra = 0
run_dam_inundation = 0
# https://fmds.water.ca.gov/webgis/?appid=dam_prototype_v2
dam_inundation_zip = r"C:\Users\elowe\Downloads\Approved_InundationBoundaries.zip"
run_CGS_hazards = 1

### Supplimental Hazards ###
run_farmland = 0
run_mining_operations = 0
run_electric_transmission_lines = 0
run_criticalhabitat = 1
criticalhabitat_zip = r"C:\Users\elowe\Downloads\gis_com(1).zip"  # https://apps.wildlife.ca.gov/cnddb-subscriptions/downloads
forestservice_zip = r"C:\Users\elowe\Downloads\crithab_all_layers(1).zip"  # https://ecos.fws.gov/ecp/report/critical-habitat --> "A zip file containing two shapefiles, one for lines, one for polygons, which aggregate all critical habitat shapes for all species"
run_tsunami_inundation = 0  # modify code to create seperate featureclass for adding features
supplimental_flood_fc = r'C:\workspace\ARE-10103_HazardUpdates\SuppFlood_20221208.gdb\Supplemental_Flood_Hazards'
run_coastalerosion = 0
run_fuds = 0
run_subsidence = 0
subsidence_tif = r'C:\workspace\__HazardUpdates\ARE-12797_Subsidence\Subsidence_20150613_20240701_wNoData.tif'
run_clandestine = 0  # decommmisioned
run_railroads = 0  # decommmisioned
run_agtimber_resources = 0  # decommmisioned

### Environmental Hazards ###
run_solid_waste = 1
run_epa_hazards = 1  # TRI, SEMS, NPL
run_state_priority_list = 1  # must provide [spl_sites] parameter below
# https://www.envirostor.dtsc.ca.gov/public/search?cmd=search&site_type=&corrective_action=True&reporttitle=Facilities+With+Corrective+Actions
spl_sites = r"C:\Users\elowe\Downloads\export(2).xls"
run_lust = 1
run_allwells = 1
run_ust = 0  # decommmisioned
run_geothermalwells = 0  # decommmisioned
run_vcp = 0  # decommmisioned
run_erns = 0  # decommmisioned

### Ancillary Data ###
run_jurisdictions = 0
run_firedistricts = 0

### workspace ###
workspace_dir = r'C:\workspace\__HazardUpdates'
current_jurisdictions_fc_path = r"C:\workspace\__BaseData\Corrected_Jurisdictions.gdb\CA_Jurisdictions"

ticket = 'ARE-12872'

chrome_driver_path = r"C:\Program Files (x86)\Google\Chrome\chromedriver.exe"

""" MAIN """

today = datetime.datetime.now()
today_string = today.strftime("%Y%m%d_%H%M")

# Contains the newly updated Data
if ticket.strip() != '':
    ticket = "_{}".format(ticket.strip())

workspace = os.path.join(workspace_dir, "Natural_Hazard_Updates_{}{}".format(today_string, ticket))
os.makedirs(workspace)

log_file_path = os.path.join(workspace, "NaturalHazardUpdate_{}_log.txt".format(today_string))
message = "Update Data Log File\nDate: {}\n\n".format(today_string)
writeMessages(log_file_path, message, False)

if run_flood: update_hazards.append("\t- Special Flood Hazard\n")
if run_sra: update_hazards.append("\t- State Responsibility Area (CalFire)\n")
if run_dam_inundation: update_hazards.append("\t- Dam Inundation\n")
if run_CGS_hazards: update_hazards.append("\t- Alquist-Priolo Fault Rupture\n\t- California Geological Survey Landslide Zone\n\t- California Geological Survey Liquefaction Zone\n")
if run_farmland: update_hazards.append("\t- FMMP Farmland\n")
if run_solid_waste: update_hazards.append("\t- Solid Waste Facilities (SWIS)\n")
if run_epa_hazards: update_hazards.append("\t- NPL\n\t- SEMS (CERCLIS)\n\t- Toxic Release Inventory\n")
if run_mining_operations: update_hazards.append("\t- Mining Operations\n")
if run_state_priority_list: update_hazards.append("\t- State Priority List\n")
if run_lust: update_hazards.append("\t- Leaking Underground Storage Tanks\n")
if run_ust: update_hazards.append("\t- Underground Storage Tanks\n")
if run_fuds: update_hazards.append("\t- Formerly Used Defense Sites\n")
if run_geothermalwells: update_hazards.append("\t- Geothermal Wells\n")
if run_allwells: update_hazards.append("\t- Gas/Oil/Geothermal\n")
if run_electric_transmission_lines: update_hazards.append("\t- Major Electric Transmission Lines\n")
if run_railroads: update_hazards.append("\t- Railroads\n")
if run_agtimber_resources: update_hazards.append("\t- Agricultural Resource Areas\n\t- Timber Resource Areas\n")
if run_criticalhabitat: update_hazards.append("\t- Critical Habitat\n")
if run_tsunami_inundation: update_hazards.append("\t- Supplemental Flood (Tsunami Inundation)\n")
if run_vcp: update_hazards.append("\t- Voluntary Cleanup Program\n")
if run_erns: update_hazards.append("\t- Emergency Response Notification System\n")
if run_clandestine: update_hazards.append("\t- Clandestine Drug Laboratories\n")
if run_coastalerosion: update_hazards.append("\t- Coastal Erosion (Bluffs & Dunes)\n")
if run_subsidence: update_hazards.append("\t- Subsidence\n")
if run_jurisdictions: ancillary_data_updates.append("\t- City/County Jurisdictions")
if run_firedistricts: ancillary_data_updates.append("\t- CalFire Districts")



if any(update_hazards):
    updates_gdb_name = "Natural_Hazard_Updates_{}{}.gdb".format(today_string.split('_')[0], ticket)
    updates_gdb = os.path.join(workspace, updates_gdb_name)
    arcpy.CreateFileGDB_management(workspace, updates_gdb_name)
    hazard_params = [workspace, chrome_driver_path, log_file_path, updates_gdb]

if any(ancillary_data_updates):
    ancillary_gdb_name = "AncillaryData_{}{}.gdb".format(today_string.split('_')[0], ticket)
    ancillary_gdb = os.path.join(workspace, ancillary_gdb_name)
    arcpy.CreateFileGDB_management(workspace, ancillary_gdb_name)
    ancillary_params = [workspace, chrome_driver_path, log_file_path, ancillary_gdb]

#log the hazards to be updated
writeMessages(log_file_path, "### Hazard Update Log File ###\n\nDate/Time: {}\n\n".format(today_string), False)

if len(update_hazards) == 0:
    hazard_list_string = " --- No Hazards Selected ---"
else:
    hazard_list_string = "".join(update_hazards)

m = "\nThe following hazards have been selected for updating:\n{}\n".format(hazard_list_string)
writeMessages(log_file_path, m)

if len(ancillary_data_updates) == 0:
    ancillary_list_string = " --- No Ancillary Datasets Selected ---"
else:
    ancillary_list_string = "".join(ancillary_data_updates)
m = "\nThe following ancillary datasets have been selectd for updating:\n{}\n".format(ancillary_list_string)
writeMessages(log_file_path, m)


hazard_results = list()

if run_flood:
    flood_params = hazard_params + [flood_zip]
    flood = runFlood(*flood_params)
    hazard_results.append(flood)
if run_dam_inundation:
    dam_params = hazard_params + [dam_inundation_zip]
    dam_inundation = runDamInundation(*dam_params)
    hazard_results.append(dam_inundation)
if run_CGS_hazards:
    cgs_layers = runCGS(*hazard_params)
    hazard_results.append(cgs_layers)
if run_farmland:
    farmland = runFarmland(*hazard_params)
    hazard_results.append(farmland)
if run_solid_waste:
    solid_waste = runSolidWasteFacilities(*hazard_params)
    hazard_results.append(solid_waste)
if run_epa_hazards:
    epa_layers = runEPALayers(*hazard_params)
    hazard_results.append(epa_layers)
if run_mining_operations:
    mines = runMiningOperations(*hazard_params)
    hazard_results.append(mines)
if run_state_priority_list:
    spl_hazard_params = hazard_params + [spl_sites]
    spl = runStatePriorityList(*spl_hazard_params)
    hazard_results.append(spl)
if run_lust:
    lust = runLUST(*hazard_params)
    hazard_results.append(lust)
if run_ust:
    ust = runUST(*hazard_params)
    hazard_results.append(ust)
if run_fuds:
    fuds = runFUDs(*hazard_params)
    hazard_results.append(fuds)
if run_geothermalwells:
    geothermwells = runGeothermalWells(*hazard_params)
    hazard_results.append(geothermwells)
if run_allwells:
    all_wells = runAllWells(*hazard_params)
    hazard_results.append(all_wells)
if run_electric_transmission_lines:
    electric_transmission_lines = runElectricTransmissionLines(*hazard_params)
    hazard_results.append(electric_transmission_lines)
if run_railroads:
    railroads = runRailroads(*hazard_params)
    hazard_results.append(railroads)
if run_agtimber_resources:
    agtimber_resources = runAgTimberResources(*hazard_params)
    hazard_results.append(agtimber_resources)
if run_criticalhabitat:
    criticalhabitat_hazard_params = hazard_params + [criticalhabitat_zip, forestservice_zip]
    criticalhabitat = runCriticalHabitat(*criticalhabitat_hazard_params)
    hazard_results.append(criticalhabitat)
if run_tsunami_inundation:
    tsunami_hazard_params = hazard_params + [supplimental_flood_fc]
    supplimental_flood = runTsunamiInundaiton(*tsunami_hazard_params)
    hazard_results.append(supplimental_flood)
if run_vcp:
    vcp = runVCPHazard(*hazard_params)
    hazard_results.append(vcp)
if run_erns:
    erns = runERNSHazard(*hazard_params)
    hazard_results.append(erns)
if run_clandestine:
    clandestine = runClandestineLabs(*hazard_params)
    hazard_results.append(clandestine)
if run_coastalerosion:
    coastalerosion = runCoastalBluffsErosion(*hazard_params)
    hazard_results.append(coastalerosion)
if run_subsidence:
    subsidence_params = hazard_params + [subsidence_tif]
    subsidence = runSubsidence(*subsidence_params)
    hazard_results.append(subsidence)
if run_sra:
    sra_params = hazard_params + [current_jurisdictions_fc_path]
    sra = runSRA(*sra_params)
    hazard_results.append(sra)
if run_jurisdictions:
    jurisdictions = runCAJurisdictions(*ancillary_params)
    hazard_results.append(jurisdictions)
if run_firedistricts:
    firedistricts = runCAFireDistricts(*ancillary_params)
    hazard_results.append(firedistricts)

m = "\n\n ------------ Script Complete ------------\n\n\tUpdates Saved Here:\n\t\t{}\n\n\tUpdate Details:\n\t\t{}\n\n -------------    End Log     ------------".format(workspace, log_file_path)
writeMessages(log_file_path, m)

