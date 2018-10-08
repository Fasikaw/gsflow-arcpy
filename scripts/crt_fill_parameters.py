#--------------------------------
# Name:         crt_fill_parameters.py
# Purpose:      GSFLOW CRT fill parameters
# Notes:        ArcGIS 10.2 Version
# Python:       2.7
#--------------------------------

import argparse
from collections import defaultdict
import ConfigParser
import datetime as dt
import logging
import math
import os
import shutil
import subprocess
import sys

import arcpy
from arcpy import env

import support_functions as support


def crt_fill_parameters(config_path, overwrite_flag=False, debug_flag=False):
    """Calculate GSFLOW CRT Fill Parameters

    Args:
        config_file (str): Project config file path
        ovewrite_flag (bool): if True, overwrite existing files
        debug_flag (bool): if True, enable debug level logging

    Returns:
        None
    """

    # Initialize hru_parameters class
    hru = support.HRUParameters(config_path)

    # Open input parameter config file
    inputs_cfg = ConfigParser.ConfigParser()
    try:
        inputs_cfg.readfp(open(config_path))
    except Exception as e:
        logging.error(
            '\nERROR: Config file could not be read, '
            'is not an input file, or does not exist\n'
            '  config_file = {}\n'
            '  Exception: {}\n'.format(config_path, e))
        sys.exit()

    # Log DEBUG to file
    log_file_name = 'crt_fill_parameters_log.txt'
    log_console = logging.FileHandler(
        filename=os.path.join(hru.log_ws, log_file_name), mode='w')
    log_console.setLevel(logging.DEBUG)
    log_console.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger('').addHandler(log_console)
    logging.info('\nGSFLOW CRT Fill Parameters')

    # Parameters
    exit_seg = 0

    # CRT Parameters
    try:
        use_crt_fill_flag = inputs_cfg.getboolean(
            'INPUTS', 'use_crt_fill_flag')
    except ConfigParser.NoOptionError:
        use_crt_fill_flag = False
        logging.info(
            '  Missing INI parameter, setting {} = {}'.format(
                'use_crt_fill_flag', use_crt_fill_flag))

    try:
        crt_hruflg = inputs_cfg.getint('INPUTS', 'crt_hruflg')
    except ConfigParser.NoOptionError:
        crt_hruflg = 0
        logging.info(
            '  Missing INI parameter, setting {} = {}'.format(
                'crt_hruflg', crt_hruflg))
    try:
        crt_flowflg = inputs_cfg.getint('INPUTS', 'crt_flowflg')
    except ConfigParser.NoOptionError:
        crt_flowflg = 1
        logging.info(
            '  Missing INI parameter, setting {} = {}'.format(
                'crt_flowflg', crt_flowflg))
    try:
        crt_dpit = inputs_cfg.getfloat('INPUTS', 'crt_dpit')
    except ConfigParser.NoOptionError:
        crt_dpit = 0.01
        logging.info(
            '  Missing INI parameter, setting {} = {}'.format(
                'crt_dpit', crt_dpit))
    try:
        crt_outitmax = inputs_cfg.getint('INPUTS', 'crt_outitmax')
    except ConfigParser.NoOptionError:
        crt_outitmax = 100000
        logging.info(
            '  Missing INI parameter, setting {} = {}'.format(
                'crt_outitmax', crt_outitmax))

    # Intentionally not allowing user to change this value
    crt_iprn = 1

    # CRT Fill Parameters
    fill_ws_name = 'fill_work'
    fill_strmflg = 0
    fill_visflg = 0
    fill_ifill = 1

    # CRT Executable
    crt_exe_path = inputs_cfg.get('INPUTS', 'crt_exe_path')
    output_name = 'outputstat.txt'

    # Check input paths
    if not arcpy.Exists(hru.polygon_path):
        logging.error(
            '\nERROR: Fishnet ({}) does not exist\n'.format(
                hru.polygon_path))
        sys.exit()
    # Check that input fields exist and have data
    # Fields generated by hru_parameters
    for f in [hru.type_field, hru.row_field, hru.col_field]:
        if not arcpy.ListFields(hru.polygon_path, f):
            logging.error(
                '\nERROR: Input field {} is not present in fishnet'
                '\nERROR: Try re-running hru_parameters.py\n'.format(f))
            sys.exit()
        elif support.field_stat_func(hru.polygon_path, f, 'MAXIMUM') == 0:
            logging.error(
                '\nERROR: Input field {} contains only 0'
                '\nERROR: Try re-running hru_parameters.py\n'.format(f))
            sys.exit()
    # Fields generated by dem_2_streams
    for f in [hru.irunbound_field, hru.iseg_field, hru.flow_dir_field,
              hru.outflow_field, hru.subbasin_field]:
        if not arcpy.ListFields(hru.polygon_path, f):
            logging.error(
                 '\nERROR: Input field {} is not present in fishnet'
                 '\nERROR: Try re-running dem_2_streams.py\n'.format(f))
            sys.exit()
        elif support.field_stat_func(hru.polygon_path, f, 'MAXIMUM') == 0:
            logging.error(
                 '\nERROR: Input field {} contains only 0'
                 '\nERROR: Try re-running dem_2_streams.py\n'.format(f))
            sys.exit()

    # Build output folder if necessary
    fill_ws = os.path.join(hru.param_ws, fill_ws_name)
    if not os.path.isdir(fill_ws):
        os.makedirs(fill_ws)

    # Copy CRT executable if necessary
    crt_exe_name = os.path.basename(crt_exe_path)
    if not os.path.isfile(os.path.join(fill_ws, crt_exe_name)):
        shutil.copy(crt_exe_path, fill_ws)
    if not os.path.isfile(os.path.join(fill_ws, crt_exe_name)):
        logging.error(
            '\nERROR: CRT executable ({}) does not exist\n'.format(
                os.path.join(fill_ws, crt_exe_name)))
        sys.exit()

    # Fill files
    fill_hru_casc_path = os.path.join(fill_ws, 'HRU_CASC.DAT')
    fill_outflow_hru_path = os.path.join(fill_ws, 'OUTFLOW_HRU.DAT')
    fill_land_elev_path = os.path.join(fill_ws, 'LAND_ELEV.DAT')
    fill_xy_path = os.path.join(fill_ws, 'XY.DAT')

    # Output names
    # dem_adj_raster_name = 'dem_adj'
    # hru_type_raster_name = 'hru_type'
    # lakes_raster_name = 'lakes'
    # streams_raster_name = 'streams'
    # iseg_raster_name = 'iseg'
    # irunbound_raster_name = 'irunbound'

    # Output raster paths
    # dem_adj_raster = os.path.join(fill_ws, dem_adj_raster_name + '.img')
    # hru_type_raster = os.path.join(fill_ws, hru_type_raster_name + '.img')

    # Output ascii paths
    # a_fmt = '{}_ascii.txt'
    # dem_adj_ascii = os.path.join(fill_ws, a_fmt.format(dem_adj_raster_name))
    # hru_type_ascii = os.path.join(fill_ws, a_fmt.format(hru_type_raster_name))


    # Set ArcGIS environment variables
    arcpy.CheckOutExtension('Spatial')
    env.overwriteOutput = True
    # env.pyramid = 'PYRAMIDS -1'
    env.pyramid = 'PYRAMIDS 0'
    env.workspace = fill_ws
    env.scratchWorkspace = hru.scratch_ws

    # Add fields if necessary
    logging.info('\nAdding fields if necessary')
    support.add_field_func(hru.polygon_path, hru.krch_field, 'LONG')
    support.add_field_func(hru.polygon_path, hru.irch_field, 'LONG')
    support.add_field_func(hru.polygon_path, hru.jrch_field, 'LONG')
    support.add_field_func(hru.polygon_path, hru.iseg_field, 'LONG')
    support.add_field_func(hru.polygon_path, hru.reach_field, 'LONG')
    # add_field_func(hru.polygon_path, hru.rchlen_field, 'LONG')
    support.add_field_func(hru.polygon_path, hru.maxreach_field, 'LONG')
    support.add_field_func(hru.polygon_path, hru.outseg_field, 'LONG')
    support.add_field_func(hru.polygon_path, hru.irunbound_field, 'LONG')
    support.add_field_func(hru.polygon_path, hru.crt_elev_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.crt_fill_field, 'DOUBLE')

    # Calculate KRCH, IRCH, JRCH for stream segments
    logging.info('\nKRCH, IRCH, & JRCH for streams')
    fields = [
        hru.type_field, hru.iseg_field, hru.row_field, hru.col_field,
        hru.krch_field, hru.irch_field, hru.jrch_field]
    with arcpy.da.UpdateCursor(hru.polygon_path, fields) as update_c:
        for row in update_c:
            if (int(row[0]) in [1, 3] and int(row[1]) > 0):
                row[4], row[5], row[6] = 1, int(row[2]), int(row[3])
            else:
                row[4], row[5], row[6] = 0, 0, 0
            update_c.updateRow(row)

    # Get list of segments and downstream cell for each stream/lake cell
    # Downstream is calulated from flow direction
    # Use IRUNBOUND instead of ISEG, since ISEG will be zeroed for lakes
    logging.info('Cell out-flow dictionary')
    cell_dict = dict()
    fields = [
        hru.type_field, hru.krch_field, hru.lake_id_field, hru.iseg_field,
        hru.irunbound_field, hru.dem_adj_field, hru.flow_dir_field,
        hru.col_field, hru.row_field, hru.id_field]
    for row in arcpy.da.SearchCursor(hru.polygon_path, fields):
        # Skip inactive cells
        if int(row[0]) == 0:
            continue
        # Skip non-lake and non-stream cells
        if (int(row[1]) == 0 and int(row[2]) == 0):
            continue
        # Read in parameters
        cell = (int(row[7]), int(row[8]))
        # support.next_row_col(FLOW_DIR, CELL)
        # HRU_ID, ISEG,  NEXT_CELL, DEM_ADJ, X, X, X
        cell_dict[cell] = [
            int(row[9]), int(row[4]), support.next_row_col(int(row[6]), cell),
            float(row[5]), 0, 0, 0]
        del cell
    # Build list of unique segments
    iseg_list = sorted(list(set([v[1] for v in cell_dict.values()])))

    # Calculate IREACH and OUTSEG
    logging.info('Calculate {} and {}'.format(
        hru.reach_field, hru.outseg_field))
    outseg_dict = dict()
    for iseg in iseg_list:
        # logging.debug('    Segment: {}'.format(iseg))
        # Subset of cell_dict for current iseg
        iseg_dict = dict(
            [(k, v) for k, v in cell_dict.items() if v[1] == iseg])
        # List of all cells in current iseg
        iseg_cells = iseg_dict.keys()
        # List of out_cells for all cells in current iseg
        out_cells = [value[2] for value in iseg_dict.values()]
        # Every iseg will (should?) have one out_cell
        out_cell = list(set(out_cells) - set(iseg_cells))[0]
        # If not output cell, assume edge of domain
        try:
            outseg = cell_dict[out_cell][1]
        except KeyError:
            outseg = exit_seg
        # Track sub-basin outseg
        outseg_dict[iseg] = outseg
        if iseg > 0:
            # Calculate reach number for each cell
            reach_dict = dict()
            start_cell = list(set(iseg_cells) - set(out_cells))[0]
            for i in xrange(len(out_cells)):
                # logging.debug('    Reach: {}  Cell: {}'.format(i+1, start_cell))
                reach_dict[start_cell] = i + 1
                start_cell = iseg_dict[start_cell][2]
            # For each cell in iseg, save outseg, reach, & maxreach
            for iseg_cell in iseg_cells:
                cell_dict[iseg_cell][4:] = [
                    outseg, reach_dict[iseg_cell], len(iseg_cells)]
            del reach_dict, start_cell
        else:
            # For each lake segment cell, only save outseg
            # All lake cells are routed directly to the outseg
            for iseg_cell in iseg_cells:
                cell_dict[iseg_cell][4:] = [outseg, 0, 0]
        del iseg_dict, iseg_cells, iseg
        del out_cells, out_cell, outseg

    # Saving ireach and outseg
    logging.info('Save {} and {}'.format(hru.reach_field, hru.outseg_field))
    fields = [
        hru.type_field, hru.iseg_field, hru.col_field, hru.row_field,
        hru.outseg_field, hru.reach_field, hru.maxreach_field]
    with arcpy.da.UpdateCursor(hru.polygon_path, fields) as update_c:
        for row in update_c:
            # if (int(row[0]) > 0 and int(row[1]) > 0):
            # #DEADBEEF - I'm not sure why only iseg > 0 in above line
            # DEADBEEF - This should set outseg for streams and lakes
            if (int(row[0]) > 0 and int(row[1]) != 0):
                row[4:] = cell_dict[(int(row[2]), int(row[3]))][4:]
            else:
                row[4:] = [0, 0, 0]
            update_c.updateRow(row)

    # Set all lake iseg to 0
    logging.info('Lake {}'.format(hru.iseg_field))
    update_rows = arcpy.UpdateCursor(hru.polygon_path)
    for row in update_rows:
        if int(row.getValue(hru.type_field)) != 2:
            continue
        iseg = int(row.getValue(hru.iseg_field))
        if iseg < 0:
            row.setValue(hru.iseg_field, 0)
        update_rows.updateRow(row)
        del row, iseg
    del update_rows

    # Set environment parameters
    env.extent = hru.extent
    env.cellsize = hru.cs
    env.outputCoordinateSystem = hru.sr

    # # Build rasters
    # logging.info('\nOutput model grid rasters')
    # arcpy.PolygonToRaster_conversion(
    #    hru.polygon_path, hru.type_field, hru_type_raster,
    #    'CELL_CENTER', '', hru.cs)
    # arcpy.PolygonToRaster_conversion(
    #    hru.polygon_path, hru.dem_adj_field, dem_adj_raster,
    #    'CELL_CENTER', '', hru.cs)
    #
    # # Build rasters
    # logging.info('Output model grid ascii')
    # arcpy.RasterToASCII_conversion(hru_type_raster, hru_type_ascii)
    # arcpy.RasterToASCII_conversion(dem_adj_raster, dem_adj_ascii)

    logging.debug('\nRemoving existing CRT fill files')
    if os.path.isfile(fill_outflow_hru_path):
        os.remove(fill_outflow_hru_path)
    if os.path.isfile(fill_hru_casc_path):
        os.remove(fill_hru_casc_path)
    if os.path.isfile(fill_land_elev_path):
        os.remove(fill_land_elev_path)
    if os.path.isfile(fill_xy_path):
        os.remove(fill_xy_path)

    # Input parameters files for Cascade Routing Tool (CRT)
    logging.info('\nBuilding output CRT fill files')

    # Generate OUTFLOW_HRU.DAT for CRT
    # Outflow cells exit the model to inactive cells or out of the domain
    #   Outflow field is set in dem_2_streams
    logging.info('  {}'.format(os.path.basename(fill_outflow_hru_path)))
    outflow_hru_list = []
    fields = [
        hru.type_field, hru.outflow_field, hru.subbasin_field,
        hru.row_field, hru.col_field]
    for row in arcpy.da.SearchCursor(hru.polygon_path, fields):
        if int(row[0]) != 0 and int(row[1]) == 1:
            outflow_hru_list.append([int(row[3]), int(row[4])])
    if outflow_hru_list:
        with open(fill_outflow_hru_path, 'w+') as f:
            f.write('{}    NUMOUTFLOWHRU\n'.format(
                len(outflow_hru_list)))
            for i, outflow_hru in enumerate(outflow_hru_list):
                f.write('{} {} {}   OUTFLOW_ID ROW COL\n'.format(
                    i + 1, outflow_hru[0], outflow_hru[1]))
        f.close()
    else:
        logging.error('\nERROR: No OUTFLOWHRU points, exiting')
        sys.exit()
    del outflow_hru_list

    # # DEADBEEF - Old method for setting OUTFLOW_HRU.DAT
    # #   Only streams that flow to real gauges are used
    # # Generate OUTFLOW_HRU.DAT for CRT
    # logging.info('  {}'.format(
    #    os.path.basename(fill_outflow_hru_path)))
    # outflow_hru_list = []
    # fields = [
    #    hru.type_field, hru.iseg_field, hru.outseg_field, hru.reach_field,
    #    hru.maxreach_field, hru.col_field, hru.row_field]
    # for row in arcpy.da.SearchCursor(hru.polygon_path, fields):
    #    if int(row[0]) != 1 or int(row[1]) == 0:
    #        continue
    #    if int(row[2]) == 0 and int(row[3]) == int(row[4]):
    #        outflow_hru_list.append([int(row[6]), int(row[5])])
    # if outflow_hru_list:
    #    with open(fill_outflow_hru_path, 'w+') as f:
    #        f.write('{}    NUMOUTFLOWHRU\n'.format(
    #            len(outflow_hru_list)))
    #        for i, outflow_hru in enumerate(outflow_hru_list):
    #            f.write('{} {} {}   OUTFLOW_ID ROW COL\n'.format(
    #                i+1, outflow_hru[0], outflow_hru[1]))
    #    f.close()
    # del outflow_hru_list

    # Generate HRU_CASC.DAT for CRT from hru_polygon
    logging.info('  {}'.format(os.path.basename(fill_hru_casc_path)))
    hru_type_dict = defaultdict(dict)
    for row in sorted(arcpy.da.SearchCursor(
            hru.polygon_path,
            [hru.row_field, hru.col_field, hru.type_field, hru.dem_adj_field])):
        # Calculate CRT fill for all non-lake and non-ocean (elev > 0) cells
        # if row[3] > 0 and row[2] == 0:
        #    hru_type_dict[int(row[0])][int(row[1])] = 1
        # else: hru_type_dict[int(row[0])][int(row[1])] = row[2]
        # Calculate CRT fill for all active cells
        hru_type_dict[int(row[0])][int(row[1])] = row[2]
    hru_casc_header = (
        '{} {} {} {} {} {} {} {}     '
        'HRUFLG STRMFLG FLOWFLG VISFLG IPRN IFILL DPIT OUTITMAX\n').format(
            crt_hruflg, fill_strmflg, crt_flowflg, fill_visflg,
            crt_iprn, fill_ifill, crt_dpit, crt_outitmax)
    with open(fill_hru_casc_path, 'w+') as f:
        f.write(hru_casc_header)
        for row, col_data in sorted(hru_type_dict.items()):
            f.write(
                ' '.join([str(t) for c, t in sorted(col_data.items())]) +
                '\n')
    f.close()
    del hru_casc_header, hru_type_dict
    # # Generate HRU_CASC.DATA for CRT from raster/ascii
    # with open(hru_type_ascii, 'r') as f: ascii_data = f.readlines()
    # f.close()
    # hru_casc_header = (
    #    '{} {} {} {} {} {} {} {}     ' +
    #    'HRUFLG STRMFLG FLOWFLG VISFLG ' +
    #    'IPRN IFILL DPIT OUTITMAX\n').format(
    #        crt_hruflg, fill_strmflg, crt_flowflg, fill_visflg,
    #        crt_iprn, fill_ifill, crt_dpit, crt_outitmax)
    # with open(fill_hru_casc_path, 'w+') as f:
    #    f.write(hru_casc_header)
    #    for ascii_line in ascii_data[6:]: f.write(ascii_line)
    # f.close()
    # del hru_casc_header, ascii_data

    # Generate LAND_ELEV.DAT for CRT from hru_polygon
    logging.info('  {}'.format(os.path.basename(fill_land_elev_path)))
    dem_adj_dict = defaultdict(dict)
    for row in sorted(arcpy.da.SearchCursor(
            hru.polygon_path, [hru.row_field, hru.col_field, hru.dem_adj_field])):
        dem_adj_dict[int(row[0])][int(row[1])] = row[2]
    with open(fill_land_elev_path, 'w+') as f:
        row_first = dem_adj_dict.keys()[0]
        f.write('{} {}       NROW NCOL\n'.format(
            len(dem_adj_dict.keys()), len(dem_adj_dict[row_first])))
        for row, col_data in sorted(dem_adj_dict.items()):
            f.write(
                ' '.join(['{:10.6f}'.format(t) for c, t in sorted(col_data.items())]) +
                '\n')
    f.close()
    del dem_adj_dict
    # # Generate LAND_ELEV.DAT for CRT from raster/ascii
    # logging.info('  {}'.format(os.path.basename(fill_land_elev_path)))
    # with open(dem_adj_ascii, 'r') as f: ascii_data = f.readlines()
    # f.close()
    # with open(fill_land_elev_path, 'w+') as f:
    #    f.write('{} {}       NROW NCOL\n'.format(
    #        ascii_data[1].split()[1], ascii_data[0].split()[1]))
    #    for ascii_line in ascii_data[6:]: f.write(ascii_line)
    # f.close()
    # del ascii_data

    # Generate XY.DAT for CRT
    logging.info('  {}'.format(os.path.basename(fill_xy_path)))
    xy_list = [
        map(int, row)
        for row in sorted(arcpy.da.SearchCursor(
            hru.polygon_path, [hru.id_field, hru.x_field, hru.y_field]))]
    with open(fill_xy_path, 'w+') as f:
        for line in sorted(xy_list):
            f.write(' '.join(map(str, line)) + '\n')
    f.close()
    del xy_list

    # Run CRT
    logging.info('\nRunning CRT')
    subprocess.check_output(crt_exe_name, cwd=fill_ws, shell=True)

    # Read in outputstat.txt and get filled DEM
    logging.info('\nReading CRT {}'.format(output_name))
    output_path = os.path.join(fill_ws, output_name)
    with open(output_path, 'r') as f:
        output_data = [l.strip() for l in f.readlines()]
    f.close()

    # Determine where filled data is in the file
    try:
        crt_dem_i = output_data.index(
            'CRT FILLED LAND SURFACE MODEL USED TO GENERATE CASCADES')
        crt_fill_i = output_data.index(
            'DIFFERENCES BETWEEN FILLED AND UNFILLED LAND SURFACE MODELS')
    except ValueError:
        logging.error(
            '\nERROR: CRT didn\'t completely run\n' +
            '  Check the CRT outputstat.txt file\n')
        sys.exit()

    logging.info('  Break indices: {}, {}'.format(
        crt_dem_i, crt_fill_i))
    crt_dem_data = [
        r.split() for r in output_data[crt_dem_i+1: crt_dem_i+hru.rows+1]]
    crt_fill_data = [
        r.split() for r in output_data[crt_fill_i+1: crt_fill_i+hru.rows+1]]
    logging.info('  ROWS/COLS: {}/{}'.format(
        len(crt_dem_data), len(crt_dem_data[0])))
    logging.info('  ROWS/COLS: {}/{}'.format(
        len(crt_fill_data), len(crt_fill_data[0])))

    #   crt_type_i = crt_fill_i + (crt_fill_i - crt_dem_i)

    #    crt_dem_data = [
    #        r.split() for r in output_data[crt_dem_i+1: crt_dem_i+hru.rows+1]]
    #    crt_fill_data = [
    #        r.split() for r in output_data[crt_fill_i+1: crt_type_i-1]]

    # Build dictionaries of the CRT data
    crt_dem_dict = defaultdict(dict)
    crt_fill_dict = defaultdict(dict)
    for i, r in enumerate(crt_dem_data):
        crt_dem_dict[i + 1] = dict(
            [(j + 1, c) for j, c in enumerate(crt_dem_data[i])])
    for i, r in enumerate(crt_fill_data):
        crt_fill_dict[i + 1] = dict(
            [(j + 1, c) for j, c in enumerate(crt_fill_data[i])])

    # Write CRT values to hru_polygon
    logging.info('Writing CRT data to fishnet')
    logging.debug('  {:<4s} {:<4s} {:>7s}'.format('ROW', 'COL', 'FILL'))
    fields = [
        hru.row_field, hru.col_field, hru.crt_elev_field, hru.crt_fill_field,
        hru.dem_adj_field]
    with arcpy.da.UpdateCursor(hru.polygon_path, fields) as update_c:
        for row in update_c:
            # If DEM values are too large for CRT, they may be symbols that will be skipped
            if support.is_number(crt_dem_dict[int(row[0])][int(row[1])]):
                row[2] = float(crt_dem_dict[int(row[0])][int(row[1])])
                row[3] = float(crt_fill_dict[int(row[0])][int(row[1])])
                if float(row[3]) > 0:
                    logging.debug('  {:>4d} {:>4d} {:>7.2f}'.format(
                        row[0], row[1], float(row[3])))
                if use_crt_fill_flag and float(row[3]) > 0:
                    row[4] = row[2]
                update_c.updateRow(row)


def cell_distance(cell_a, cell_b, cs):
    """"""
    ai, aj = cell_a
    bi, bj = cell_b
    return math.sqrt((ai - bi) ** 2 + (aj - bj) ** 2) * cs

# def calc_stream_width(flow_acc):
#    return -2E-6 * flow_acc ** 2 + 0.0092 * flow_acc + 1


def arg_parse():
    """"""
    parser = argparse.ArgumentParser(
        description='CRT Fill',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-i', '--ini', required=True,
        help='Project input file', metavar='PATH')
    parser.add_argument(
        '-o', '--overwrite', default=False, action='store_true',
        help='Force overwrite of existing files')
    parser.add_argument(
        '-d', '--debug', default=logging.INFO, const=logging.DEBUG,
        help='Debug level logging', action='store_const', dest='loglevel')
    args = parser.parse_args()

    # Convert input file to an absolute path
    if os.path.isfile(os.path.abspath(args.ini)):
        args.ini = os.path.abspath(args.ini)
    return args


if __name__ == '__main__':
    args = arg_parse()

    logging.basicConfig(level=args.loglevel, format='%(message)s')
    logging.info('\n{}'.format('#' * 80))
    log_f = '{:<20s} {}'
    logging.info(log_f.format(
        'Run Time Stamp:', dt.datetime.now().isoformat(' ')))
    logging.info(log_f.format('Current Directory:', os.getcwd()))
    logging.info(log_f.format('Script:', os.path.basename(sys.argv[0])))

    # Calculate CRT Fill Parameters
    crt_fill_parameters(
        config_path=args.ini, overwrite_flag=args.overwrite,
        debug_flag=args.loglevel==logging.DEBUG)
