"""Wrapper for geo2rdr"""
from datetime import timedelta
import os
import time

import isce3
import journal

from compass.utils.runconfig import RunConfig
from compass.utils.yaml_argparse import YamlArgparse


def run(cfg: dict):
    """
    Run geo2rdr with user-defined options
    stored in runconfig dictionary (cfg)

    Parameters
    ----------
    cfg: dict
      Dictionary with user-defined options
    """
    info_channel = journal.info("s1_geo2rdr.run")
    info_channel.log('Starting s1_geo2rdr burst')

    # Tracking time elapsed for processing
    t_start = time.time()

    # Common initializations for different bursts
    dem_raster = isce3.io.Raster(cfg.dem)
    epsg = dem_raster.get_epsg()
    proj = isce3.core.make_projection(epsg)
    ellipsoid = proj.ellipsoid

    # Check if user wants to use GPU for processing
    # Initialize CPU or GPU geo2rdr object
    use_gpu = isce3.core.gpu_check.use_gpu(cfg.gpu_enabled, cfg.gpu_id)
    if use_gpu:
        device = isce3.cuda.core.Device(cfg.gpu_id)
        isce3.cuda.core.set_device(device)
        geo2rdr = isce3.cuda.geometry.Geo2Rdr
    else:
        geo2rdr = isce3.geometry.Geo2Rdr

    # Get specific geo2rdr parameters from runconfig
    threshold = cfg.geo2rdr_params.threshold
    iters = cfg.geo2rdr_params.numiter
    blocksize = cfg.geo2rdr_params.lines_per_block

    # list to keep track of id+dates pairs processed
    id_dates_processed = []

    # Run geo2rdr once per burst ID + date pair
    for burst in cfg.bursts:
        # Extract date string and create directory
        burst_id = burst.burst_id
        date_str = burst.sensing_start.strftime("%Y%m%d")
        id_date = (burst_id, date_str)

        # Create top output path
        top_output_path = f'{cfg.scratch_path}/{burst_id}'
        os.makedirs(top_output_path, exist_ok=True)

        # This ensures running geo2rdr only once; avoiding running for the different polarizations of the same burst_id
        if id_date in id_dates_processed:
            continue
        id_dates_processed.append(id_date)

        # Get topo layers from vrt
        ref_burst_path = cfg.reference_radar_info.path
        topo_raster = isce3.io.Raster(f'{ref_burst_path}/topo.vrt')

        # Create date directory
        burst_output_path = f'{top_output_path}/{date_str}'
        os.makedirs(burst_output_path, exist_ok=True)

        # Get radar grid and orbit
        rdr_grid = burst.as_isce3_radargrid()
        orbit = burst.orbit

        # Initialize geo2rdr object
        geo2rdr_obj = geo2rdr(rdr_grid, orbit, ellipsoid,
                              isce3.core.LUT2d(),
                              threshold, iters,
                              blocksize)

        # Execute geo2rdr
        geo2rdr_obj.geo2rdr(topo_raster, burst_output_path)

    dt = str(timedelta(seconds=time.time() - t_start)).split(".")[0]
    info_channel.log(f"s1_geo2rdr burst successfully ran in {dt} (hr:min:sec)")


if __name__ == "__main__":
    """Run geo2rdr from command line"""
    parser = YamlArgparse()

    # Get a runconfig dict from command line arguments
    cfg = RunConfig.load_from_yaml(parser.args.run_config_path, 's1_geo2rdr')

    # Run geo2rdr
    run(cfg)
