import math
import importlib
from urllib.parse import urlparse
import fs

def generate_hexagonal_grid(boundingbox, spacing):
    """Generates an hexagonal grid inside a given bounding-box with a given spacing between the vertices"""
    hexheight = spacing
    hexwidth = math.sqrt(3) * spacing / 2
    vertspacing = 0.75 * hexheight
    horizspacing = hexwidth
    sizex = int((boundingbox[1] - boundingbox[0]) / horizspacing) + 2
    sizey = int((boundingbox[3] - boundingbox[2]) / vertspacing) + 2
    if sizey % 2 == 0:
        sizey += 1
    pointsret = []
    for i in range(-2, sizex):
        for j in range(-2, sizey):
            xpos = i * spacing
            ypos = j * spacing
            if j % 2 == 1:
                xpos += spacing * 0.5
            if (j % 2 == 1) and (i == sizex - 1):
                continue
            pointsret.append([int(xpos + boundingbox[0]), int(ypos + boundingbox[2])])
    return pointsret

def load_plugin(class_full_name):
    package, class_name = class_full_name.rsplit('.', 1)
    plugin_module = importlib.import_module(package)
    plugin_class = getattr(plugin_module, class_name)
    return plugin_class

def get_fs_parsed_url(url):
    parsed_url = urlparse(url)
    url_prefix = "{}://{}".format(parsed_url.scheme, parsed_url.netloc)
    return url_prefix, parsed_url.path

def fs_create_dir(output_dir):
    if "://" not in output_dir and ":/" in output_dir:
        output_dir = output_dir.replace(":/", "://")
    fs_loc, fs_path = get_fs_parsed_url(output_dir)
    with fs.open_fs(fs_loc) as out_fs:
        if not out_fs.exists(fs_path):
            out_fs.makedirs(fs_path)

def get_ts_files(ts_folder):

    if "://" not in ts_folder and ":/" in ts_folder:
        ts_folder = ts_folder.replace(":/", "://")
    with fs.open_fs(ts_folder) as cur_fs:
        all_ts_fnames = []
        all_ts_fnames_glob = cur_fs.glob("*.json")
        for ts_fname_glob in all_ts_fnames_glob:
            ts_fname = ts_fname_glob.path
            all_ts_fnames.append(cur_fs.geturl(ts_fname))
        return all_ts_fnames

