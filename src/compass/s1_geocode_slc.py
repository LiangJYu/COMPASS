#!/usr/bin/env python

'''wrapper for geocoded SLC'''

from datetime import timedelta
import os
import time

import isce3
import journal
import numpy as np
from osgeo import gdal

from compass import s1_rdr2geo
from compass import s1_geocode_metadata

from compass.utils.elevation_antenna_pattern import apply_eap_correction
from compass.utils.geo_metadata import GeoCslcMetadata
from compass.utils.geo_runconfig import GeoRunConfig
from compass.utils.helpers import get_module_name
from compass.utils.range_split_spectrum import range_split_spectrum
from compass.utils.yaml_argparse import YamlArgparse
from s1reader.s1_reader import is_eap_correction_necessary

def run(cfg: GeoRunConfig):
    '''
    Run geocode burst workflow with user-defined
    args stored in dictionary runconfig *cfg*

    Parameters
    ---------
    cfg: GeoRunConfig
        GeoRunConfig object with user runconfig options
    '''
    module_name = get_module_name(__file__)
    info_channel = journal.info(f"{module_name}.run")
    info_channel.log(f"Starting {module_name} burst")

    # Start tracking processing time
    t_start = time.time()

    # Common initializations
    image_grid_doppler = isce3.core.LUT2d()
    threshold = cfg.geo2rdr_params.threshold
    iters = cfg.geo2rdr_params.numiter
    blocksize = cfg.geo2rdr_params.lines_per_block
    flatten = cfg.geocoding_params.flatten

    # process one burst only
    for burst in cfg.bursts:
        # Reinitialize the dem raster per burst to prevent raster artifacts
        # caused by modification in geocodeSlc
        dem_raster = isce3.io.Raster(cfg.dem)
        epsg = dem_raster.get_epsg()
        proj = isce3.core.make_projection(epsg)
        ellipsoid = proj.ellipsoid

        date_str = burst.sensing_start.strftime("%Y%m%d")
        burst_id = burst.burst_id
        pol = burst.polarization
        id_pol = f"{burst_id}_{pol}"
        geo_grid = cfg.geogrids[burst_id]

        # Create top output path
        burst_output_path = f'{cfg.product_path}/{burst_id}/{date_str}'
        os.makedirs(burst_output_path, exist_ok=True)

        scratch_path = f'{cfg.scratch_path}/{burst_id}/{date_str}'
        os.makedirs(scratch_path, exist_ok=True)

        radar_grid = burst.as_isce3_radargrid()
        native_doppler = burst.doppler.lut2d
        orbit = burst.orbit

        # Get azimuth polynomial coefficients for this burst
        az_carrier_poly2d = burst.get_az_carrier_poly()

        # Generate required metadata layers
        if cfg.rdr2geo_params.enabled:
            s1_rdr2geo.run(cfg, save_in_scratch=True)
            if cfg.rdr2geo_params.geocode_metadata_layers:
               s1_geocode_metadata.run(cfg, fetch_from_scratch=True)

        #Load the input burst SLC
        temp_slc_path = f'{scratch_path}/{id_pol}_temp.vrt'
        burst.slc_to_vrt_file(temp_slc_path)

        # Check if EAP correction is necessary
        check_eap = is_eap_correction_necessary(burst.ipf_version)
        if check_eap.phase_correction:
            temp_slc_path_corrected = temp_slc_path.replace('_temp.vrt',
                                                            '_corrected_temp.rdr')
            apply_eap_correction(burst,
                                 temp_slc_path,
                                 temp_slc_path_corrected,
                                 check_eap)
            # Replace the input burst if the correction is applied
            temp_slc_path = temp_slc_path_corrected


        # Split the range bandwidth of the burst, if required
        if cfg.split_spectrum_params.enabled:
            rdr_burst_raster = range_split_spectrum(burst,
                                                    temp_slc_path,
                                                    cfg.split_spectrum_params,
                                                    scratch_path)
        else:
            rdr_burst_raster = isce3.io.Raster(temp_slc_path)

        # Generate output geocoded burst raster
        geo_burst_raster = isce3.io.Raster(
            f'{burst_output_path}/{id_pol}.slc',
            geo_grid.width, geo_grid.length,
            rdr_burst_raster.num_bands, gdal.GDT_CFloat32,
            cfg.geocoding_params.output_format)

        # Extract burst boundaries
        b_bounds = np.s_[burst.first_valid_line:burst.last_valid_line,
                   burst.first_valid_sample:burst.last_valid_sample]

        # Create sliced radar grid representing valid region of the burst
        sliced_radar_grid = burst.as_isce3_radargrid()[b_bounds]

        # Geocode
        isce3.geocode.geocode_slc(geo_burst_raster, rdr_burst_raster,
                                  dem_raster,
                                  radar_grid, sliced_radar_grid,
                                  geo_grid, orbit,
                                  native_doppler,
                                  image_grid_doppler, ellipsoid, threshold,
                                  iters, blocksize, flatten,
                                  azimuth_carrier=az_carrier_poly2d)

        # Set geo transformation
        geotransform = [geo_grid.start_x, geo_grid.spacing_x, 0,
                        geo_grid.start_y, 0, geo_grid.spacing_y]
        geo_burst_raster.set_geotransform(geotransform)
        geo_burst_raster.set_epsg(epsg)
        del geo_burst_raster
        del dem_raster # modified in geocodeSlc

        # Save burst metadata
        metadata = GeoCslcMetadata.from_georunconfig(cfg, burst_id)
        json_path = f'{burst_output_path}/{id_pol}.json'
        with open(json_path, 'w') as f_json:
            metadata.to_file(f_json, 'json')

    dt = str(timedelta(seconds=time.time() - t_start)).split(".")[0]
    info_channel.log(f"{module_name} burst successfully ran in {dt} (hr:min:sec)")


if __name__ == "__main__":
    '''Run geocode cslc workflow from command line'''
    # load arguments from command line
    parser = YamlArgparse()

    # Get a runconfig dict from command line argumens
    cfg = GeoRunConfig.load_from_yaml(parser.run_config_path,
                                      workflow_name='s1_cslc_geo')

    # Run geocode burst workflow
    run(cfg)
