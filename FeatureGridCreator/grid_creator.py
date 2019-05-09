# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FeatureGridCreator
                                 A QGIS plugin
 Creates a grid of features 
                              -------------------
        begin                : 2014-08-27
        git sha              : $Format:%H$
        copyright            : (C) 2014 by Zuidt
        email                : richard@zuidt.nl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os.path
import math
# Qt
from qgis.PyQt.QtCore import (
    qVersion, 
    QCoreApplication, 
    QSettings, 
    Qt,
    QTranslator, 
    QVariant, 
    QUrl
)
from qgis.PyQt.QtGui import (
    QColor,
    QCursor,
    QDesktopServices,
    QFont, 
    QIcon,
    QPixmap
)
from qgis.PyQt.QtWidgets import (
    QAction,
    QButtonGroup, 
    QDialogButtonBox,
    QMessageBox
)
# Qgis
from qgis.core import (
    QgsCategorizedSymbolRenderer, 
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsGeometry,
    QgsPalLayerSettings,
    QgsPoint,
    QgsPointXY,
    QgsProject,
    QgsRectangle, 
    QgsRendererCategory, 
    QgsSymbol,
    QgsTextBufferSettings, 
    QgsTextFormat, 
    QgsUnitTypes,    
    QgsVectorLayer,
    QgsVectorLayerSimpleLabeling, 
    QgsWkbTypes
)
from qgis.gui import (
    QgsMapTool
)

from grid_creator_dialog import FeatureGridCreatorDialog
from grid_creator_labeler_dialog import FeatureGridCreatorLabelerDialog

# get the logger for this plugin
import logging
from . import LOGGER_NAME
log = logging.getLogger(LOGGER_NAME)

# Initialize Qt resources from file resources.py
#import resources_rc

class FeatureGridCreator:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            '{}.qm'.format(locale))
            #'FeatureGridCreator_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        #
        #   CONSTANTS
        #
        self.SETTINGS_SECTION = 'gridcreator'
        self.MSG_BOX_TITLE = 'Grid creator'
        self.MSG_TRENCHES = self.tr('trenches')
        self.MSG_HOLES = self.tr('holes')
        self.MSG_ABOUT = self.tr('Written by Richard Duivenvoorde (Zuidt)\nEmail - richard@zuidt.nl\n' +
                                'Funded by - SOB Research - http://www.sobresearch.nl\n' +
                                'Source: https://github.com/rduivenvoorde/featuregridcreator')
        self.MSG_NO_ACTIVE_LAYER = self.tr('No active layer found\n' +
            'Please make one (multi)-polygon or (multi)-line layer active by choosing a layer in the legend')
        self.MSG_NO_VECTOR_LAYER = self.tr('Please make one vector layer active by choosing a vector layer in the legend')
        self.MSG_WRONG_GEOM_TYPE = self.tr('Please make one (multi)-polygon or (multi)-line layer layer active by choosing a layer in the legend')
        self.MSG_NO_VALID_LAYER = self.tr('No VALID layer found\n' + \
            'Please make one (multi)-polygon or (multi)-line layer active by choosing a layer in the legend')
        self.MSG_LAYER_NOT_EDITABLE = self.tr('Layer is not editable\n' + \
            'Please make it editable, then enable this tool again and hover over the selected features.')
        self.MSG_NO_SELECTED_FEATURES = self.tr('Layer has no selected features\n' + \
            'Please select a set of features first, then enable this tool again and hover over the features.')
        self.MSG_NO_METER_LAYER = self.tr('Layers crs is not in Unit "meters"\n' + \
                                          'Please use data which has crs in meters, not in e.g. Degrees (not LatLon).')

        self.GRID_SQUARE = 1
        self.GRID_DIAMOND = 2
        self.POINT_FEATURES = 1
        self.TRENCH_FEATURES = 2

        self.RESULT_FEATURE_POINT = 0
        self.RESULT_FEATURE_TRENCH_STRAIGHT = 1
        self.RESULT_FEATURE_TRENCH_BENDED_OR_SHORT = 2

        #
        #   MAIN DIALOG
        #
        # Create the main dialog (after translation) and keep reference
        self.dlg = FeatureGridCreatorDialog()
        self.dlg.setModal(True)
        # init dx and dy values in dialog
        self.dlg.spinBox_dx.setValue(float(self.dx()))
        self.dlg.spinBox_dy.setValue(float(self.dy()))
        self.dlg.spinBox_dx.valueChanged.connect(self.dx_change_slot)
        self.dlg.spinBox_dy.valueChanged.connect(self.dy_change_slot)

        self.dlg.cbx_inside_polygons.toggled.connect(self.inside_polygons_change_slot)
        # set current value from settings
        self.dlg.cbx_inside_polygons.setChecked(self.inside_polygons())

        # init dx and dy values in dialog
        self.dlg.spinBox_trench_width.setValue(int(self.trench_width()))
        self.dlg.spinBox_trench_length.setValue(int(self.trench_length()))
        self.dlg.spinBox_trench_width.valueChanged.connect(self.trench_width_change_slot)
        self.dlg.spinBox_trench_length.valueChanged.connect(self.trench_length_change_slot)

        self.dlg.buttonBox.button(QDialogButtonBox.Apply).clicked.connect(self.create_features)
        self.dlg.buttonBox.helpRequested.connect(self.help)
        self.dlg.buttonBox.rejected.connect(self.hide_create_features_dialog)

        self.grid_shape_group = QButtonGroup()
        # NOTE: first add to group, THEN assign an id to it
        self.grid_shape_group.addButton(self.dlg.radio_square)
        self.grid_shape_group.setId(self.dlg.radio_square, self.GRID_SQUARE)
        self.grid_shape_group.addButton(self.dlg.radio_diamond)
        self.grid_shape_group.setId(self.dlg.radio_diamond, self.GRID_DIAMOND)
        self.grid_shape_group.buttonReleased.connect(self.grid_shape_change_slot)
        # set current value from settings
        self.grid_shape_group.button(self.grid_shape()).setChecked(True)
        # create a 'button group' for buttons with feature types
        self.feature_type_group = QButtonGroup()
        self.feature_type_group.addButton(self.dlg.radio_points)
        self.feature_type_group.setId(self.dlg.radio_points, self.POINT_FEATURES)
        self.feature_type_group.addButton(self.dlg.radio_trenches)
        self.feature_type_group.setId(self.dlg.radio_trenches, self.TRENCH_FEATURES)
        self.feature_type_group.buttonReleased.connect(self.feature_type_change_slot)
        self.feature_type_group.button(self.feature_type()).setChecked(True)
        self.feature_type_change_slot()  # force a signal because above 'setChecked' does not fire a change signal?

        #
        #   LABEL DIALOG
        #
        self.lbl_dlg = FeatureGridCreatorLabelerDialog()
        self.lbl_dlg.le_prefix.setText(self.lbl_prefix())
        self.lbl_dlg.spinbox_number.setValue(self.lbl_number())
        self.lbl_dlg.le_postfix.setText(self.lbl_postfix())
        self.lbl_dlg.le_prefix.textChanged.connect(self.lbl_prefix_change_slot)
        self.lbl_dlg.spinbox_number.valueChanged.connect(self.lbl_number_change_slot)
        self.lbl_dlg.le_postfix.textChanged.connect(self.lbl_postfix_change_slot)
        self.lbl_dlg.buttonBox.helpRequested.connect(self.help)
        self.label_example()  # init the example string

        # Declare instance attributes
        self.actions = []
        self.tool = None
        self.layer = None
        self.menu = self.tr(u'&Feature Grid Creator')

        self.toolbar = self.iface.addToolBar(u'FeatureGridCreator')
        self.toolbar.setObjectName(u'FeatureGridCreator')

    def about(self):
        QMessageBox.information(self.iface.mainWindow(), "Feature Grid Creator About", self.MSG_ABOUT)

    def help(self):
        docs = os.path.join(os.path.dirname(__file__), "help/html/en", "index.html")
        QDesktopServices.openUrl(QUrl("file:" + docs))

    def get_settings_value(self, key, default=''):
        if QSettings().contains(self.SETTINGS_SECTION + key):
            key = self.SETTINGS_SECTION + key
            val = QSettings().value(key)
            return val
        else:
            return default

    def set_settings_value(self, key, value):
        key = self.SETTINGS_SECTION + key
        QSettings().setValue(key, value)

    #
    # MAIN DIALOG setters/getters and slots
    #

    # getter/setter for dx (saved in settings)
    def dx(self, value=None):
        if value is None:
            return float(self.get_settings_value('dx', '10'))
        else:
            self.set_settings_value('dx', value)

    # getter/setter for dy (saved in settings)
    def dy(self, value=None):
        if value is None:
            return float(self.get_settings_value('dy', '10'))
        else:
            self.set_settings_value('dy', value)

    def trench_width(self, value=None):
        if value is None:
            return float(self.get_settings_value('trench_width', '100'))
        else:
            self.set_settings_value('trench_width', value)

    def trench_length(self, value=None):
        if value is None:
            return float(self.get_settings_value('trench_height', '100'))
        else:
            self.set_settings_value('trench_height', value)

    def grid_shape(self, value=None):
        if value is None:
            return int(self.get_settings_value('grid_shape', str(self.GRID_SQUARE)))
        else:
            self.set_settings_value('grid_shape', value)

    def inside_polygons(self, value=None):
        if value is None:
            return self.get_settings_value('inside_polygons', 'True') in ['true', 'True', True]
        else:
            self.set_settings_value('inside_polygons', value)

    def feature_type(self, value=None):
        if value is None:
            return int(self.get_settings_value('feature_type', str(self.POINT_FEATURES)))
        else:
            self.set_settings_value('feature_type', value)
    #
    # SLOTS
    #

    def dx_change_slot(self, dx):
        self.dx(dx)

    def dy_change_slot(self, dy):
        self.dy(dy)

    def trench_width_change_slot(self, w):
        self.trench_width(w)

    def trench_length_change_slot(self, h):
        self.trench_length(h)

    def grid_shape_change_slot(self):
        self.grid_shape(self.grid_shape_group.checkedId())

    def inside_polygons_change_slot(self):
        self.inside_polygons(self.dlg.cbx_inside_polygons.isChecked())

    def feature_type_change_slot(self):
        self.feature_type(self.feature_type_group.checkedId())
        self.dlg.spinBox_trench_length.setEnabled(self.dlg.radio_trenches.isChecked())
        self.dlg.spinBox_trench_width.setEnabled(self.dlg.radio_trenches.isChecked())
        self.dlg.lbl_trench_length.setEnabled(self.dlg.radio_trenches.isChecked())
        self.dlg.lbl_trench_width.setEnabled(self.dlg.radio_trenches.isChecked())

    #
    # LABEL DIALOG setters/getters and slots
    #
    # getter/setter for label prefix (saved in settings)
    def lbl_prefix(self, value=None):
        if value is None:
            return self.get_settings_value('lbl_prefix', 'prefix')
        else:
            self.set_settings_value('lbl_prefix', value)

    # getter/setter for label number (saved in settings)
    def lbl_number(self, value=None):
        if value is None:
            if self.get_settings_value('lbl_number') == '':
                return 1
            return int(self.get_settings_value('lbl_number', '1'))
        else:
            self.set_settings_value('lbl_number', value)

    # getter/setter for label prefix (saved in settings)
    def lbl_postfix(self, value=None):
        if value is None:
            return self.get_settings_value('lbl_postfix', 'postfix')
        else:
            self.set_settings_value('lbl_postfix', value)
    #
    # SLOTS
    #

    def lbl_prefix_change_slot(self, prefix):
        self.lbl_prefix(prefix)
        self.label_example()

    def lbl_number_change_slot(self, number):
        self.lbl_number(number)
        self.label_example()

    def lbl_postfix_change_slot(self, postfix):
        self.lbl_postfix(postfix)
        self.label_example()

    def label(self, number):
        lbl = str(number)
        if not self.lbl_prefix() in ['prefix', '']:
            lbl = self.lbl_prefix() + '_' + lbl
        if not self.lbl_postfix() in ['postfix', '']:
            lbl += '_' + self.lbl_postfix()
        return lbl

    def label_example(self):
        self.lbl_dlg.lbl_example.setText(self.label(self.lbl_number()) + ', ' + self.label(self.lbl_number() + 1)
                                         + ', ' + self.label(self.lbl_number() + 2) + ' ...')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('FeatureGridCreator', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None
    ):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        self.create_action = self.add_action(
            ':/plugins/FeatureGridCreator/icon.png',
            text=self.tr(u'Create a grid of trench or holes'),
            callback=self.show_create_features_dialog,
            parent=self.iface.mainWindow())
        self.create_action.setCheckable(True)

        self.label_action = self.add_action(
            ':/plugins/FeatureGridCreator/icon2.png',
            text=self.tr(u'Label selected features'),
            callback=self.start_labeling,
            parent=self.iface.mainWindow())
        self.label_action.setCheckable(True)

        # help
        self.add_action(
            ':/plugins/FeatureGridCreator/help.png',
            text=self.tr(u'Help'),
            callback=self.help,
            add_to_toolbar=False,
            parent=self.iface.mainWindow())

        # about
        self.add_action(
            ':/plugins/FeatureGridCreator/help.png',
            text=self.tr(u'About'),
            callback=self.about,
            add_to_toolbar=False,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&Feature Grid Creator'),
                action)
            self.iface.removeToolBarIcon(action)

    def show_create_features_dialog(self):
        """Init and show dialog"""
        #pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True)

        if self.init_create_features_dialog():
            # show the dialog
            self.dlg.show()
        else:
            return
        self.create_action.setChecked(True)

    def hide_create_features_dialog(self):
        self.create_action.setChecked(False)

    def init_create_features_dialog(self):
        """
        init dialog based on layer type
        :param self:
        :return: true if ok, false if wrong type of layer
        """
        # check if current active layer is a polygon layer:
        layer = self.iface.activeLayer()
        layer_problem = False
        if layer is None:
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate(self.SETTINGS_SECTION, self.MSG_NO_ACTIVE_LAYER), QMessageBox.Ok, QMessageBox.Ok)
            layer_problem = True
        elif layer.type() > 0:  # 0 = vector, 1 = raster
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate(self.SETTINGS_SECTION, self.MSG_NO_VECTOR_LAYER), QMessageBox.Ok, QMessageBox.Ok)
            layer_problem = True
        # don't know if this is possible / needed
        elif not layer.isValid():
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate(self.SETTINGS_SECTION, self.MSG_NO_VALID_LAYER), QMessageBox.Ok, QMessageBox.Ok)
            layer_problem = True
        if layer_problem:
            self.create_action.setChecked(False)
            self.dlg.hide()
            return False
        # check if current active VECTOR layer has an OK type
        geom_type = layer.dataProvider().wkbType()
        if not(geom_type == QgsWkbTypes.Polygon or geom_type == QgsWkbTypes.MultiPolygon or \
                geom_type == QgsWkbTypes.LineString or geom_type == QgsWkbTypes.MultiLineString or \
                geom_type == QgsWkbTypes.Polygon25D or geom_type == QgsWkbTypes.MultiPolygon25D ):
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate(self.SETTINGS_SECTION, self.MSG_WRONG_GEOM_TYPE), QMessageBox.Ok, QMessageBox.Ok)
            layer_problem = True
        # check layer's projection is not a geographical projection force units in meters
        if layer.crs().mapUnits() !=  QgsUnitTypes.DistanceMeters:
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate(self.SETTINGS_SECTION, self.MSG_NO_METER_LAYER), QMessageBox.Ok, QMessageBox.Ok)
            layer_problem = True
        if layer_problem:
            self.create_action.setChecked(False)
            self.dlg.hide()
            return False

        # disable some dialog parts if geometries in the layer are lines
        geoms_are_polygons = (geom_type == QgsWkbTypes.Polygon or geom_type == QgsWkbTypes.MultiPolygon or \
            geom_type == QgsWkbTypes.Polygon25D or geom_type == QgsWkbTypes.MultiPolygon25D  )
        self.dlg.box_dy.setEnabled(geoms_are_polygons)
        self.dlg.box_grid_shape.setEnabled(geoms_are_polygons)
        self.dlg.box_inside_polygons.setEnabled(geoms_are_polygons)
        self.dlg.progress_bar.setValue(0)

        # now use current active layer as current for the rest of this 'dialog session'
        self.current_layer = self.iface.mapCanvas().currentLayer()
        return True

    def create_features(self):
        active_layer = self.current_layer # self.current_layer is current when dialog was initalised
        self.dlg.progress_bar.setValue(0)

        # for size of progress bar
        fcount = 0
        if len(active_layer.selectedFeatures()) < 1: # NO selection
            features = active_layer.getFeatures()  # iterator
            fcount = active_layer.featureCount()
        else: # selected features
            features = active_layer.selectedFeatures()  # features[]
            fcount = len(features)

        # give the memory layer the same CRS as the source layer
        crs = active_layer.crs()

        if self.feature_type() == self.TRENCH_FEATURES:
            memory_lyr = QgsVectorLayer("Polygon?crs=epsg:" + str(crs.postgisSrid()) + "&index=yes", self.MSG_TRENCHES, "memory")
        else:
            memory_lyr = QgsVectorLayer("Point?crs=epsg:" + str(crs.postgisSrid()) + "&index=yes", self.MSG_HOLES, "memory")

        QgsProject.instance().addMapLayer(memory_lyr)

        provider = memory_lyr.dataProvider()
        provider.addAttributes([
                        QgsField("code", QVariant.String),
                        QgsField("ftype", QVariant.Int)])

        # http://snorf.net/blog/2014/03/04/symbology-of-vector-layers-in-qgis-python-plugins/
        # Categorized symbol renderer for different type of grid features: points, straight trench and bended or stort trench
        # define a lookup: value -> (color, label)
        ftype = {
            '0': ('#00f', self.tr('hole')),
        }
        if self.feature_type() == self.TRENCH_FEATURES:
            ftype = {
                '1': ('#00f', self.tr('trench straight')),
                '2': ('#f00', self.tr('trench bend or short')),
                #'': ('#000', 'Unknown'),
            }
        # create a category for each
        categories = []
        for feature_type, (color, label) in ftype.items():
            symbol = QgsSymbol.defaultSymbol(memory_lyr.geometryType())
            symbol.setColor(QColor(color))
            category = QgsRendererCategory(feature_type, symbol, label)
            categories.append(category)
        # create the renderer and assign it to a layer
        expression = 'ftype'  # field name
        renderer = QgsCategorizedSymbolRenderer(expression, categories)
        memory_lyr.setRenderer(renderer)

        fid = 0
        start_x = 0
        start_y = 0
        ddx = 0  # square grid default
        if self.grid_shape() == self.GRID_DIAMOND:
            ddx = 0.5 * self.dx()
        add_this_one = True
        fts = []
        self.dlg.progress_bar.setMaximum(fcount)
        for f in features:
            self.dlg.progress_bar.setValue(self.dlg.progress_bar.value() + 1)
            if f.geometry().wkbType() == QgsWkbTypes.Polygon or f.geometry().wkbType() == QgsWkbTypes.MultiPolygon or \
              f.geometry().wkbType() == QgsWkbTypes.Polygon25D or f.geometry().wkbType() == QgsWkbTypes.MultiPolygon25D :
                # polygon
                bbox = f.geometry().boundingBox()
                if not self.inside_polygons():
                    # grow the bbox to be sure it is big enough to be able to rotate it
                    if bbox.width() > bbox.height():
                        bbox.setYMaximum(bbox.center().y() + bbox.width() / 2)
                        bbox.setYMinimum(bbox.center().y() - bbox.width() / 2)
                    elif bbox.height() > bbox.width():
                        bbox.setXMaximum(bbox.center().x() + bbox.height() / 2)
                        bbox.setXMinimum(bbox.center().x() - bbox.height() / 2)

                start_x = bbox.xMinimum() + float(self.dx() / 2)
                start_y = bbox.yMinimum() + float(self.dy() / 2)
                for row in range(0, int(math.ceil(bbox.height() / self.dy()))):
                    for column in range(0, int(math.ceil(bbox.width() / self.dx()))):
                        fet = QgsFeature()
                        geom_type = self.create_point_or_trench(start_x, start_y)
                        if self.inside_polygons():
                            add_this_one = f.geometry().contains(geom_type[0])
                        if add_this_one:
                            fet.setGeometry(geom_type[0])
                            #fet.setAttributes([ ''+unicode(fid) ])
                            fet.setAttributes(['', geom_type[1]])
                            fts.append(fet)
                            fid += 1
                        start_x += self.dx()
                    start_x = bbox.xMinimum() + float(self.dx() / 2)
                    if row % 2 == 0:
                        start_x += ddx
                    start_y += self.dy()
            # lines
            elif f.geometry().wkbType() == QgsWkbTypes.LineString:
                if self.feature_type() == self.TRENCH_FEATURES:
                    start_x = 0
                fts.extend(self.handle_line(start_x, start_y, self.dx(), f.geometry()))
            elif f.geometry().wkbType() == QgsWkbTypes.MultiLineString:
                QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate("featuregridcreator", "Sorry, MultiLinestring currently not supported."), QMessageBox.Ok, QMessageBox.Ok)

        provider.addFeatures(fts)
        memory_lyr.updateFields()
        memory_lyr.updateExtents()
        self.iface.mapCanvas().refresh()

        # make layer with new features active and editable
        self.iface.setActiveLayer(memory_lyr)
        # select all features in current memoryLayer
        ids = []
        for f in memory_lyr.getFeatures(QgsFeatureRequest()):
            ids.append(f.id())
        memory_lyr.selectByIds(ids)
        # set to editing
        memory_lyr.startEditing()
        self.layer = memory_lyr
        self.create_action.setChecked(False)

    def handle_line(self, start, end, interval, line_geom):
        """Creating Points or Trenches at coordinates along the line
        """
        length = line_geom.length()
        distance = start
        if 0 < end <= length:
            length = end
        # array with all generated features
        feats = []
        while distance <= length:
            #log.debug('{} {} {}'.format(distance, length, (distance <= length)))
            # Create a new QgsFeature and assign it the new geometry
            feature = QgsFeature()
            feature.setAttributes([''])
            geom_type = self.create_point_or_trench_on_line(line_geom, distance, interval)
            if geom_type[0] is not None:
                feature.setGeometry(geom_type[0])
                feature.setAttributes(['', geom_type[1]])
                feats.append(feature)
            # Increase the distance
            distance += interval
        return feats

    def create_point_or_trench(self, x, y):
        if self.feature_type() == self.TRENCH_FEATURES:
            # trench width and length in centimeters  and div by 2
            w = self.trench_width() / 200
            l = self.trench_length() / 200
            # a polygon with trenches
            return QgsGeometry.fromRect(QgsRectangle(x - l, y - w, x + l, y + w)), self.RESULT_FEATURE_TRENCH_STRAIGHT  # 1 meaning a straight trench
        else:
            # a polygon with points
            return QgsGeometry.fromPointXY(QgsPointXY(x, y)), self.RESULT_FEATURE_POINT  # 0 meaning a point

    def create_point_or_trench_on_line(self, line_geom, distance, interval):
        # Get a point on the line at current distance
        geom = line_geom.interpolate(distance)  # interpolate returns a QgsGeometry
        if self.feature_type() == self.TRENCH_FEATURES:
            # trench width and length in centimeters
            w = self.trench_width() / 100
            l = self.trench_length() / 100
            #x1 = geom.asPoint().x()
            #y1 = geom.asPoint().y()
            # a non rotated trench
            #return QgsGeometry.fromRect(QgsRectangle(x1-l, y1-w, x1+l, y1+w))
            # a trench in the direction of the line
            geom2 = line_geom.interpolate(distance + l)  # interpolate returns a QgsGeometry-point
            vertices = [geom.constGet()]
            # BUT check if there are vertices on this line_geom in between
            # see if there are vertices on the path here...
            if geom2.isNull():   # IF interpolation is AFTER the last vertex: interpolate returns a NULL geom...
                # then make geom2 the last vertex of the line (to have a shorter trench)
                geom2 = QgsGeometry.fromPointXY(line_geom.asPolyline()[-1])
            vertices.append(geom2.constGet())
            line = QgsGeometry.fromPolyline(vertices)
            # checking if length of the generated line is as requested
            # if the difference is more then 1 cm (comparing floats....)
            # we either do NOT add it, or generate rounded caps
            if (int(self.trench_length()) - int(line.length() * 100)) > 1.0:
                # buffer(distance, segments, endcapstyle, joinstyle, mitrelimit)
                # endcap 2 = flat
                # join 1 = round
                #trench = line.buffer(w/2, 4, 1, 1, 1)
                #trench = None
                # print line_geom.touches(geom2)  # true
                # line.closestSegmentWithContext(point, minDistPoint, afterVertex, 0, 0.00000001)
                # returns a segmentWithContext like: (0.0, (104642,490373), 2)
                # being: distance, point, segmentAfter
                segment_context = line_geom.closestSegmentWithContext(geom.asPoint())
                segment_context2 = line_geom.closestSegmentWithContext(geom2.asPoint())
                ii = 1
                for i in range(segment_context[2], segment_context2[2]):
                    #new_vertex = line_geom.vertexAt(segment_context[2])
                    new_vertex = line_geom.vertexAt(i)
                    line.insertVertex(new_vertex.x(), new_vertex.y(), ii)
                    ii += 1
                trench = line.buffer(w / 2, 0, 2, 1, 1)
                # trench = line.buffer(w/2, 1, 1, 1, 1) # 'round' endcap
                return trench, self.RESULT_FEATURE_TRENCH_BENDED_OR_SHORT  # 2 meaning this is not a straight trench (a bended one)
            else:
                # buffer(distance, segments, endcapstyle, joinstyle, mitrelimit)
                # endcap 2 = flat
                # join 1 = round
                trench = line.buffer(w / 2, 0, 2, 1, 1)
                return trench, self.RESULT_FEATURE_TRENCH_STRAIGHT  # 1 meaning a straigh trench
        else:
            # a line with points
            return geom, self.RESULT_FEATURE_POINT  # 0 meaning a point

    def start_labeling(self):
        if not self.label_action.isChecked():  # looks contra intuitive, but action is already checked here!
            self.stop_labeling()
            return
        self.layer = self.iface.activeLayer()
        self.label_action.setChecked(True)
        bail_out = False
        if self.layer is None:
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate(self.SETTINGS_SECTION, self.MSG_NO_ACTIVE_LAYER), QMessageBox.Ok, QMessageBox.Ok)
            bail_out = True
        elif self.layer.type() > 0:  # 0 = vector, 1 = raster
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate(self.SETTINGS_SECTION, self.MSG_NO_VECTOR_LAYER), QMessageBox.Ok, QMessageBox.Ok)
            bail_out = True
        # don't know if this is possible / needed
        elif not self.layer.isValid():
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate(self.SETTINGS_SECTION, self.MSG_NO_VALID_LAYER), QMessageBox.Ok, QMessageBox.Ok)
            bail_out = True
        elif self.layer.selectedFeatureCount() == 0:
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate(self.SETTINGS_SECTION, self.MSG_NO_SELECTED_FEATURES), QMessageBox.Ok, QMessageBox.Ok)
            bail_out = True
        elif not self.layer.isEditable():
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate(self.SETTINGS_SECTION, self.MSG_LAYER_NOT_EDITABLE), QMessageBox.Ok, QMessageBox.Ok)
            bail_out = True
        if bail_out:
            self.label_action.setChecked(False)
            return False

        #self.lbl_dlg.show()
        # Run the dialog event loop
        result = self.lbl_dlg.exec_()
        # See if OK was pressed
        if result == 0:
            self.stop_labeling()
            return
        self.tool = LabelTool(self.iface.mapCanvas(), self.lbl_prefix(), self.lbl_number(), self.lbl_postfix())
        self.tool.set_layer(self.layer)
        self.iface.mapCanvas().setMapTool(self.tool)
        # deactivate this tool when the layer is being deleted!
        if self.layer:
            self.layer.destroyed.connect(self.stop_labeling)
        # deactivate this tool when user selects another layer
        self.iface.currentLayerChanged.connect(self.stop_labeling)

    def stop_labeling(self):
        self.label_action.setChecked(False)
        self.iface.mapCanvas().unsetMapTool(self.tool)


# http://3nids.wordpress.com/2013/02/14/identify-feature-on-map/
class LabelTool(QgsMapTool):

    def __init__(self, canvas, prefix, counter, postfix):
        QgsMapTool.__init__(self, canvas)
        self.canvas = canvas
        self.layer = None
        self.features = []
        self.labeled_ids = []
        self.control_key = False
        self.prefix = prefix
        self.counter = counter
        self.postfix = postfix
        self.cursor = QCursor(QPixmap(["16 16 4 1", "  c None", ". c #000000", "+ c #FFFFFF", "- c #FF0000",
                                       "                ",
                                       "       +.+      ",
                                       "      ++.++     ",
                                       "     +.....+    ",
                                       "    +.     .+   ",
                                       "   +.   .   .+  ",
                                       "  +.    .    .+ ",
                                       " ++.    -    .++",
                                       " ... ..---.. ...",
                                       " ++.    -    .++",
                                       "  +.    .    .+ ",
                                       "   +.   .   .+  ",
                                       "   ++.     .+   ",
                                       "    ++.....+    ",
                                       "      ++.++     ",
                                       "       +.+      "]))

    def label(self, number):
        lbl = str(number)
        if not self.prefix in ['prefix', '']:
            lbl = self.prefix + '_' + lbl
        if not self.postfix in ['postfix', '']:
            lbl += '_' + self.postfix
        return lbl

    def set_layer(self, layer):
        self.layer = layer

    def canvasMoveEvent(self, event):
        #self.canvas.grabKeyboard()
        self.canvas.setFocus()
        if self.layer is None:
            return
        point = self.canvas.getCoordinateTransform().toMapCoordinates(event.x(), event.y())
        # create the search rectangle
        search_radius = QgsMapTool.searchRadiusMU(self.canvas)
        r = QgsRectangle()
        r.setXMinimum(point.x() - search_radius)
        r.setXMaximum(point.x() + search_radius)
        r.setYMinimum(point.y() - search_radius)
        r.setYMaximum(point.y() + search_radius)
        for f in self.layer.getFeatures(
                QgsFeatureRequest().setFilterRect(r).setFlags(QgsFeatureRequest.ExactIntersect)):
            if f.id() in self.layer.selectedFeatureIds():
                label = self.label(self.counter)
                attrs = {0: label}
                self.counter += 1
                self.layer.dataProvider().changeAttributeValues({f.id(): attrs})
                self.layer.deselect(f.id())
                self.labeled_ids.append(f.id())
                self.layer.updateFields()
                return

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.control_key = False

    def keyPressEvent(self, event):
        #remove the last added point when the Ctrl-z key is pressed
        if event.key() == Qt.Key_Control:
            self.control_key = True
        if event.key() == Qt.Key_Z and self.control_key:
            if len(self.labeled_ids) > 0:
                self.counter -= 1
                attrs = {0: ''}
                undo_ft = self.labeled_ids.pop()
                self.layer.dataProvider().changeAttributeValues({undo_ft: attrs})
                selected_ids = self.layer.selectedFeatureIds()
                selected_ids.append(undo_ft)
                self.layer.selectByIds(selected_ids)
                self.layer.updateFields()
                return

    def activate(self):
        self.labeled_ids = []
        if self.layer is None:
            self.deactivate()
            return
        self.canvas.setCursor(self.cursor)
        #self.canvas.setInteractive(True) # not working
        # init
        self.features = []
        for f in self.layer.getFeatures(QgsFeatureRequest()):
            self.features.append(f)        
        # labeling settings    
        # https://gis.stackexchange.com/questions/273266/reading-and-setting-label-settings-in-pyqgis-3
        settings  = QgsPalLayerSettings()
        
        text_format = QgsTextFormat()
        text_format.setFont(QFont("Arial", 10))
        text_format.setSize(12)
        settings.setFormat(text_format)
        
        buffer_settings = QgsTextBufferSettings()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(1)
        buffer_settings.setColor(QColor("white"))
        text_format.setBuffer(buffer_settings)
        
        settings.fieldName = "code"
        #settings.placement = 2
        settings.enabled = True
        settings = QgsVectorLayerSimpleLabeling(settings)
        self.layer.setLabelsEnabled(True)
        self.layer.setLabeling(settings)
        self.layer.triggerRepaint()


    def deactivate(self):
        self.layer = None
