"""

  This code is released under the GNU Affero General Public License.

  OpenEnergyMonitor project:
  http://openenergymonitor.org

"""

import os

"""emonhub_version

Reads the emonhub version from version.txt at the root of the install.

Kept in its own module so that interfacers can report the version without
importing emonhub.py, which would be circular: emonhub.py imports every
interfacer.

  version       "2.7.19", or "unknown" if version.txt is missing
  __version__   "v2.7.19", or "v? missing version file"

"""


def _read_version():
    src = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    vpath = os.path.join(os.path.dirname(src), "version.txt")
    try:
        with open(vpath, "r") as f:
            return f.read().strip()
    except OSError:
        return ""


_version = _read_version()

version = _version if _version else "unknown"
__version__ = "v" + _version if _version else "v? missing version file"
