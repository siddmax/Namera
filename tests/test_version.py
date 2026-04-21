from importlib.metadata import version as dist_version

import namera


def test_package_version_matches_distribution_metadata():
    assert namera.__version__ == dist_version("namera")
