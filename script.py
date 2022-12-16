from resources.lib.common.logger import info
from resources.lib.kodiutils import create_plugin_url, container_update
from resources.lib.params import params

info('START : [{}]'.format(params.all))
plugin_url = create_plugin_url({'url': '/Search/search-people?ms=1&id=search-people&search={}'.format(params.all[3])})
container_update(plugin_url, True)
