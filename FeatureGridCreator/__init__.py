# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FeatureGridCreator
                                 A QGIS plugin
 Creates a grid of features 
                             -------------------
        begin                : 2014-08-27
        copyright            : (C) 2014 by Zuidt
        email                : richard@zuidt.nl
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""

import os
import site

site.addsitedir(os.path.abspath('%s' % os.path.dirname(__file__)))

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load FeatureGridCreator class from file FeatureGridCreator.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .grid_creator import FeatureGridCreator
    return FeatureGridCreator(iface)
