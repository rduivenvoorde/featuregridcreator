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
from PyQt4.QtCore import *
from PyQt4.QtGui import *
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from grid_creator_dialog import FeatureGridCreatorDialog
import os.path
import math
import sys
from qgis.core import *
from qgis.gui import *

#sys.path.append('/home/richard/apps/pycharm-3.4.1/pycharm-debug.egg')
#import pydevd


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

        self.MSG_BOX_TITLE = 'Grid creator'
        self.SETTINGS_SECTION = 'gridcreator'
        self.GRID_SQUARE = 1
        self.GRID_DIAMOND = 2
        self.POINT_FEATURES = 1
        self.TRENCH_FEATURES = 2

        self.RESULT_FEATURE_POINT = 0
        self.RESULT_FEATURE_TRENCH_STRAIGHT = 1
        self.RESULT_FEATURE_TRENCH_BENDED_OR_SHORT = 2

        # Create the dialog (after translation) and keep reference
        self.dlg = FeatureGridCreatorDialog()
        # init dx and dy values in dialog
        self.dlg.spinBox_dx.setValue(int(self.dx()))
        self.dlg.spinBox_dy.setValue(int(self.dy()))
        self.dlg.spinBox_dx.valueChanged.connect(self.dx_change_slot)
        self.dlg.spinBox_dy.valueChanged.connect(self.dy_change_slot)

        self.dlg.cbx_inside_polygons.toggled.connect(self.inside_polygons_change_slot)
        # set current value from settings
        self.dlg.cbx_inside_polygons.setChecked(self.inside_polygons())

        # init button group with grid shapes
        self.grid_shape_group = QButtonGroup()
        # NOTE: first add to group, THEN assign an id to it
        self.grid_shape_group.addButton(self.dlg.radio_square)
        self.grid_shape_group.setId(self.dlg.radio_square, self.GRID_SQUARE)
        self.grid_shape_group.addButton(self.dlg.radio_diamond)
        self.grid_shape_group.setId(self.dlg.radio_diamond, self.GRID_DIAMOND)
        self.grid_shape_group.buttonReleased.connect(self.grid_shape_change_slot)
        # set current value from settings
        self.grid_shape_group.button(self.grid_shape()).setChecked(True)

        self.feature_type_group = QButtonGroup()
        self.feature_type_group.addButton(self.dlg.radio_points)
        self.feature_type_group.setId(self.dlg.radio_points, self.POINT_FEATURES)
        self.feature_type_group.addButton(self.dlg.radio_trenches)
        self.feature_type_group.setId(self.dlg.radio_trenches, self.TRENCH_FEATURES)
        self.feature_type_group.buttonReleased.connect(self.feature_type_change_slot)
        self.feature_type_group.button(self.feature_type()).setChecked(True)
        self.feature_type_change_slot() # force a signal because above 'setChecked' does not fire a change signal?

        # init dx and dy values in dialog
        self.dlg.spinBox_trench_width.setValue(int(self.trench_width()))
        self.dlg.spinBox_trench_length.setValue(int(self.trench_length()))
        self.dlg.spinBox_trench_width.valueChanged.connect(self.trench_width_change_slot)
        self.dlg.spinBox_trench_length.valueChanged.connect(self.trench_length_change_slot)

        # Declare instance attributes
        self.actions = []
        self.tool = None
        self.layer = None
        self.menu = self.tr(u'&Feature Grid Creator')

        self.toolbar = self.iface.addToolBar(u'FeatureGridCreator')
        self.toolbar.setObjectName(u'FeatureGridCreator')

    def about(self):
        about_str =  "Written by Richard Duivenvoorde (Zuidt)\nEmail - richard@zuidt.nl\n"
        about_str += "Funded by - SOB Research - http://www.sobresearch.nl\n"
        about_str += "Source: https://github.com/rduivenvoorde/featuregridcreator"
        QMessageBox.information(self.iface.mainWindow(), "Feature Grid Creator About", about_str)

    def help(self):
        docs = os.path.join(os.path.dirname(__file__), "help/build/html", "index.html")
        QDesktopServices.openUrl( QUrl("file:" + docs) )

    def getSettingsValue(self, key, default=''):
        if QSettings().contains(self.SETTINGS_SECTION + key):
            key = self.SETTINGS_SECTION + key
            val = QSettings().value(key)
            return val
        else:
            return default

    def setSettingsValue(self, key, value):
        key = self.SETTINGS_SECTION + key
        QSettings().setValue(key, value)

    # getter/setter for dx (saved in settings)
    def dx(self, value=None):
        if value is None:
            return float(self.getSettingsValue('dx', 10))
        else:
            self.setSettingsValue('dx', value)

    # getter/setter for dy (saved in settings)
    def dy(self, value=None):
        if value is None:
            return float(self.getSettingsValue('dy', 10))
        else:
            self.setSettingsValue('dy', value)

    def trench_width(self, value=None):
        if value is None:
            return float(self.getSettingsValue('trench_width', 100))
        else:
            self.setSettingsValue('trench_width', value)

    def trench_length(self, value=None):
        if value is None:
            return float(self.getSettingsValue('trench_height', 100))
        else:
            self.setSettingsValue('trench_height', value)

    def grid_shape(self, value=None):
        if value is None:
            return int(self.getSettingsValue('grid_shape', self.GRID_SQUARE))
        else:
            self.setSettingsValue('grid_shape', value)

    def inside_polygons(self, value=None):
        if value is None:
            return self.getSettingsValue('inside_polygons', True) in ['true', 'True', True]
        else:
            self.setSettingsValue('inside_polygons', value)

    def feature_type(self, value=None):
        if value is None:
            return int(self.getSettingsValue('feature_type', self.POINT_FEATURES))
        else:
            self.setSettingsValue('feature_type', value)

    def dx_change_slot(self, dx):
        self.dx(dx)

    def dy_change_slot(self, dy):
        self.dy(dy)

    def trench_width_change_slot(self, w):
        self.trench_width(w)

    def trench_length_change_slot(self, h):
        self.trench_length(h)

    def grid_shape_change_slot(self, on):
        self.grid_shape(self.grid_shape_group.checkedId())

    def inside_polygons_change_slot(self):
        self.inside_polygons(self.dlg.cbx_inside_polygons.isChecked())

    def feature_type_change_slot(self):
        self.feature_type(self.feature_type_group.checkedId())
        self.dlg.spinBox_trench_length.setEnabled(self.dlg.radio_trenches.isChecked())
        self.dlg.spinBox_trench_width.setEnabled(self.dlg.radio_trenches.isChecked())
        self.dlg.lbl_trench_length.setEnabled(self.dlg.radio_trenches.isChecked())
        self.dlg.lbl_trench_width.setEnabled(self.dlg.radio_trenches.isChecked())

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
        parent=None):
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
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        self.add_action(
            ':/plugins/FeatureGridCreator/icon.png',
            text=self.tr(u'Create a grid of Features'),
            callback=self.run,
            parent=self.iface.mainWindow())

        self.add_action(
            ':/plugins/FeatureGridCreator/icon2.png',
            text=self.tr(u'Label them'),
            callback=self.start_labeling,
            parent=self.iface.mainWindow())

        # help
        self.add_action(
            ':/plugins/FeatureGridCreator/help.png',
            text=self.tr(u'Help'),
            callback=self.help,
            parent=self.iface.mainWindow())

        # about
        self.add_action(
            ':/plugins/FeatureGridCreator/help.png',
            text=self.tr(u'About'),
            callback=self.about,
            parent=self.iface.mainWindow())

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Feature Grid Creator'),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run method that performs all the real work"""
        #pydevd.settrace('localhost', port=5678, stdoutToServer=True, stderrToServer=True)

        # check if current active layer is a polygon layer:
        layer =  self.iface.activeLayer()
        if layer == None:
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate("featuregridcreator", "No active layer found\n" "Please make one (multi)-polygon or (multi)-line layer active by choosing a layer in the legend"), QMessageBox.Ok, QMessageBox.Ok)
            return
        # don't know if this is possible / needed
        if not layer.isValid():
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate("featuregridcreator", "No VALID layer found\n" "Please make one (multi)-polygon or (multi)-line layer active by choosing a layer in the legend"), QMessageBox.Ok, QMessageBox.Ok)
            return
        if (layer.type()>0): # 0 = vector, 1 = raster
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate("featuregridcreator", "Please make one vector layer active by choosing a vector layer in the legend"), QMessageBox.Ok, QMessageBox.Ok)
            return
        geom_type = layer.dataProvider().geometryType()
        if not(geom_type == QGis.WKBPolygon or geom_type == QGis.WKBMultiPolygon or geom_type == QGis.WKBLineString or geom_type == QGis.WKBMultiLineString):
            QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate("featuregridcreator", "Please make one (multi)-polygon or (multi)-line layer layer active by choosing a layer in the legend"), QMessageBox.Ok, QMessageBox.Ok)
            return

        # disable some dialog parts if geometries in the layer are lines
        geoms_are_polygons = (geom_type == QGis.WKBPolygon or geom_type == QGis.WKBMultiPolygon)
        self.dlg.box_dy.setEnabled(geoms_are_polygons)
        self.dlg.box_grid_shape.setEnabled(geoms_are_polygons)
        self.dlg.box_inside_polygons.setEnabled(geoms_are_polygons)

        # show the dialog
        self.dlg.show()

        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result == False:
            return

        activeLayer=self.iface.mapCanvas().currentLayer()
        features = None

        if len(activeLayer.selectedFeatures()) < 1:
            features = activeLayer.getFeatures()
        else:
            features = activeLayer.selectedFeatures()

        # give the memory layer the same CRS as the source layer
        crs=activeLayer.crs()

        if self.feature_type()==self.TRENCH_FEATURES:
            memLayer = QgsVectorLayer("Polygon?crs=epsg:"+str(crs.postgisSrid())+"&index=yes", "grid polygons", "memory")
        else:
            memLayer = QgsVectorLayer("Point?crs=epsg:"+str(crs.postgisSrid())+"&index=yes", "grid points", "memory")

        QgsMapLayerRegistry.instance().addMapLayer(memLayer)

        provider = memLayer.dataProvider()
        provider.addAttributes( [
                        QgsField("code", QVariant.String),
                        QgsField("ftype", QVariant.Int),
                        ] )

        # http://snorf.net/blog/2014/03/04/symbology-of-vector-layers-in-qgis-python-plugins/
        # Categorized symbol renderer for different type of grid features: points, straight trench and bended or stort trench
        # define a lookup: value -> (color, label)
        ftype = {
            '0': ('#00f', 'point'),
            '1': ('#00f', 'trench straight'),
            '2': ('#f00', 'trench bend or short'),
            '': ('#000', 'Unknown'),
        }
        # create a category for each item in animals
        categories = []
        for feature_type, (color, label) in ftype.items():
            symbol = QgsSymbolV2.defaultSymbol(memLayer.geometryType())
            symbol.setColor(QColor(color))
            category = QgsRendererCategoryV2(feature_type, symbol, label)
            categories.append(category)
        # create the renderer and assign it to a layer
        expression = 'ftype' # field name
        renderer = QgsCategorizedSymbolRendererV2(expression, categories)
        memLayer.setRendererV2(renderer)

        fid = 0
        start_x = 0
        start_y = 0
        ddx = 0  # square grid default
        if self.grid_shape()==self.GRID_DIAMOND:
            ddx = 0.5 * self.dx()
        bbox = None
        add_this_one = True
        fts = []
        for f in features:
            if f.geometry().wkbType() == QGis.WKBPolygon or f.geometry().wkbType() == QGis.WKBMultiPolygon:

                # polygon
                bbox= f.geometry().boundingBox()
                if not self.inside_polygons():
                    # grow the bbox to be sure it is big enough to be able to rotate it
                    if bbox.width() > bbox.height():
                        bbox.setYMaximum(bbox.center().y()+bbox.width()/2)
                        bbox.setYMinimum(bbox.center().y()-bbox.width()/2)
                    elif bbox.height() > bbox.width():
                        bbox.setXMaximum(bbox.center().x()+bbox.height()/2)
                        bbox.setXMinimum(bbox.center().x()-bbox.height()/2)

                start_x = bbox.xMinimum() + int(self.dx()/2)
                start_y = bbox.yMinimum() + int(self.dy()/2)
                for row in range(0, int(math.ceil(bbox.height()/self.dy()))):
                    for column in range(0, int(math.ceil(bbox.width()/self.dx()))):
                        fet = QgsFeature()
                        geom_type = self.create_point_or_trench(start_x, start_y)
                        if self.inside_polygons():
                            add_this_one = f.geometry().contains(geom_type[0])
                        if add_this_one:
                            fet.setGeometry(geom_type[0])
                            #fet.setAttributes([ ''+str(fid) ])
                            fet.setAttributes(['', geom_type[1]])
                            fts.append(fet)
                            fid += 1
                        start_x += self.dx()
                    start_x = bbox.xMinimum() + int(self.dx()/2)
                    if row%2 == 0:
                        start_x += ddx
                    start_y += self.dy()
            # lines
            elif f.geometry().wkbType() == QGis.WKBLineString:
                if self.feature_type() == self.TRENCH_FEATURES:
                    start_x = 0
                fts.extend(self.handle_line(start_x, start_y, self.dx(), f.geometry()))
            elif f.geometry().wkbType() == QGis.WKBMultiLineString:
                QMessageBox.warning(self.iface.mainWindow(), self.MSG_BOX_TITLE, QCoreApplication.translate("featuregridcreator", "Sorry, MultiLinestring currently not supported."), QMessageBox.Ok, QMessageBox.Ok)

        provider.addFeatures(fts)
        memLayer.updateFields()
        memLayer.updateExtents()
        self.iface.mapCanvas().refresh()

        # make layer with new features active and editable
        self.iface.setActiveLayer(memLayer)
        # select all features in current memoryLayer
        ids = []
        for f in memLayer.getFeatures(QgsFeatureRequest()):
            ids.append(f.id())
        memLayer.setSelectedFeatures(ids)
        # set to editing
        memLayer.startEditing()
        self.layer = memLayer

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
            # trench width and length in centimeters
            w = self.trench_width()/100
            l = self.trench_length()/100
            # a polygon with trenches
            return (QgsGeometry.fromRect(QgsRectangle(x-l, y-w, x+l, y+w)), self.RESULT_FEATURE_TRENCH_STRAIGHT) # 1 meaning a straight trench
        else:
            # a polygon with points
            return (QgsGeometry.fromPoint(QgsPoint(x, y)), self.RESULT_FEATURE_POINT) # 0 meaning a point

    def create_point_or_trench_on_line(self, line_geom, distance, interval):
        # Get a point on the line at current distance
        geom = line_geom.interpolate(distance)  # interpolate returns a QgsGeometry
        if self.feature_type() == self.TRENCH_FEATURES:
            # trench width and length in centimeters
            w = self.trench_width()/100
            l = self.trench_length()/100
            x1 = geom.asPoint().x()
            y1 = geom.asPoint().y()
            # a non rotated trench
            #return QgsGeometry.fromRect(QgsRectangle(x1-l, y1-w, x1+l, y1+w))
            # a trench in the direction of the line
            geom2 = line_geom.interpolate(distance + l)  # interpolate returns a QgsGeometry-point
            vertices = [geom.asPoint()]
            # BUT check if there are vertices on this line_geom in between
            # see if there are vertices on the path here...
            vertices.append(geom2.asPoint())
            line = QgsGeometry.fromPolyline(vertices)
            # checking if length of the generated line is as requested
            # if the difference is more then 1 cm (comparing floats....)
            # we either do NOT add it, or generate rounded caps
            if (int(self.trench_length()) - int(line.length()*100)) > 1.0:
                # buffer(distance, segments, endcapstyle, joinstyle, mitrelimit)
                # endcap 2 = flat
                # join 1 = round
                #trench = line.buffer(w/2, 4, 1, 1, 1)
                #trench = None

                print "******************************"
                print "******************************"
                print line_geom.exportToWkt()
                # print line_geom.touches(geom2)  # true
                # line.closestSegmentWithContext(point, minDistPoint, afterVertex, 0, 0.00000001)
                # returns a segmentWithContext like: (0.0, (104642,490373), 2)
                # being: distance, point, segmentAfter
                segment_context = line_geom.closestSegmentWithContext(geom.asPoint())
                print segment_context[2]
                segment_context2 = line_geom.closestSegmentWithContext(geom2.asPoint())
                print segment_context2[2]
                print line.exportToWkt()
                ii = 1
                for i in range(segment_context[2], segment_context2[2]):
                    print "&&&&&&&&&&&&&&&&&&&&&&&&&&&"
                    #new_vertex = line_geom.vertexAt(segment_context[2])
                    new_vertex = line_geom.vertexAt(i)
                    print new_vertex
                    line.insertVertex(new_vertex.x(), new_vertex.y(), ii)
                    ii += 1
                    print line.exportToWkt()
                trench = line.buffer(w/2, 0, 2, 1, 1)
                # trench = line.buffer(w/2, 1, 1, 1, 1) # 'round' endcap
                return (trench, self.RESULT_FEATURE_TRENCH_BENDED_OR_SHORT) # 2 meaning this is not a straight trench (a bended one)
            else:
                # buffer(distance, segments, endcapstyle, joinstyle, mitrelimit)
                # endcap 2 = flat
                # join 1 = round
                trench = line.buffer(w/2, 0, 2, 1, 1)
                return (trench, self.RESULT_FEATURE_TRENCH_STRAIGHT) # 1 meaning a straigh trench
        else:
            # a line with points
            return (geom, self.RESULT_FEATURE_POINT) # 0 meaning a point

    def start_labeling(self):
        #tool = PointHoverTool2(self.iface.mapCanvas(), self.layer)
        #import pdb
        #pyqtRemoveInputHook()
        #pdb.set_trace()
        #self.tool = tool
        #self.iface.mapCanvas().setMapTool(self.tool)
        tool = LabelTool(self.iface.mapCanvas())
        self.tool = tool
        self.tool.set_layer(self.layer)
        self.iface.mapCanvas().setMapTool(self.tool)
        # deactivate this tool when the layer is being deleted!
        self.layer.layerDeleted.connect(self.stop_labeling)
        # deactivate this tool when user selects another layer
        self.iface.currentLayerChanged.connect(self.stop_labeling)

    def stop_labeling(self):
        self.iface.mapCanvas().unsetMapTool(self.tool)


# http://3nids.wordpress.com/2013/02/14/identify-feature-on-map/
class LabelTool(QgsMapTool):

    def __init__(self, canvas):
        self.canvas = canvas
        self.layer = None
        self.features = []
        self.counter = 0
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
        QgsMapTool.__init__(self, canvas)

    def set_layer(self, layer):
        self.layer = layer

    def canvasMoveEvent(self, event):
    #def canvasReleaseEvent(self, event):
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
            if f.id() in self.layer.selectedFeaturesIds():
                self.counter += 1
                attrs = {0: self.counter}
                self.layer.dataProvider().changeAttributeValues({f.id(): attrs})
                self.layer.updateFields()
                self.layer.deselect(f.id())
                return

    def activate(self):
        self.canvas.setCursor(self.cursor)

        palyr = QgsPalLayerSettings()
        palyr.readFromLayer(self.layer)
        palyr.enabled = True
        palyr.fieldName = 'code'
        palyr.placement = QgsPalLayerSettings.AroundPoint
        palyr.setDataDefinedProperty(QgsPalLayerSettings.Size, True, True, '10', '')
        palyr.writeToLayer(self.layer)

        self.features = []
        self.counter = 0
        for f in self.layer.getFeatures(QgsFeatureRequest()):
            self.features.append(f)

    def deactivate(self):
        self.layer = None
