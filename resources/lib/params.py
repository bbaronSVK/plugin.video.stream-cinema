import sys
from resources.lib.kodiutils import params as decode


class Params:
    handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
    args = decode(sys.argv[2]) if len(sys.argv) > 2 else {}
    resume = sys.argv[3][7:] != 'false' if len(sys.argv) > 3 else False
    url = None


params = Params()