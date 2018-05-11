'''
   Copyright (c) 2017 Yogesh Khatri 

   This file is part of mac_apt (macOS Artifact Parsing Tool).
   Usage or distribution of this software/code is subject to the 
   terms of the MIT License.

'''
from __future__ import print_function
#from __future__ import unicode_literals # Must disable for sqlite.row_factory

from helpers.macinfo import *
from helpers.writer import *
from helpers.bookmark import *
from biplist import *
import logging
import sqlite3

__Plugin_Name = "NETUSAGE"
__Plugin_Friendly_Name = "Net Usage"
__Plugin_Version = "1.0"
__Plugin_Description = "Reads the NetUsage (network usage) database to get program and other network usage data"
__Plugin_Author = "Yogesh Khatri"
__Plugin_Author_Email = "yogesh@swiftforensics.com"

__Plugin_Standalone = True
__Plugin_Standalone_Usage = 'Provide one or more netusage sqlite databases as input to process. This is '\
                            'located at /private/var/networkd/netusage.sqlite'

log = logging.getLogger('MAIN.' + __Plugin_Name) # Do not rename or remove this ! This is the logger object

#---- Do not change the variable names in above section ----#

class NetUsage:

    def __init__(self, item_type, item_name, first_seen, last_seen, artifact_date, wifi_in, wifi_out, wired_in, wired_out, wwan_in, wwan_out, bytes_in, bytes_out, comment, source):
        self.item_type = item_type
        self.item_name = item_name
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.artifact_date = artifact_date
        self.wifi_in = wifi_in
        self.wifi_out = wifi_out
        self.wired_in = wired_in
        self.wired_out = wired_out
        self.wwan_in = wwan_in
        self.wwan_out = wwan_out
        self.bytes_in = bytes_in
        self.bytes_out = bytes_out
        self.comment = comment
        self.source_file = source

def PrintAll(netusage_items, output_params):

    netusage_info = [ ('Type',DataType.TEXT),('Name',DataType.TEXT),('FirstSeenDate',DataType.DATE),
                        ('LastSeenDate',DataType.DATE),('ArtifactDate',DataType.DATE),
                        ('WifiIn',DataType.REAL),('WifiOut',DataType.REAL),('WiredIn', DataType.REAL),
                        ('WiredOut',DataType.REAL),('WWanIn',DataType.REAL),('WWanOut',DataType.REAL),
                        ('BytesIn', DataType.REAL),('BytesOut', DataType.REAL),
                        ('Comment',DataType.TEXT),('Source',DataType.TEXT)
                      ]

    log.info (str(len(netusage_items)) + " net usage item(s) found")
    netusage_list = []
    for item in netusage_items:
        n_item = [ item.item_type, item.item_name, item.first_seen, item.last_seen, 
                 item.artifact_date, item.wifi_in, item.wifi_out, item.wired_in, item.wired_out, item.wwan_in,
                 item.wwan_out, item.bytes_in, item.bytes_out, item.comment, item.source_file
                ]
        netusage_list.append(n_item)
    WriteList("net usage information", "NetUsage", netusage_list, netusage_info, output_params, '')

def ReadLastGKRejectPlist(plist):
    bookmark_data = plist.get('BookmarkData', None)
    timestamp = plist.get('TimeStamp', None)
    mal_type = plist.get('XProtectMalwareType', None)

    if bookmark_data:
        bm = Bookmark.from_bytes(bookmark_data)
        file_path = ''
        vol_path = ''
        orig_vol_path = ''
        try:
            # Get full file path
            vol_path = bm.tocs[0][1].get(BookmarkKey.VolumePath, '')
            file_path = bm.tocs[0][1].get(BookmarkKey.Path, [])

            file_path = '/' + '/'.join(file_path)
            if vol_path and (not file_path.startswith(vol_path)):
                file_path += vol_path
            
            # If file is on a mounted volume (dmg), get the dmg file details too
            orig_vol_bm = bm.tocs[0][1].get(BookmarkKey.VolumeBookmark, None)
            if orig_vol_bm:
                filtered = filter(lambda x: x[0]==orig_vol_bm, bm.tocs)
                if filtered:
                    orig_vol_toc = filtered[0][1]
                    orig_vol_path = orig_vol_toc.get(BookmarkKey.Path, '')
                    if orig_vol_path:
                        orig_vol_path = '/' + '/'.join(orig_vol_path)
                else:
                    print ("Error, tid {} not found ".format(orig_vol_bm))
        except:
            log.error('Error processing BookmarkData from .LastGKReject')
            log.debug(bm)

        log.info('.LastGKReject -> File   = {}'.format(file_path))
        if vol_path:
            log.info('.LastGKReject -> Volume = {}'.format(vol_path))
        if orig_vol_path:
            log.info('.LastGKReject -> Orininating Volume = {}'.format(orig_vol_path))

    if mal_type:
        # According to Patrick Wardle (Synack)
        # 2=unsigned, 3= modified bundle, 5=signed app, 7=modified app
        if mal_type == 2:   mal_type = "Unsigned app/program"
        elif mal_type == 3: mal_type = "Modified Bundle"
        elif mal_type == 5: mal_type = "Signed App"
        elif mal_type == 7: mal_type = "Modified App"
        log.info('.LastGKReject -> XProtectMalwareType = {}'.format(mal_type))
    

def ReadNetUsageDb(db, netusage_items, source):
    '''Reads netusage.sqlite db'''
    try:
        query = "SELECT pk.z_name as item_type, na.zidentifier as item_name, "\
                "na.zfirsttimestamp as first_seen_date, "\
                "na.ztimestamp as last_seen_date, "\
                "rp.ztimestamp as rp_date, rp.zbytesin, rp.zbytesout "\
                "FROM znetworkattachment as na  "\
                "LEFT JOIN z_primarykey pk ON na.z_ent = pk.z_ent "\
                "LEFT JOIN zliverouteperf rp ON rp.zhasnetworkattachment = na.z_pk "\
                "ORDER BY pk.z_name, zidentifier, rp_date desc"
        db.row_factory = sqlite3.Row
        cursor = db.execute(query)
        for row in cursor:
            try:
                nu_data = NetUsage(row['item_type'], row['item_name'], CommonFunctions.ReadMacAbsoluteTime(row['first_seen_date']),
                                    CommonFunctions.ReadMacAbsoluteTime(row['last_seen_date']),
                                    CommonFunctions.ReadMacAbsoluteTime(row['rp_date']), '', '', '', '', '','',  row['zbytesin'], 
                                    row['zbytesout'], "Bytes in/out are based off ArtifactDate", source)
                netusage_items.append(nu_data)
            except:
                log.exception('Error fetching row data')
        # Get process info now
        query = "SELECT pk.z_name as item_type ,p.zprocname as process_name, "\
                "p.zfirsttimestamp as first_seen_date, "\
                "p.ztimestamp as last_seen_date, "\
                " lu.ztimestamp as usage_since, "\
                "lu.zwifiin, lu.zwifiout,lu.zwiredin,lu.zwiredout,lu.zwwanin,lu.zwwanout  "\
                "FROM zliveusage lu LEFT JOIN zprocess p ON p.z_pk = lu.zhasprocess  "\
                "LEFT JOIN z_primarykey pk ON p.z_ent = pk.z_ent  "\
                "ORDER BY process_name"
        db.row_factory = sqlite3.Row
        cursor = db.execute(query)
        for row in cursor:
            try:
                nu_data = NetUsage(row['item_type'], row['process_name'], CommonFunctions.ReadMacAbsoluteTime(row['first_seen_date']),
                                    CommonFunctions.ReadMacAbsoluteTime(row['last_seen_date']),
                                    CommonFunctions.ReadMacAbsoluteTime(row['usage_since']), 
                                    row['zwifiin'], row['zwifiout'], row['zwiredin'], row['zwiredout'], row['zwwanin'], row['zwwanout'],
                                    '','', "Data usage is counted from ArtifactDate onwards", source)
                netusage_items.append(nu_data)
            except:
                log.exception('Error fetching row data')
    except:
        log.exception('Query  execution failed. Query was: ' + query)

def OpenDb(inputPath):
    log.info ("Processing file " + inputPath)
    try:
        conn = sqlite3.connect(inputPath)
        log.debug ("Opened database successfully")
        return conn
    except:
        log.exception ("Failed to open database, is it a valid DB?")
    return None

def OpenDbFromImage(mac_info, inputPath):
    '''Returns tuple of (connection, wrapper_obj)'''
    log.info ("Processing net usage events from file {}".format(inputPath))
    try:
        sqlite = SqliteWrapper(mac_info)
        conn = sqlite.connect(inputPath)
        log.debug ("Opened database successfully")
        return conn, sqlite
    except Exception as ex:
        log.exception ("Failed to open database, is it a valid DB?")
    return None

def ProcessDbFromPath(mac_info, netusage_items, source_path):
    if mac_info.IsValidFilePath(source_path):
        mac_info.ExportFile(source_path, __Plugin_Name)
        db, wrapper = OpenDbFromImage(mac_info, source_path)
        if db != None:
            ReadNetUsageDb(db, netusage_items, source_path)
            db.close()

def Plugin_Start(mac_info):
    '''Main Entry point function for plugin'''
    netusage_items = []
    netusage_path  = '/private/var/networkd/netusage.sqlite'
    
    ProcessDbFromPath(mac_info, netusage_items, netusage_path)

    # Also get Last GateKeeper rejected file (not seen in 10.13?)
    gk_reject_path = "/private/var/db/.LastGKReject"
    if mac_info.IsValidFilePath(gk_reject_path):
        mac_info.ExportFile(gk_reject_path, __Plugin_Name)
        success, plist, error = mac_info.ReadPlist(gk_reject_path)
        if success:
            ReadLastGKRejectPlist(plist)
        else:
            log.error("Problem reading .LastGKReject plist - " + error)
    else:
        log.debug('{} not found'.format(gk_reject_path))
    if len(netusage_items) > 0:
        PrintAll(netusage_items, mac_info.output_params)
    else:
        log.info('No net usage data found')

def Plugin_Start_Standalone(input_files_list, output_params):
    log.info("Module Started as standalone")
    for input_path in input_files_list:
        log.debug("Input file passed was: " + input_path)
        if input_path.endswith('.LastGKReject'):
            try:
                plist = readPlist(input_path)
                ReadLastGKRejectPlist(plist)
            except Exception as ex:
                log.exception('Failed to read file: {}'.format(input_path))
        elif input_path.endswith('.sqlite'):
            netusage_items = []
            db = OpenDb(input_path)
            if db != None:
                ReadNetUsageDb(db, netusage_items, input_path)
                db.close()
            if len(netusage_items) > 0:
                PrintAll(netusage_items, output_params)
            else:
                log.info('No net usage data found in {}'.format(input_path))

if __name__ == '__main__':
    print ("This plugin is a part of a framework and does not run independently on its own!")