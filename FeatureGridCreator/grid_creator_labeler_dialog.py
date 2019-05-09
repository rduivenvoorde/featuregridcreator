# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FeatureGridCreatorDialog
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

import os

from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt import uic

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'grid_creator_labeler.ui'))


class FeatureGridCreatorLabelerDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(FeatureGridCreatorLabelerDialog, self).__init__(parent)
        self.setupUi(self)
