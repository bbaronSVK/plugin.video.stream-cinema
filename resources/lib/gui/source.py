from base import BaseDialog


class SourceXML(BaseDialog):
    def __init__(self, *args, **kwargs):
        super(SourceXML, self).__init__(self, args)
        self.window_id = 2000
        self.results = kwargs.get('results')
        self.total_results = str(len(self.results))
        self.make_items()

    def make_items(self):
        pass

    def onInit(self):
        super(SourceXML, self).onInit()
        win = self.getControl(self.window_id)
        win.addItems(self.item_list)
        self.setFocusId(self.window_id)

    def run(self):
        self.doModal()
        try:
            del self.results
        except:
            pass
        return self.selected

    def onAction(self, action):
        try:
            action_id = action.getId()  # change to just "action" as the ID is already returned in that.
            if action_id in self.info_actions:
                pass
            if action_id in self.selection_actions:
                focus_id = self.getFocusId()
            elif action in self.closing_actions:
                self.selected = (None, '')
                self.close()
        except:
            pass
