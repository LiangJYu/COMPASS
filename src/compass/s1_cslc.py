from compass import s1_rdr2geo, s1_geo2rdr, s1_resample
from compass.utils.runconfig import RunConfig
from compass.utils.yaml_argparse import YamlArgparse


def run(cfg):
    # If boolean flag "is_reference" is true
    # Run rdr2geo and archive reference burst
    if cfg.is_reference:
        s1_rdr2geo.run(cfg)
    else:
        s1_geo2rdr.run(cfg)
        s1_resample.run(cfg)


if __name__ == "__main__":
    '''run rdr2geo from command line'''
    # load command line args
    arg_parser = YamlArgparse()

    # get a runconfig dict from command line args
    runconfig = RunConfig.load_from_yaml(arg_parser.run_config_path, 's1_cslc_radar')

    # run rdr2geo
    run(runconfig)
