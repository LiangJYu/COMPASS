import os
import pytest
import types

from compass.utils import iono

@pytest.fixture(scope='session')
def ionex_params(download_data=True):
    '''
    Prepare IONEX data for unit test

    Parameters
    ----------
    download_data: bool
        Boolean flag allow to download TEC data
        for unit test if set to True

    Returns
    -------
    tec_file: str
        Path to local or downloaded TEC file to
        use in the unit test
    '''
    test_params = types.SimpleNamespace()

    # Set the path to fetch data for the test
    test_params.tec_dir = os.path.join(os.path.dirname(__file__), "data")
    test_params.date_str = '20151115'
    test_params.sol_code = 'jpl'

    # Create TEC directory
    os.makedirs(test_params.tec_dir, exist_ok=True)

    # Generate the TEC filename
    tec_file = iono.get_ionex_filename(test_params.date_str,
                                       tec_dir=test_params.tec_dir,
                                       sol_code=test_params.sol_code)

    # TODO figure out how to toggle download
    # If prep_mode=True, download data
    if download_data:
        if not os.path.isfile(tec_file):
            print(f'Download IONEX file at {test_params.date_str} from '
                  f'{test_params.sol_code} to {test_params.tec_dir}')
            tec_file = iono.download_ionex(test_params.date_str,
                                           test_params.tec_dir,
                                           sol_code=test_params.sol_code)

    test_params.tec_file = tec_file

    return test_params
