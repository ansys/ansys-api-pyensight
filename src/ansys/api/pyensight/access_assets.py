import os

def ensight_api_test_assests():
    """Read ensight_api_test_assets.txt and return it as string.

    Returns
    -------
    str
        The file contents as string.
    """
    dir = os.path.dirname(__file__)
    assets_file_name = os.path.join(dir, "assets", "ensight_api_test_assets.txt")
    with open(assets_file_name, "r") as file:
        file_str = file.read()
    return file_str
