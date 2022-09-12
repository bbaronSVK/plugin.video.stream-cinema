import xbmcgui
from resources.lib.common.logger import debug


class Skip(xbmcgui.WindowXMLDialog):

    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)
        self.callback = None
        self.is_visible = False

    @property
    def is_button_visible(self):
        return self.is_visible

    def onInit(self):  # type: () -> None
        self.setFocus(self.getControl(3001))

    def onClick(self, control_id):
        debug('SKIP onclick: ' + str(control_id))
        if control_id == 3001:
            self.callback()

    def onAction(self, action):  # type: (Action) -> None
        # if action ==
        debug("action: {}".format(action.getId()))
        pass

    def set_visibility(self):
        self.is_visible = not self.is_visible

    def show_with_callback(self, callback):
        self.callback = callback
        if self.is_button_visible is False:
            self.show()
            self.set_visibility()

