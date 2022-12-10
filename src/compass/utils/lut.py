'''
Placeholder for model-based correction LUT
'''
import os

import isce3

def compute_geocoding_correction_luts(burst, rg_step=200, az_step=0.25,
                                      dem_path=None, scratch_path=None):
    '''
    Compute slant range and azimuth LUTs corrections
    to be applied during burst geocoding

    Parameters
    ----------
    burst: Sentinel1BurstSlc
        S1-A/B burst object
    xstep: int
        LUT spacing along x/slant range in meters
    ystep: int
        LUT spacing along y/azimuth in seconds
    dem_path: str
        Path to the DEM required for azimuth FM rate mismatch.
        If `None`, the function will raise an error.
    scratch_path: str
        Path to the scratch directory.
        If `None`, `burst.az_fm_rate_mismatch_mitigation()` will
        create temporary directory internally.

    Returns
    -------
    rg_lut: isce3.core.LUT2d
        2D array containing sum of range corrections
    az_lut: isce3.core.LUT2d
        2D array containg sum of azimuth corrections
    '''

    az_lut = burst.bistatic_delay(range_step=rg_step, az_step=az_step)
    rg_lut = burst.geometrical_and_steering_doppler(range_step=rg_step, az_step=az_step)

    if dem_path is None:
        raise ValueError('DEM for azimith FM rate mismatch was not provided.')

    if os.path.exists(dem_path):
        raise FileNotFoundError(f'Cannot find the dem file: {dem_path}')

    az_fm_mismatch = burst.az_fm_rate_mismatch_mitigation(dem_path,
                                                          scratch_path,
                                                          rangeg_step=rg_step,
                                                          az_step=az_step)

    az_lut_data = az_lut.data + az_fm_mismatch.data
    az_lut = isce3.core.LUT2d(az_lut.x_start,
                              az_lut.y_start,
                              az_lut.x_spacing,
                              az_lut.x_spacing,
                              az_lut_data)

    return rg_lut, az_lut
