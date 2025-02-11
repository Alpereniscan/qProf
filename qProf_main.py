
from qgis.core import *

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *

from . import resources


from .qt_utils.tools import warn
from .qgis_utils.utils import create_action

from .qProf_QWidget import QProfQWidget

_plugin_name_ = "qProf"
_version_ = "0.5.1.1" # This is based on build 0.5.1 


class qProf_main(object):

    def __init__(self, interface):

        self.plugin_name = _plugin_name_
        self.interface = interface
        self.main_window = self.interface.mainWindow()
        self.canvas = self.interface.mapCanvas()

        self.actions = []

    def initGui(self):

        self.qactOpenMainWin = create_action(
            ":/plugins/{}/icons/qprof.png".format(self.plugin_name),
            self.plugin_name,
            self.open_qprof,
            whats_this="Topographic and geological profiles",
            parent=self.interface.mainWindow())
        self.interface.addPluginToMenu(self.plugin_name,
                                       self.qactOpenMainWin)
        self.actions.append(self.qactOpenMainWin)

    def unload(self):

        self.interface.removePluginMenu(self.plugin_name, self.qactOpenMainWin)

    def open_qprof(self):

        project = QgsProject.instance()

        if project.count() == 0:
            warn(
                parent=None,
                header=_plugin_name_,
                msg="No project/layer available.\nPlease open project and add layers.")
            return

        qprof_DockWidget = QDockWidget(self.plugin_name,
                                       self.interface.mainWindow())
        qprof_DockWidget.setAttribute(Qt.WA_DeleteOnClose)
        qprof_DockWidget.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.qProf_QWidget = QProfQWidget(self.plugin_name,
                                          self.canvas)
        qprof_DockWidget.setWidget(self.qProf_QWidget)
        qprof_DockWidget.destroyed.connect(self.qProf_QWidget.closeEvent)
        self.interface.addDockWidget(Qt.RightDockWidgetArea, qprof_DockWidget)

