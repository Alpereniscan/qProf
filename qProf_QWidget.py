# -*- coding: utf-8 -*-


import os
from math import isnan, sin, cos, asin, radians, degrees, floor, ceil
import numpy as np

import copy

import xml.dom.minidom

import unicodedata

from osgeo import ogr

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from matplotlib import rcParams

import webbrowser

from qgis.core import QgsPoint, QgsRaster, QgsMapLayerRegistry, QgsMapLayer, QGis, QgsGeometry
from qgis.gui import QgsRubberBand

from geosurf.qt_utils import lastUsedDir, setLastUsedDir

from geosurf.spatial import Point2D, MultiLine2D, Line2D
from geosurf.spatial import Point3D, Segment3D, MultiLine3D, Line3D                           
from geosurf.spatial import merge_lines, GeolPlane, GeolAxis, CartesianPlane, ParamLine
from geosurf.spatial import xytuple_list_to_Line2D, xytuple_list2_to_MultiLine2D
                            
from geosurf.geo_io import QGisRasterParameters
from geosurf.profile import Profile_Elements, TopoLine3D, DEMParams
from geosurf.geodetic import TrackPointGPX
from geosurf.intersections import map_struct_pts_on_section, calculate_distance_with_sign
from geosurf.errors import VectorInputException, GPXIOException, VectorIOException
           
from geosurf.qgs_tools import loaded_line_layers, loaded_point_layers, loaded_polygon_layers, pt_geoms_attrs, \
                            raster_qgis_params, loaded_monoband_raster_layers, \
                            line_geoms_with_id, qgs_point_2d, project_qgs_point, vect_attrs, \
                            line_geoms_attrs, field_values, MapDigitizeTool

from geosurf.string_utils import clean_string
from geosurf.utils import to_float

from geosurf.qt_utils import new_file_path, old_file_path
            
from mpl.mpl_widget import MplWidget, plot_line, plot_filled_line
from mpl.utils import valid_intervals
from projections import line2d_change_crs

import resources


_plugin_name_ = "qProf"

        
class qprof_QWidget(QWidget):
    
    colors = ['orange', 'green', 'red', 'grey', 'brown', 'yellow', 'magenta', 'black', 'blue', 'white', 'cyan', 'chartreuse']

    colors_addit = ["darkseagreen", "darkgoldenrod","darkviolet", "hotpink", "powderblue", "yellowgreen", "palevioletred", 
                  "seagreen", "darkturquoise", "beige", "darkkhaki", "red", "yellow","magenta","blue","cyan","chartreuse"] 

    def __init__(self, canvas):

        super(qprof_QWidget, self).__init__() 
        self.mapcanvas = canvas
        self.initialize_parameters()      
        self.setup_gui()
           

    def initialize_parameters(self):

        self.selected_dems = []
        self.selected_dem_colors = []
        self.selected_dem_parameters = []

        self.sample_distance = None
        self.profile_windows = []
        self.cross_section_windows = [] 
        self.source_profile = None
        self.current_directory = os.path.dirname(__file__) 
        self.profiles = None
        self.DEM_data_export = None 
        self.profile_GPX = None

        self.plane_attitudes_colors = []
        self.curve_colors = [] 
        

    def info(self, msg):
        
        QMessageBox.information(self,  _plugin_name_, msg)
        
        
    def warn(self, msg):
    
        QMessageBox.warning(self,  _plugin_name_, msg)
          
                      
    def setup_gui(self): 

        self.dialog_layout = QVBoxLayout()
        self.main_widget = QTabWidget()        
        self.main_widget.addTab(self.setup_topoprofile_tab(), "Topography")         
        self.main_widget.addTab(self.setup_project_section_tab(), "Projections")
        self.main_widget.addTab(self.setup_intersect_section_tab(), "Intersections")
        self.main_widget.addTab(self.setup_export_section_tab(), "Export")
        self.main_widget.addTab(self.setup_about_tab(), "Help/About")
        
        self.prj_input_line_comboBox.currentIndexChanged[int].connect(self.update_linepoly_layers_boxes)
        self.inters_input_line_comboBox.currentIndexChanged[int].connect(self.update_linepoly_layers_boxes)
        self.inters_input_polygon_comboBox.currentIndexChanged[int].connect(self.update_linepoly_layers_boxes)
               
        self.refresh_struct_line_lyr_combobox()
        self.refresh_struct_polygon_lyr_combobox()
        
        QgsMapLayerRegistry.instance().layerWasAdded.connect(self.refresh_struct_point_lyr_combobox)        
        QgsMapLayerRegistry.instance().layerWasAdded.connect(self.refresh_struct_line_lyr_combobox)
        QgsMapLayerRegistry.instance().layerWasAdded.connect(self.refresh_struct_polygon_lyr_combobox)
        
        QgsMapLayerRegistry.instance().layerRemoved.connect(self.refresh_struct_point_lyr_combobox)                
        QgsMapLayerRegistry.instance().layerRemoved.connect(self.refresh_struct_line_lyr_combobox)
        QgsMapLayerRegistry.instance().layerRemoved.connect(self.refresh_struct_polygon_lyr_combobox)
                       
        self.dialog_layout.addWidget(self.main_widget)                             
        self.setLayout(self.dialog_layout)            
        self.adjustSize()               
        self.setWindowTitle('qProf')        
                
  
    def setup_topoprofile_tab(self):  

        profile_widget = QWidget() 
        profile_layout = QVBoxLayout()
 
        profile_toolbox = QToolBox()        
        
        ## input section
        
        profileDEM_QWidget = QWidget()
        profileDEM_Layout = QVBoxLayout()        

        ## Input from DEM
        
        inputDEM_QGroupBox = QGroupBox(profileDEM_QWidget)
        inputDEM_QGroupBox.setTitle("Input DEMs")
        
        inputDEM_Layout = QGridLayout()

        self.DefineSourceDEMs_pushbutton = QPushButton(self.tr("Define source DEMs")) 
        self.DefineSourceDEMs_pushbutton.clicked.connect(self.define_source_DEMs)
            
        inputDEM_Layout.addWidget(self.DefineSourceDEMs_pushbutton, 0, 0, 1, 3) 

        inputDEM_QGroupBox.setLayout(inputDEM_Layout)
        
        profileDEM_Layout.addWidget(inputDEM_QGroupBox)
                
        ## Line layer input
        
        inputLine_QGroupBox = QGroupBox(profileDEM_QWidget)
        inputLine_QGroupBox.setTitle("Input line")
        
        inputLine_Layout = QGridLayout()
        
        inputLine_Layout.addWidget(QLabel("Input from"), 0, 0, 1, 1)
 
        self.LoadLineLayer_checkbox = QRadioButton(self.tr("line layer"))
        self.LoadLineLayer_checkbox.setChecked(True)
        inputLine_Layout.addWidget(self.LoadLineLayer_checkbox, 0, 1, 1, 1)   
               
        self.DigitizeLine_checkbox = QRadioButton(self.tr("digitization"))
        inputLine_Layout.addWidget(self.DigitizeLine_checkbox, 0, 2, 1, 1)
        
        self.PointListforLine_checkbox = QRadioButton(self.tr("point list"))
        inputLine_Layout.addWidget(self.PointListforLine_checkbox, 0, 3, 1, 1)
        
        self.DefineLine_pushbutton = QPushButton(self.tr("Define profile line"))  
        self.DefineLine_pushbutton.clicked.connect(self.define_line) 
        inputLine_Layout.addWidget(self.DefineLine_pushbutton, 1, 0, 1, 4)
                        
        inputLine_QGroupBox.setLayout(inputLine_Layout)
        
        profileDEM_Layout.addWidget(inputLine_QGroupBox)
                  

        ## Profile statistics

        prof_stats_QGroupBox = QGroupBox(profileDEM_QWidget)
        prof_stats_QGroupBox.setTitle("Profile statistics")

        prof_stats_Layout = QGridLayout()

        self.profile_stats_pushbutton = QPushButton(self.tr("Calculate profile statistics"))
        self.profile_stats_pushbutton.clicked.connect(self.calculate_statistics)

        prof_stats_Layout.addWidget(self.profile_stats_pushbutton, 0, 0, 1, 3)

        prof_stats_QGroupBox.setLayout(prof_stats_Layout)

        profileDEM_Layout.addWidget(prof_stats_QGroupBox)

        
        ## create profile section
        
        plotDEM_QGroupBox = QGroupBox(profileDEM_QWidget)
        plotDEM_QGroupBox.setTitle('Plot topographic profile')
        
        plotDEM_Layout = QGridLayout()                

        # profile options
        
        # trace sampling distance                 
        plotDEM_Layout.addWidget(QLabel(self.tr("Line densify distance")), 0, 0, 1, 1)         
        self.profile_densify_distance_lineedit = QLineEdit()
        plotDEM_Layout.addWidget(self.profile_densify_distance_lineedit, 0, 1, 1, 1)

        plotDEM_Layout.addWidget(QLabel(self.tr("Vertical exaggeration")), 1, 0, 1, 1)
        self.DEM_exageration_ratio_Qlineedit = QLineEdit()
        self.DEM_exageration_ratio_Qlineedit.setText("1")
        plotDEM_Layout.addWidget(self.DEM_exageration_ratio_Qlineedit, 1, 1, 1, 1)

        plotDEM_Layout.addWidget(QLabel(self.tr("Plot z min value")), 0, 2, 1, 1)
        self.plot_min_value_QLineedit = QLineEdit()
        self.plot_min_value_QLineedit.setText("[automatic]")
        plotDEM_Layout.addWidget(self.plot_min_value_QLineedit, 0, 3, 1, 1)

        plotDEM_Layout.addWidget(QLabel(self.tr("Plot z max value")), 1, 2, 1, 1)
        self.plot_max_value_QLineedit = QLineEdit()
        self.plot_max_value_QLineedit.setText("[automatic]")
        plotDEM_Layout.addWidget(self.plot_max_value_QLineedit, 1, 3, 1, 1)
                        
        self.DEM_plot_height_checkbox = QCheckBox(self.tr("Height"))
        self.DEM_plot_height_checkbox.setChecked(True) 
        plotDEM_Layout.addWidget(self.DEM_plot_height_checkbox, 2, 0, 1, 1)

        self.DEM_plot_height_filled_checkbox = QCheckBox(self.tr("(filled)"))
        plotDEM_Layout.addWidget(self.DEM_plot_height_filled_checkbox, 2, 3, 1, 1)

        self.DEM_plot_slope_checkbox = QCheckBox(self.tr("Slope (degrees)"))
        plotDEM_Layout.addWidget(self.DEM_plot_slope_checkbox, 3, 0, 1, 1)
       
        self.DEM_plot_slope_absolute_qradiobutton = QRadioButton(self.tr("absolute"))
        self.DEM_plot_slope_absolute_qradiobutton.setChecked(True);
        plotDEM_Layout.addWidget(self.DEM_plot_slope_absolute_qradiobutton, 3, 1, 1, 1)

        self.DEM_plot_slope_directional_qradiobutton = QRadioButton(self.tr("directional"))
        plotDEM_Layout.addWidget(self.DEM_plot_slope_directional_qradiobutton, 3, 2, 1, 1)
                       
        self.DEM_plot_slope_filled_checkbox = QCheckBox(self.tr("(filled)"))
        plotDEM_Layout.addWidget(self.DEM_plot_slope_filled_checkbox, 3, 3, 1, 1)
 
        self.swap_profile_horiz_checkbox = QCheckBox(self.tr("Invert profile line orientation"))
        plotDEM_Layout.addWidget(self.swap_profile_horiz_checkbox, 4, 0, 1, 2)

        self.swap_xaxis_checkbox = QCheckBox(self.tr("Flip x-axis direction"))
        plotDEM_Layout.addWidget(self.swap_xaxis_checkbox, 4, 2, 1, 2)

                                       
        self.CreateProfDEM_pushbutton = QPushButton(self.tr("Create profile")) 
        self.CreateProfDEM_pushbutton.clicked.connect(self.create_topo_profiles_from_DEMs)
                       
        plotDEM_Layout.addWidget(self.CreateProfDEM_pushbutton, 5, 0, 1, 4)
     
        plotDEM_QGroupBox.setLayout(plotDEM_Layout)

        profileDEM_Layout.addWidget(plotDEM_QGroupBox)


        #########
        
               
        profileDEM_QWidget.setLayout(profileDEM_Layout)
                
        profile_toolbox.addItem (profileDEM_QWidget, "Topographic profiles from DEMs") 
        
                        
        ## Input from GPX
        
        profileGPX_QWidget = QWidget()
        profileGPX_Layout = QVBoxLayout()        

        ## Input from DEM
        
        inputGPX_QGroupBox = QGroupBox(profileDEM_QWidget)
        inputGPX_QGroupBox.setTitle('Input')
        
        inputGPX_Layout = QGridLayout()
                        
        inputGPX_Layout.addWidget(QLabel(self.tr("Input GPX file with track points:")), 0, 0, 1, 3)       

        self.input_gpx_lineEdit = QLineEdit()
        self.input_gpx_lineEdit.setPlaceholderText("my_track.gpx")
        inputGPX_Layout.addWidget(self.input_gpx_lineEdit, 1, 0, 1, 2)
        
        self.input_gpx_QPButt = QPushButton("...")
        self.input_gpx_QPButt.clicked.connect(self.select_input_gpxFile)
        inputGPX_Layout.addWidget(self.input_gpx_QPButt, 1, 2, 1, 1)
               
        inputGPX_QGroupBox.setLayout(inputGPX_Layout)
        
        profileGPX_Layout.addWidget(inputGPX_QGroupBox)
        
        # Plot section

        plotGPX_QGroupBox = QGroupBox(profileGPX_QWidget)
        plotGPX_QGroupBox.setTitle('Plot')
        
        plotGPX_Layout = QGridLayout()
                
        plotGPX_Layout.addWidget(QLabel(self.tr("Plot:")), 2, 0, 1, 1)  
        
        self.GPX_plot_height_checkbox = QCheckBox(self.tr("height"))
        self.GPX_plot_height_checkbox.setChecked(True) 
        plotGPX_Layout.addWidget(self.GPX_plot_height_checkbox, 2, 1, 1, 1)  

        self.GPX_plot_slope_checkbox = QCheckBox(self.tr("slope"))
        self.GPX_plot_slope_checkbox.setChecked(False)
        plotGPX_Layout.addWidget(self.GPX_plot_slope_checkbox, 2, 2, 1, 1) 
        
        self.CalcProf3D_pushbutton = QPushButton(self.tr("Create profile")) 
        self.CalcProf3D_pushbutton.clicked.connect(self.create_topo_profile_from_GPX)
             
        plotGPX_Layout.addWidget(self.CalcProf3D_pushbutton, 3, 0, 1, 3)                       

        plotGPX_QGroupBox.setLayout(plotGPX_Layout)
        
        profileGPX_Layout.addWidget(plotGPX_QGroupBox)
        
        ##### 
               
        profileGPX_QWidget.setLayout(profileGPX_Layout)                
        profile_toolbox.addItem (profileGPX_QWidget, "Topographic profiles from GPXs") 
                 
        # widget final setup 
                       
        profile_layout.addWidget(profile_toolbox)
        profile_widget.setLayout(profile_layout) 
        
        return profile_widget     
        

    def setup_project_section_tab(self):
        
        section_project_QWidget = QWidget()  
        section_project_layout = QVBoxLayout() 

        project_toolbox = QToolBox()
        
        ### Point project toolbox
        
        xs_point_proj_QWidget = QWidget()
        xs_point_proj_Layout = QVBoxLayout()         

        ## input section
        
        xs_input_point_proj_QGroupBox = QGroupBox(xs_point_proj_QWidget)
        xs_input_point_proj_QGroupBox.setTitle('Input')
        
        xs_input_point_proj_Layout = QGridLayout()
                
        # input point geological layer
                
        xs_input_point_proj_Layout.addWidget(QLabel("Layer: "), 0, 0, 1, 1)
        self.prj_struct_point_comboBox = QComboBox()
        self.prj_struct_point_comboBox.currentIndexChanged[int].connect(self.update_point_layers_boxes)
               
        xs_input_point_proj_Layout.addWidget(self.prj_struct_point_comboBox, 0, 1, 1, 6)        
        self.refresh_struct_point_lyr_combobox()
        
        xs_input_point_proj_Layout.addWidget(QLabel("Fields:"), 1, 0, 1, 1)
                   
        xs_input_point_proj_Layout.addWidget(QLabel("Id"), 1, 1, 1, 1)
        self.proj_point_id_fld_comboBox = QComboBox()
        xs_input_point_proj_Layout.addWidget(self.proj_point_id_fld_comboBox, 1, 2, 1, 1)
                     
        xs_input_point_proj_Layout.addWidget(QLabel("Dip dir."), 1, 3, 1, 1)
        self.proj_point_dipdir_fld_comboBox = QComboBox()
        xs_input_point_proj_Layout.addWidget(self.proj_point_dipdir_fld_comboBox, 1, 4, 1, 1) 
                
        xs_input_point_proj_Layout.addWidget(QLabel("Dip ang. field"), 1, 5, 1, 1)
        self.proj_point_dipang_fld_comboBox = QComboBox()
        xs_input_point_proj_Layout.addWidget(self.proj_point_dipang_fld_comboBox, 1, 6, 1, 1)        
        
        xs_input_point_proj_QGroupBox.setLayout(xs_input_point_proj_Layout)        
        xs_point_proj_Layout.addWidget(xs_input_point_proj_QGroupBox)        


        ## interpolation method
        
        xs_method_point_proj_QGroupBox = QGroupBox(xs_point_proj_QWidget)
        xs_method_point_proj_QGroupBox.setTitle('Project along')
        
        xs_method_point_proj_Layout = QGridLayout()
        
        self.nearest_point_proj_choice = QRadioButton("nearest intersection")
        xs_method_point_proj_Layout.addWidget(self.nearest_point_proj_choice, 0, 0, 1, 3)        

        self.axis_common_point_proj_choice = QRadioButton("axis with trend")
        xs_method_point_proj_Layout.addWidget(self.axis_common_point_proj_choice, 1, 0, 1, 1)
        
        self.common_axis_point_trend_SpinBox = QDoubleSpinBox()
        self.common_axis_point_trend_SpinBox.setMinimum(0.0)
        self.common_axis_point_trend_SpinBox.setMaximum(359.9) 
        self.common_axis_point_trend_SpinBox.setDecimals(1)
        xs_method_point_proj_Layout.addWidget(self.common_axis_point_trend_SpinBox, 1, 1, 1, 1)

        xs_method_point_proj_Layout.addWidget(QLabel("and plunge"), 1, 2, 1, 1)
                
        self.common_axis_point_plunge_SpinBox = QDoubleSpinBox()
        self.common_axis_point_plunge_SpinBox.setMinimum(0.0)
        self.common_axis_point_plunge_SpinBox.setMaximum(89.9) 
        self.common_axis_point_plunge_SpinBox.setDecimals(1)
        xs_method_point_proj_Layout.addWidget(self.common_axis_point_plunge_SpinBox, 1, 3, 1, 1)                       

        self.axis_individual_point_proj_choice = QRadioButton("axes from trend field")
        xs_method_point_proj_Layout.addWidget(self.axis_individual_point_proj_choice, 2, 0, 1, 1)

        self.proj_point_indivax_trend_fld_comboBox = QComboBox()
        xs_method_point_proj_Layout.addWidget(self.proj_point_indivax_trend_fld_comboBox, 2, 1, 1, 1) 

        xs_method_point_proj_Layout.addWidget(QLabel("and plunge field"), 2, 2, 1, 1)
        self.proj_point_indivax_plunge_fld_comboBox = QComboBox()
        xs_method_point_proj_Layout.addWidget(self.proj_point_indivax_plunge_fld_comboBox, 2, 3, 1, 1)
       
        xs_method_point_proj_QGroupBox.setLayout(xs_method_point_proj_Layout)        
        xs_point_proj_Layout.addWidget(xs_method_point_proj_QGroupBox)        

        
        ## Plot groupbox
                
        xs_plot_proj_QGroupBox = QGroupBox(xs_point_proj_QWidget)
        xs_plot_proj_QGroupBox.setTitle('Plot geological attitudes')
        
        xs_plot_proj_Layout = QGridLayout()      
        
        xs_plot_proj_Layout.addWidget(QLabel("Labels"), 0, 0, 1, 1)

        self.plot_prj_add_trendplunge_label = QCheckBox("dip dir/plunge")
        xs_plot_proj_Layout.addWidget(self.plot_prj_add_trendplunge_label, 0, 1, 1, 1)  
        
        self.plot_prj_add_pt_id_label = QCheckBox("id")
        xs_plot_proj_Layout.addWidget(self.plot_prj_add_pt_id_label, 0, 2, 1, 1) 

        xs_plot_proj_Layout.addWidget(QLabel("Color"), 0, 3, 1, 1)
        self.proj_point_color_comboBox = QComboBox()
        self.proj_point_color_comboBox.addItems(qprof_QWidget.colors)
        xs_plot_proj_Layout.addWidget(self.proj_point_color_comboBox, 0, 4, 1, 1)  
        
        self.project_point_pushbutton = QPushButton(self.tr("Plot"))
        self.project_point_pushbutton.clicked.connect(self.create_struct_point_projection)        
        xs_plot_proj_Layout.addWidget(self.project_point_pushbutton, 1, 0, 1, 3)

        self.reset_point_pushbutton = QPushButton(self.tr("Reset plot"))
        self.reset_point_pushbutton.clicked.connect(self.reset_struct_point_projection)

        xs_plot_proj_Layout.addWidget(self.reset_point_pushbutton, 1, 3, 1, 2)
                                                        
        xs_plot_proj_QGroupBox.setLayout(xs_plot_proj_Layout)        
        xs_point_proj_Layout.addWidget(xs_plot_proj_QGroupBox)                

        self.flds_prj_point_comboBoxes = [self.proj_point_id_fld_comboBox,
                                          self.proj_point_dipdir_fld_comboBox,
                                          self.proj_point_dipang_fld_comboBox,
                                          self.proj_point_indivax_trend_fld_comboBox,
                                          self.proj_point_indivax_plunge_fld_comboBox]
                                     
        
        ##
        
                
        xs_point_proj_QWidget.setLayout(xs_point_proj_Layout)                
        project_toolbox.addItem (xs_point_proj_QWidget, "Geological attitudes") 
                
        ## END Point project toolbox
        
        ### Line project toolbox
        
        xs_line_proj_QWidget = QWidget()
        xs_line_proj_Layout = QVBoxLayout()         

        ## input section
        
        xs_input_line_proj_QGroupBox = QGroupBox(xs_line_proj_QWidget)
        xs_input_line_proj_QGroupBox.setTitle('Input')
        
        xs_input_line_proj_Layout = QGridLayout()
                
        # input geological layer
                
        xs_input_line_proj_Layout.addWidget(QLabel("Layer"), 0, 0, 1, 1)
        self.prj_input_line_comboBox = QComboBox()
               
        xs_input_line_proj_Layout.addWidget(self.prj_input_line_comboBox, 0, 1, 1, 3)        
                           
        xs_input_line_proj_Layout.addWidget(QLabel("Id field"), 1, 0, 1, 1)
        self.id_fld_line_prj_comboBox = QComboBox()
        xs_input_line_proj_Layout.addWidget(self.id_fld_line_prj_comboBox, 1, 1, 1, 3)

        xs_input_line_proj_Layout.addWidget(QLabel("Line densify distance"), 2, 0, 1, 1)         
        self.project_line_densify_distance_lineedit = QLineEdit()
        xs_input_line_proj_Layout.addWidget(self.project_line_densify_distance_lineedit, 2, 1, 1, 3)
        
        self.flds_prj_line_comboBoxes = [self.id_fld_line_prj_comboBox]

        xs_input_line_proj_QGroupBox.setLayout(xs_input_line_proj_Layout)        
        xs_line_proj_Layout.addWidget(xs_input_line_proj_QGroupBox)       

        ## interpolation method
        
        xs_method_line_proj_QGroupBox = QGroupBox(xs_line_proj_QWidget)
        xs_method_line_proj_QGroupBox.setTitle('Project')
        
        xs_method_line_proj_Layout = QGridLayout()

        xs_method_line_proj_Layout.addWidget(QLabel("Projection axis:"), 0, 0, 1, 1)
                
        xs_method_line_proj_Layout.addWidget(QLabel("trend"), 0, 1, 1, 1)
        
        self.common_axis_line_trend_SpinBox = QDoubleSpinBox()
        self.common_axis_line_trend_SpinBox.setMinimum(0.0)
        self.common_axis_line_trend_SpinBox.setMaximum(359.9) 
        self.common_axis_line_trend_SpinBox.setDecimals(1)
        xs_method_line_proj_Layout.addWidget(self.common_axis_line_trend_SpinBox, 0, 2, 1, 1)

        xs_method_line_proj_Layout.addWidget(QLabel("plunge"), 0, 3, 1, 1)
                
        self.common_axis_line_plunge_SpinBox = QDoubleSpinBox()
        self.common_axis_line_plunge_SpinBox.setMinimum(0.0)
        self.common_axis_line_plunge_SpinBox.setMaximum(89.9) 
        self.common_axis_line_plunge_SpinBox.setDecimals(1)
        xs_method_line_proj_Layout.addWidget(self.common_axis_line_plunge_SpinBox, 0, 4, 1, 1)                       

        # calculate profile
                         
        self.project_line_pushbutton = QPushButton(self.tr("Plot traces"))
        self.project_line_pushbutton.clicked.connect(self.create_struct_line_projection)        
        xs_method_line_proj_Layout.addWidget(self.project_line_pushbutton, 1, 0, 1, 5)

        self.reset_curves_pushbutton = QPushButton(self.tr("Reset traces"))
        self.reset_curves_pushbutton.clicked.connect(self.reset_structural_lines_projection)

        xs_method_line_proj_Layout.addWidget(self.reset_curves_pushbutton, 2, 0, 1, 5)
                                                
        xs_method_line_proj_QGroupBox.setLayout(xs_method_line_proj_Layout)        
        xs_line_proj_Layout.addWidget(xs_method_line_proj_QGroupBox)                

                        
        ## 
        
        xs_line_proj_QWidget.setLayout(xs_line_proj_Layout)                
        project_toolbox.addItem (xs_line_proj_QWidget, "Geological traces") 
    
        ## END Line project toolbox
                
        # widget final setup
                
        section_project_layout.addWidget(project_toolbox) 
           
        section_project_QWidget.setLayout(section_project_layout)
        
        return section_project_QWidget


    def setup_intersect_section_tab(self):
        
        intersect_widget = QWidget()  
        intersect_layout = QVBoxLayout()  

        intersect_toolbox = QToolBox()
        
        ### Line intersection section
        
        line_intersect_QWidget = QWidget()
        line_intersect_Layout = QVBoxLayout()         

        ## input section
        
        inters_line_input_QGroupBox = QGroupBox(line_intersect_QWidget)
        inters_line_input_QGroupBox.setTitle('Input')
         
        inters_line_input_Layout = QGridLayout()

                
        # input traces layer
      
        inters_line_input_Layout.addWidget(QLabel("Line layer"), 0, 0, 1, 1)

        self.inters_input_line_comboBox = QComboBox()
                       
        inters_line_input_Layout.addWidget(self.inters_input_line_comboBox, 0, 1, 1, 3)        
        self.refresh_struct_line_lyr_combobox()
                   
        inters_line_input_Layout.addWidget(QLabel("Id field"), 1, 0, 1, 1)
        self.inters_input_id_fld_line_comboBox = QComboBox()
        inters_line_input_Layout.addWidget(self.inters_input_id_fld_line_comboBox, 1, 1, 1, 3)
        
        self.flds_inters_line_comboBoxes = [self.inters_input_id_fld_line_comboBox]
        
        inters_line_input_QGroupBox.setLayout(inters_line_input_Layout)        
        line_intersect_Layout.addWidget(inters_line_input_QGroupBox)  

        ## do section
        
        inters_line_do_QGroupBox = QGroupBox(line_intersect_QWidget)
        inters_line_do_QGroupBox.setTitle('Intersect')
         
        inters_line_do_Layout = QGridLayout()
        
        self.inters_line_do_pushbutton = QPushButton(self.tr("Intersect")) 
        self.inters_line_do_pushbutton.clicked.connect(self.do_line_intersection)
        inters_line_do_Layout.addWidget(self.inters_line_do_pushbutton, 1, 0, 1, 4)

        self.line_inters_reset_pushbutton = QPushButton(self.tr("Reset intersections")) 
        self.line_inters_reset_pushbutton.clicked.connect(self.line_intersection_reset)
        inters_line_do_Layout.addWidget(self.line_inters_reset_pushbutton, 2, 0, 1, 4)
        

        inters_line_do_QGroupBox.setLayout(inters_line_do_Layout)        
        line_intersect_Layout.addWidget(inters_line_do_QGroupBox)  
                
        # END do section
        
        line_intersect_QWidget.setLayout(line_intersect_Layout)                
        intersect_toolbox.addItem (line_intersect_QWidget, "Intersect line layer") 
                       
        # END Line intersection section
 
        ### Polygon intersection section
        
        polygon_intersect_QWidget = QWidget()
        polygon_intersect_Layout = QVBoxLayout()         


        ## input section
        
        inters_polygon_input_QGroupBox = QGroupBox(polygon_intersect_QWidget)
        inters_polygon_input_QGroupBox.setTitle('Input')
         
        inters_polygon_input_Layout = QGridLayout()

                
        # input traces layer
      
        inters_polygon_input_Layout.addWidget(QLabel("Polygon layer"), 0, 0, 1, 1)

        self.inters_input_polygon_comboBox = QComboBox()
                       
        inters_polygon_input_Layout.addWidget(self.inters_input_polygon_comboBox, 0, 1, 1, 3)        
        self.refresh_struct_polygon_lyr_combobox()
                   
        inters_polygon_input_Layout.addWidget(QLabel("Classification field"), 1, 0, 1, 1)
        self.inters_polygon_classifaction_field_comboBox = QComboBox()
        inters_polygon_input_Layout.addWidget(self.inters_polygon_classifaction_field_comboBox, 1, 1, 1, 3)
        
        self.flds_inters_polygon_comboBoxes = [self.inters_polygon_classifaction_field_comboBox]
        
        inters_polygon_input_QGroupBox.setLayout(inters_polygon_input_Layout)        
        polygon_intersect_Layout.addWidget(inters_polygon_input_QGroupBox)  

        ## do section
        
        inters_polygon_do_QGroupBox = QGroupBox(polygon_intersect_QWidget)
        inters_polygon_do_QGroupBox.setTitle('Intersect')
         
        inters_polygon_do_Layout = QGridLayout()
        
        self.inters_polygon_do_pushbutton = QPushButton(self.tr("Intersect")) 
        self.inters_polygon_do_pushbutton.clicked.connect(self.do_polygon_intersection)
        inters_polygon_do_Layout.addWidget(self.inters_polygon_do_pushbutton, 1, 0, 1, 4)

        self.polygon_inters_reset_pushbutton = QPushButton(self.tr("Reset intersections")) 
        self.polygon_inters_reset_pushbutton.clicked.connect(self.polygon_intersection_reset)
        inters_polygon_do_Layout.addWidget(self.polygon_inters_reset_pushbutton, 2, 0, 1, 4)
        

        inters_polygon_do_QGroupBox.setLayout(inters_polygon_do_Layout)        
        polygon_intersect_Layout.addWidget(inters_polygon_do_QGroupBox)  
                
        # END do section

        polygon_intersect_QWidget.setLayout(polygon_intersect_Layout)                
        intersect_toolbox.addItem (polygon_intersect_QWidget, "Intersect polygon layer") 

        # END Polygon intersection section
        
               
        
        intersect_layout.addWidget(intersect_toolbox) 
        
        intersect_widget.setLayout(intersect_layout) 
        
        return intersect_widget       


    def setup_export_section_tab(self):
                
                     
        impexp_widget = QWidget()  
        impexp_layout = QVBoxLayout()  


        # Export section        

        export_QGroupBox = QGroupBox(impexp_widget)
        export_QGroupBox.setTitle('Export')
         
        export_inner_Layout = QGridLayout()
        
          
        self.export_image_QPushButton = QPushButton("Figure")
        export_inner_Layout.addWidget(self.export_image_QPushButton, 1, 0, 1, 4)  
        self.export_image_QPushButton.clicked.connect(self.do_export_image)              
        
        self.export_topographic_profile_QPushButton = QPushButton("Topographic profile data")
        export_inner_Layout.addWidget(self.export_topographic_profile_QPushButton, 2, 0, 1, 4)  
        self.export_topographic_profile_QPushButton.clicked.connect(self.do_export_topo_profiles)      
        
        self.export_project_geol_attitudes_QPushButton = QPushButton("Projected geological attitude data")
        export_inner_Layout.addWidget(self.export_project_geol_attitudes_QPushButton, 3, 0, 1, 4)  
        self.export_project_geol_attitudes_QPushButton.clicked.connect(self.do_export_project_geol_attitudes) 
                
        self.export_project_geol_lines__QPushButton = QPushButton("Projected geological line data")
        export_inner_Layout.addWidget(self.export_project_geol_lines__QPushButton, 4, 0, 1, 4)  
        self.export_project_geol_lines__QPushButton.clicked.connect(self.do_export_project_geol_lines) 
                
        self.export_line_intersections_QPushButton = QPushButton("Line intersection data")
        export_inner_Layout.addWidget(self.export_line_intersections_QPushButton, 5, 0, 1, 4)  
        self.export_line_intersections_QPushButton.clicked.connect(self.do_export_line_intersections) 
                
        self.export_polygon_intersections_QPushButton = QPushButton("Polygon intersection data")
        export_inner_Layout.addWidget(self.export_polygon_intersections_QPushButton, 6, 0, 1, 4)  
        self.export_polygon_intersections_QPushButton.clicked.connect(self.do_export_polygon_intersections)         
                
        export_QGroupBox.setLayout(export_inner_Layout)        
        impexp_layout.addWidget(export_QGroupBox)        

       
        impexp_widget.setLayout(impexp_layout) 
        
        return impexp_widget      

   

    def do_export_topo_profiles(self):
        
        def get_source_type():
            
            if dialog.src_allselecteddems_QRadioButton.isChecked():
                return ["all_dems"]
            elif dialog.src_singledem_QRadioButton.isChecked():
                return ["single_dem",  dialog.src_singledemlist_QComboBox.currentIndex()]
            elif dialog.src_singlegpx_QRadioButton.isChecked():
                return ["gpx_file"]
            else:                
                return []
            
        def get_format_type():
            
            if dialog.outtype_shapefile_line_QRadioButton.isChecked():
                return "shapefile - line"
            elif dialog.outtype_shapefile_point_QRadioButton.isChecked():
                return "shapefile - point"
            elif dialog.outtype_csv_QRadioButton.isChecked():
                return "csv"
            else:
                return ""           
            
        if not (self.profile_GPX or self.profiles):
            self.warn("No profile defined")
            return          
        
        dialog = TopographicProfileExportDialog(self.selected_dems)

        if dialog.exec_():
            
            output_source = get_source_type()
            if output_source == []:
                self.warn("Error in output source")
                return
            
            output_format = get_format_type()
            if output_format == "":
                self.warn("Error in output format")
                return
            
            output_filepath = dialog.outpath_QLineEdit.text()
            if len(output_filepath) == 0:
                self.warn("Error in output path")
                return                         
                    
        else:
            
            self.warn("No export defined")
            return
        
        
        self.output_topography(output_source, output_format, output_filepath)


    def output_topography(self, output_source, output_format, output_filepath):
                
        if output_source[0] == "all_dems":        
            self.topography_export_all_dems(output_format, output_filepath)
        elif output_source[0] == "single_dem": 
            ndx_dem_to_export = output_source[1]
            self.topography_export_single_dem(output_format, ndx_dem_to_export, output_filepath) 
        elif output_source[0] == "gpx_file":
            self.topography_export_gpx_data(output_format, output_filepath)
        else:
            self.warn("Internal error: output choice not correctly defined")
            return


    def do_export_project_geol_attitudes(self):

            
        def get_format_type():
            
            if dialog.outtype_shapefile_point_QRadioButton.isChecked():
                return "shapefile - point"
            elif dialog.outtype_csv_QRadioButton.isChecked():
                return "csv"
            else:
                return ""           

        try:
            num_plane_attitudes_sets = len(self.profiles.plane_attitudes)
        except:
            self.warn("No available geological attitudes")
            return
        else:
            if num_plane_attitudes_sets == 0:
                self.warn("No available geological attitudes")
                return        
        
        dialog = PointDataExportDialog()

        if dialog.exec_():
            
            output_format = get_format_type()
            if output_format == "":
                self.warn("Error in output format")
                return
            
            output_filepath = dialog.outpath_QLineEdit.text()
            if len(output_filepath) == 0:
                self.warn("Error in output path")
                return                         
                    
        else:
            
            self.warn("No export defined")
            return
        
        
        self.output_geological_attitudes(output_format, output_filepath)


    def output_geological_attitudes(self, output_format, output_filepath):


        # definition of field names
        header_list = ['id',
                       'or_strpt_x',
                       'or_strpt_y',
                       'or_strpt_z',
                       'prj_strpt_x',
                       'prj_strpt_y',
                       'prj_strpt_z',
                       's',
                       'or_dipdir',
                       'or_dipangle',
                       'trc_dipangle',
                       'trc_dipdir']

        parsed_geologicalattitudes_results = self.parse_geologicalattitudes_results_for_export(self.profiles.plane_attitudes)

        # output for csv file
        if output_format == "csv":
            self.write_generic_csv(output_filepath, header_list, parsed_geologicalattitudes_results)
        elif output_format == "shapefile - point":
            self.write_geological_attitudes_ptshp(output_filepath, header_list, parsed_geologicalattitudes_results)
        else:
            self.warn("Internal error in export format")
            return
        
        self.info("Projected attitudes saved")
    
    
    def do_export_project_geol_lines(self):
        
        try:
            num_proj_lines_sets = len(self.profiles.curves)
        except:
            self.warn("No available geological traces")
            return 
        else:
            if num_proj_lines_sets == 0:
                self.warn("No available geological traces to save")
                return 

        fileName = QFileDialog.getSaveFileName(self, 
                                               self.tr("Save results"),
                                                "*.csv",
                                                self.tr("csv (*.csv)"))

        if fileName is None or fileName == '':
            self.warn("No output file has been defined")
            return  
            
        parsed_curves_for_export = self.parse_geologicalcurves_for_export()
        header_list = ['id', 's', 'z']
        
        self.write_generic_csv(fileName, header_list, parsed_curves_for_export)
        
        self.info("Projected lines saved")        
          
    
    
    def do_export_line_intersections(self):
   
            
        def get_format_type():
            
            if dialog.outtype_shapefile_point_QRadioButton.isChecked():
                return "shapefile - point"
            elif dialog.outtype_csv_QRadioButton.isChecked():
                return "csv"
            else:
                return ""           

        try:
            num_intersection_pts = len(self.profiles.intersection_pts)
        except:
            self.warn("No available profile-line intersections")
            return
        else:
            if num_intersection_pts == 0:
                self.warn("No available profile-line intersections")
                return        
        
        dialog = PointDataExportDialog()

        if dialog.exec_():
            
            output_format = get_format_type()
            if output_format == "":
                self.warn("Error in output format")
                return
            
            output_filepath = dialog.outpath_QLineEdit.text()
            if len(output_filepath) == 0:
                self.warn("Error in output path")
                return                         
                    
        else:
            
            self.warn("No export defined")
            return
        
        self.output_profile_lines_intersections(output_format, output_filepath)


    def output_profile_lines_intersections(self, output_format, output_filepath):


        # definition of field names
        header_list = ['id',
                       's',
                       'x',
                       'y',
                       'z']

        parsed_profilelineintersections = self.parse_profilelineintersections_for_export(self.profiles.intersection_pts)

        # output for csv file
        if output_format == "csv":
            self.write_generic_csv(output_filepath, header_list, parsed_profilelineintersections)
        elif output_format == "shapefile - point":
            self.write_intersection_line_ptshp(output_filepath, header_list, parsed_profilelineintersections)
        else:
            self.warn("Internal error in export format")
            return
        
        self.info("Profile-lines intersections saved")


               
    def write_intersection_line_ptshp(self, fileName, header_list, intersline_results):


        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName(shape_driver_name)
        if shape_driver is None:
            self.warn("%s driver is not available" % shape_driver_name)
            return

        try:
            shp_datasource = shape_driver.CreateDataSource(unicode(fileName))
        except TypeError:
            shp_datasource = shape_driver.CreateDataSource(str(fileName))
            
        if shp_datasource is None:
            self.warn("Creation of %s shapefile failed" % os.path.split(fileName)[1])
            return

        ptshp_layer = shp_datasource.CreateLayer('profile', geom_type=ogr.wkbPoint25D)
        if ptshp_layer is None:
            self.warn("Output layer creation failed")
            return

        # creates required fields
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[0], ogr.OFTString))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[1], ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[2], ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[3], ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[4], ogr.OFTReal))

        ptshp_featureDefn = ptshp_layer.GetLayerDefn()

        # loops through output records
        for rec_id, s, x, y, z in intersline_results:

            pt_feature = ogr.Feature(ptshp_featureDefn)

            pt = ogr.Geometry(ogr.wkbPoint25D)
            pt.SetPoint(0, x, y, z)
            pt_feature.SetGeometry(pt)

            pt_feature.SetField(header_list[0], str(rec_id))
            pt_feature.SetField(header_list[1], s)
            pt_feature.SetField(header_list[2], x)
            pt_feature.SetField(header_list[3], y)
            pt_feature.SetField(header_list[4], z)
            
            ptshp_layer.CreateFeature(pt_feature)

            pt_feature.Destroy()

        shp_datasource.Destroy()


    def parse_profilelineintersections_for_export(self, profile_intersection_pts):

        result_data = []  
              
        for distances_from_profile_start, intersection_point3d, intersection_id in profile_intersection_pts: 

            result_data.append([intersection_id, distances_from_profile_start, intersection_point3d._x, intersection_point3d._y, intersection_point3d._z])
         
        return result_data

   
    def do_export_polygon_intersections(self):  
            
        def get_format_type():
            
            if dialog.outtype_shapefile_line_QRadioButton.isChecked():
                return "shapefile - line"
            elif dialog.outtype_csv_QRadioButton.isChecked():
                return "csv"
            else:
                return ""           

        try:
            num_intersection_lines = len(self.profiles.intersection_lines)
        except:
            self.warn("No available profile-polygon intersections")
            return
        else:
            if num_intersection_lines == 0:
                self.warn("No available profile-polygon intersections")
                return        
        
        dialog = LineDataExportDialog()

        if dialog.exec_():
            
            output_format = get_format_type()
            if output_format == "":
                self.warn("Error in output format")
                return
            
            output_filepath = dialog.outpath_QLineEdit.text()
            if len(output_filepath) == 0:
                self.warn("Error in output path")
                return                         
                    
        else:
            
            self.warn("No export defined")
            return
        
        
        self.output_profile_polygons_intersections(output_format, output_filepath)


    def output_profile_polygons_intersections(self, output_format, output_filepath):

        # definition of field names
        header_list = ['class_fld',
                       's',
                       'x',
                       'y',
                       'z']

        # output for csv file
        if output_format == "csv":
            self.write_line_csv(output_filepath, header_list, self.profiles.intersection_lines)
        elif output_format == "shapefile - line":
            self.write_intersection_polygon_lnshp(output_filepath, header_list, self.profiles.intersection_lines)
        else:
            self.warn("Internal error in export format")
            return
        
        self.info("Profile-polygon intersections saved")


               
    def write_intersection_polygon_lnshp(self, fileName, header_list, intersline_results):


        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName(shape_driver_name)
        if shape_driver is None:
            self.warn("%s driver is not available" % shape_driver_name)
            return

        try:
            shp_datasource = shape_driver.CreateDataSource(unicode(fileName))
        except TypeError:
            shp_datasource = shape_driver.CreateDataSource(str(fileName))
            
        if shp_datasource is None:
            self.warn("Creation of %s shapefile failed" % os.path.split(fileName)[1])
            return

        lnshp_layer = shp_datasource.CreateLayer('profile', geom_type=ogr.wkbLineString25D)
        if lnshp_layer is None:
            self.warn("Output layer creation failed")
            return

        # creates required fields
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[0], ogr.OFTString))
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[1], ogr.OFTReal))

        lnshp_featureDefn = lnshp_layer.GetLayerDefn()

        # loops through output records
        
        for classification, line3d, s_list in intersline_results:
            
            assert len(line3d._pts) == len(s_list)
            
            # loops through output records   
                              
            for ndx in range(len(line3d._pts) - 1):
                
                rec_a = line3d._pts[ndx]
                rec_b = line3d._pts[ndx+1]
                  
                x0, y0, z0 = rec_a._x, rec_a._y, rec_a._z
                x1, y1, z1 = rec_b._x, rec_b._y, rec_b._z
                s = s_list[ndx+1]
    
                ln_feature = ogr.Feature(lnshp_featureDefn)            
                segment_3d = ogr.CreateGeometryFromWkt('LINESTRING(%f %f %f, %f %f %f)' % (x0, y0, z0, x1, y1, z1))       
                ln_feature.SetGeometry(segment_3d) 
    
                ln_feature.SetField(header_list[0], str(classification))
                ln_feature.SetField(header_list[1], s)
                
                lnshp_layer.CreateFeature(ln_feature)
    
                ln_feature.Destroy()

        shp_datasource.Destroy()

    
           
    def setup_about_tab(self):
 
        help_QGroupBox = QGroupBox( self.tr("Help") )  
        
        helpLayout = QVBoxLayout( ) 
                
        self.help_pButton = QPushButton( "Open help in browser" )
        self.help_pButton.clicked[bool].connect( self.open_html_help ) 
        self.help_pButton.setEnabled( True )       
        helpLayout.addWidget( self.help_pButton ) 
                
        help_QGroupBox.setLayout( helpLayout )  
              
        return help_QGroupBox


    def open_html_help( self ):        

        webbrowser.open('{}/help/help.html'.format(os.path.dirname(__file__)), new = True )


    def refresh_struct_point_lyr_combobox(self):
        
        self.pointLayers = loaded_point_layers()
        self.prj_struct_point_comboBox.clear()        
        message = "choose"
        self.prj_struct_point_comboBox.addItem(message)
        self.prj_struct_point_comboBox.addItems([layer.name() for layer in self.pointLayers])              


    def update_ComboBox(self, combobox, layer_list):
    
        combobox.clear()
        if len(layer_list) == 0:
            return
        combobox.addItem("choose")
        combobox.addItems([layer.name() for layer in layer_list]) 
            

    def refresh_struct_polygon_lyr_combobox(self):
        
        self.current_polygon_layers = loaded_polygon_layers()    
        #self.update_ComboBox(self.prj_input_polygon_comboBox, self.current_polygon_layers)
        self.update_ComboBox(self.inters_input_polygon_comboBox, self.current_polygon_layers)
        
        
    def refresh_struct_line_lyr_combobox(self):
        
        self.current_line_layers = loaded_line_layers()    
        self.update_ComboBox(self.prj_input_line_comboBox, self.current_line_layers)
        self.update_ComboBox(self.inters_input_line_comboBox, self.current_line_layers)
 
 
    def define_source_DEMs(self):  
        
        self.selected_dems = []
        self.selected_dem_colors = []
        self.selected_dem_parameters = []
        
        current_raster_layers = loaded_monoband_raster_layers()  
        if len(current_raster_layers) == 0:
            self.warn("No loaded DEM")
            return            

        dialog = SourceDEMsDialog(current_raster_layers)

        if dialog.exec_():
            selected_dems, selected_dem_colors = self.get_selected_dems_params(dialog)
        else:
            self.warn("No DEM chosen")
            return
            
        if  len(selected_dems) == 0: 
            self.warn("No selected DEM")
            return      
        else:
            self.selected_dems = selected_dems
            self.selected_dem_colors = selected_dem_colors 
 
        # get project CRS information
        on_the_fly_projection, project_crs = self.get_on_the_fly_projection() 
                
        # get geodata
        self.selected_dem_parameters = [self.get_dem_parameters(dem) for dem in selected_dems] 
        
        # get DEMs resolutions in project CRS and choose the min value
        dem_resolutions_prj_crs_list = []        
        for dem, dem_params in zip(self.selected_dems, self.selected_dem_parameters):
            dem_resolutions_prj_crs_list.append(self.get_dem_resolution_in_prj_crs(dem, dem_params, on_the_fly_projection, project_crs))
        min_dem_resolution = min(dem_resolutions_prj_crs_list)
        if min_dem_resolution > 1:
            min_dem_proposed_resolution = round(min_dem_resolution)
        else:
            min_dem_proposed_resolution = min_dem_resolution
        self.profile_densify_distance_lineedit.setText(str(min_dem_proposed_resolution))
         
        
    def get_selected_dems_params(self, dialog):   

        selected_dems = []
        selected_dem_colors = [] 
        for dem_qgis_ndx in range(dialog.listDEMs_treeWidget.topLevelItemCount ()):
            curr_DEM_item = dialog.listDEMs_treeWidget.topLevelItem (dem_qgis_ndx) 
            if curr_DEM_item.checkState (0) == 2:
                selected_dems.append(dialog.singleband_raster_layers_in_project[dem_qgis_ndx])
                selected_dem_colors.append(dialog.listDEMs_treeWidget.itemWidget(curr_DEM_item, 1).currentText())  
         
        return selected_dems, selected_dem_colors
        
 
    def define_line(self):
        
        if self.DigitizeLine_checkbox.isChecked():
            self.digitize_line()
        elif self.LoadLineLayer_checkbox.isChecked():
            self.load_line_layer()
        elif self.PointListforLine_checkbox.isChecked():
            self.load_point_list()
        
        
    def get_line_layer_params(self, dialog):
        
        line_layer = dialog.line_shape
        order_field_ndx = dialog.Trace2D_order_field_comboBox.currentIndex() 
        
        return line_layer, order_field_ndx
        

    def get_point_list(self, dialog):
        
        raw_point_string = dialog.point_list_qtextedit.toPlainText()
        raw_point_list = raw_point_string.split("\n")
        raw_point_list = map(lambda unicode_txt: clean_string(str(unicode_txt)), raw_point_list) 
        data_list = filter(lambda rp: rp != "", raw_point_list)       
        
        #try:
        point_list = [to_float(xy_pair.split(",")) for xy_pair in data_list]
        line2d = xytuple_list_to_Line2D(point_list)
        assert line2d.num_points() >= 2
        return line2d
        
           
    def digitize_line(self):

        self.info("Now you can digitize a line on the map.\nLeft click: add point\nRight click: end adding point")

        try:
            self.rubberband.reset(QGis.Line)
        except:
            pass

        self.previous_maptool = self.mapcanvas.mapTool()            # Save the standard map tool for restoring it at the end
        self.digitize_maptool = MapDigitizeTool(self.mapcanvas)        #  mouse listener
        self.mapcanvas.setMapTool(self.digitize_maptool)
        self.connect_digitize_maptool()
        
        self.polygon = False
        self.rubberband = QgsRubberBand(self.mapcanvas, self.polygon)
        self.rubberband.setWidth(1)
        self.rubberband.setColor(QColor(Qt.red))

        self.profile_canvas_points = []


    def connect_digitize_maptool(self):
        
        QObject.connect(self.digitize_maptool, SIGNAL("moved"), self.canvas_refresh_profile_line)
        QObject.connect(self.digitize_maptool, SIGNAL("leftClicked"), self.canvas_add_point_to_profile)        
        QObject.connect(self.digitize_maptool, SIGNAL("rightClicked"), self.canvas_end_profile_line)


    def disconnect_digitize_maptool(self):
        
        QObject.disconnect(self.digitize_maptool, SIGNAL("moved"), self.canvas_refresh_profile_line)        
        QObject.disconnect(self.digitize_maptool, SIGNAL("leftClicked"), self.canvas_add_point_to_profile)
        QObject.disconnect(self.digitize_maptool, SIGNAL("rightClicked"), self.canvas_end_profile_line)


    def xy_from_canvas(self, position):
        
        mapPos = self.mapcanvas.getCoordinateTransform().toMapCoordinates(position["x"], position["y"])
        return  mapPos.x(), mapPos.y()


    def refresh_rubberband(self, xy_list):
        
        self.rubberband.reset(QGis.Line) 
        for x,y in xy_list:
            self.rubberband.addPoint(QgsPoint(x, y))
                
        
    def canvas_refresh_profile_line( self, position):  
   
        if len(self.profile_canvas_points) == 0:
            return     

        x, y = self.xy_from_canvas(position) 
        self.refresh_rubberband(self.profile_canvas_points + [[x,y]])           


    def profile_add_point(self, position):

        x, y = self.xy_from_canvas(position)        
        self.profile_canvas_points.append([x,y])        


    def canvas_add_point_to_profile( self, position):
        
        if len(self.profile_canvas_points) == 0:
            self.rubberband.reset(self.polygon)
            
        self.profile_add_point(position)
                         

    def canvas_end_profile_line( self, position):
        
        self.refresh_rubberband(self.profile_canvas_points)

        self.source_profile = Line2D([Point2D(x, y) for x, y in self.profile_canvas_points])
        #self.profile_points_from_canvas = self.profile_canvas_points
        self.profile_canvas_points = []
       

    def restore_previous_map_tool(self):
        
        self.mapcanvas.unsetMapTool(self.digitize_maptool)
        self.mapcanvas.setMapTool(self.previous_maptool)


    def load_line_layer(self):
        
        try:
            self.disconnect_digitize_maptool()
        except:
            pass
        
        try:
            self.rubberband.reset(QGis.Line)
        except:
            pass
        
        
        current_line_layers = loaded_line_layers()   

        if len(current_line_layers) == 0:
            self.warn("No available line layers")
            return            

        dialog = SourceLineLayerDialog(current_line_layers)

        if dialog.exec_():
            line_layer, order_field_ndx = self.get_line_layer_params(dialog)
        else:
            self.warn("No defined line source")
            return

        line_fld_ndx = int(order_field_ndx) - 1
        # get profile path from input line layer
        success, result = self.get_line_trace(line_layer, line_fld_ndx)
        if not success:
            raise VectorIOException, result
        
        profile_orig_lines, mergeorder_ids = result

        profile_processed_line_2d = merge_lines(profile_orig_lines, mergeorder_ids)   
        
        on_the_fly_projection, project_crs = self.get_on_the_fly_projection()         

        # process input line layer
        profile_projected_line_2d = self.create_line_in_project_crs(profile_processed_line_2d, line_layer.crs(), on_the_fly_projection, project_crs)
        
        self.source_profile = profile_projected_line_2d.remove_coincident_successive_points()
        

    def load_point_list(self):
        
        dialog = LoadPointListDialog()

        if dialog.exec_():
            line2d = self.get_point_list(dialog)
        else:
            self.warn("No defined line source")
            return

        self.source_profile = line2d
        
                   
    def get_on_the_fly_projection(self):
        
        on_the_fly_projection = True if self.mapcanvas.hasCrsTransformEnabled() else False
        if on_the_fly_projection:
            project_crs = self.mapcanvas.mapRenderer().destinationCrs()
        else:
            project_crs = None
            
        return on_the_fly_projection, project_crs                   
 

    def get_dem_parameters(self, dem):
    
        return QGisRasterParameters(*raster_qgis_params(dem))

    
    def get_z(self, dem_layer, point):
        
        identification = dem_layer.dataProvider().identify(QgsPoint(point._x, point._y), QgsRaster.IdentifyFormatValue)
        if not identification.isValid(): 
            return np.nan
        else:
            try: 
                result_map = identification.results()
                return float(result_map[1])
            except:
                return np.nan
                          

    def interpolate_bilinear(self, dem, dem_params, point):  
      
        array_coords_dict = dem_params.geogr2raster(point)
        floor_x_raster = floor(array_coords_dict["x"])
        ceil_x_raster = ceil(array_coords_dict["x"])
        floor_y_raster = floor(array_coords_dict["y"])
        ceil_y_raster = ceil(array_coords_dict["y"])                
         
        # bottom-left center
        p1 = dem_params.raster2geogr(dict(x=floor_x_raster,
                                           y=floor_y_raster))
        # bottom-right center       
        p2 = dem_params.raster2geogr(dict(x=ceil_x_raster,
                                           y=floor_y_raster))
        # top-left center
        p3 = dem_params.raster2geogr(dict(x=floor_x_raster,
                                           y=ceil_y_raster)) 
        # top-right center       
        p4 = dem_params.raster2geogr(dict(x=ceil_x_raster,
                                           y=ceil_y_raster))
         
        z1 = self.get_z(dem, p1)
        z2 = self.get_z(dem, p2)         
        z3 = self.get_z(dem, p3)
        z4 = self.get_z(dem, p4) 
        
        delta_x = point._x - p1._x
        delta_y = point._y - p1._y 

        z_x_a = z1 + (z2-z1)*delta_x/dem_params.cellsizeEW
        z_x_b = z3 + (z4-z3)*delta_x/dem_params.cellsizeEW        
        
        return z_x_a + (z_x_b-z_x_a)*delta_y/dem_params.cellsizeNS


    def get_selected_dem_indices(self):   

        selected_dem_indices = []
        for dem_qgis_ndx in range(self.listDEMs_treeWidget.topLevelItemCount ()):
            curr_DEM_item = self.listDEMs_treeWidget.topLevelItem (dem_qgis_ndx) 
            if curr_DEM_item.checkState (0) == 2:
                selected_dem_indices.append(dem_qgis_ndx)
        return selected_dem_indices
           

    def get_line_trace(self, line_shape, order_field_ndx):

        try:
            profile_orig_lines, mergeorder_ids = line_geoms_with_id(line_shape, order_field_ndx)
        except VectorInputException as error_msg:
            return False, error_msg
        return True, (profile_orig_lines, mergeorder_ids)        
        

    def create_line_in_project_crs(self, profile_processed_line, line_layer_crs, on_the_fly_projection, project_crs):
        
        if not on_the_fly_projection:
            return profile_processed_line
        else: 
            return line2d_change_crs(profile_processed_line, line_layer_crs, project_crs)


    def interpolate_z(self, dem, dem_params, point):

        if dem_params.point_in_interpolation_area(point):
            return self.interpolate_bilinear(dem, dem_params, point)
        elif dem_params.point_in_dem_area(point):
            return self.get_z(dem, point)
        else:
            return np.nan


    def create_3d_profile(self, resampled_trace2d, on_the_fly_projection, project_crs, dem, dem_params):

        if on_the_fly_projection and dem.crs() != project_crs:
            trace2d_in_dem_crs = line2d_change_crs(resampled_trace2d, project_crs, dem.crs())
        else:
            trace2d_in_dem_crs = resampled_trace2d

        profile_line3d = Line3D()
        for trace_pt2d_dem_crs, trace_pt2d_project_crs in zip(trace2d_in_dem_crs.pts(), resampled_trace2d.pts()):
            interpolated_z = self.interpolate_z(dem, dem_params, trace_pt2d_dem_crs)
            pt_3d = Point3D(trace_pt2d_project_crs.x(),
                            trace_pt2d_project_crs.y(),
                            interpolated_z)
            profile_line3d.add_pt(pt_3d)

        return profile_line3d

   
    def get_dem_resolution_in_prj_crs(self, dem, dem_params, on_the_fly_projection, prj_crs):   
        
        def distance_projected_pts(x, y, delta_x, delta_y, src_crs, dest_crs):
            
            qgspt_start_src_crs = qgs_point_2d(x, y)
            qgspt_end_src_crs = qgs_point_2d(x + delta_x, y + delta_y) 
            
            qgspt_start_dest_crs = project_qgs_point(qgspt_start_src_crs, src_crs, dest_crs)
            qgspt_end_dest_crs = project_qgs_point(qgspt_end_src_crs, src_crs, dest_crs)  
            
            pt2_start_dest_crs = Point2D(qgspt_start_dest_crs.x(), qgspt_start_dest_crs.y())
            pt2d_end_dest_crs = Point2D(qgspt_end_dest_crs.x(), qgspt_end_dest_crs.y())        
        
            return pt2_start_dest_crs.distance(pt2d_end_dest_crs)               
                   
        cellsizeEW, cellsizeNS = dem_params.cellsizeEW, dem_params.cellsizeNS
        xMin, yMin = dem_params.xMin, dem_params.yMin
        
        if on_the_fly_projection and dem.crs() != prj_crs :            
            cellsizeEW_prj_crs = distance_projected_pts(xMin, yMin, cellsizeEW, 0, dem.crs(), prj_crs)
            cellsizeNS_prj_crs = distance_projected_pts(xMin, yMin, 0, cellsizeNS, dem.crs(), prj_crs)                        
        else:            
            cellsizeEW_prj_crs = cellsizeEW
            cellsizeNS_prj_crs = cellsizeNS
            
        return 0.5 * (cellsizeEW_prj_crs + cellsizeNS_prj_crs)
        

    def calculate_profiles(self):

        try:
            return self.calculate_dem_profiles()
        except VectorIOException, msg:
            self.warn(msg)
            return None


    def verify_profile_src_params(self):

        # get profile creation parameters
        if self.selected_dems == []:
            self.warn("DEM(s) not yet defined")
            return False
        try:
            assert self.source_profile.num_points() > 1
        except:
            self.warn("Profile line not yet defined")
            return False
        try:
            self.sample_distance = float(self.profile_densify_distance_lineedit.text())
            assert self.sample_distance > 0
        except:
            self.sample_distance = None
            self.warn("Line densify distance not correctly defined")
            return False

        return True


    def get_statistics(self, topo_profile):

        dem_name = topo_profile.dem_name
        profile_line3d = topo_profile.profile_3d

        z_min = profile_line3d.z_min()
        z_max = profile_line3d.z_max()
        z_mean = profile_line3d.z_mean()
        z_var = profile_line3d.z_var()
        z_std = profile_line3d.z_std()

        stats = dict(dem_name=dem_name,
                     z_min=z_min,
                     z_max=z_max,
                     z_mean=z_mean,
                     z_var=z_var,
                     z_std=z_std)

        return stats


    def calculate_statistics(self):

         # get profile creation parameters
        verified = self.verify_profile_src_params()
        if not verified:
            return

        # reverse profile line orientation if required
        if not self.swap_profile_horiz_checkbox.isChecked():
            self.used_profile_line = self.source_profile
        else:
            self.used_profile_line = self.source_profile.swap_horiz()

        # calculates profiles if they do not exist
        self.profiles = self.calculate_profiles()

        if self.profiles is not None:
            statistics = map(lambda p: self.get_statistics(p), self.profiles.topo_profiles)
            dialog = StatisticsDialog(statistics)
            dialog.exec_()
        else:
            self.warn('Unable to calculate statistics')


    def create_topo_profiles_from_DEMs(self):

        # get profile creation parameters
        verified = self.verify_profile_src_params()
        if not verified:
            return

        # get profile plot parameters

        try:
            self.plot_min_value_user = float(self.plot_min_value_QLineedit.text())
        except:
            self.plot_min_value_user = None

        try:
            self.plot_max_value_user = float(self.plot_max_value_QLineedit.text())
        except:
            self.plot_max_value_user = None

        try:
            self.vertical_exaggeration = float(self.DEM_exageration_ratio_Qlineedit.text())
            assert self.vertical_exaggeration > 0
        except:
            self.warn("Vertical exaggeration must be numeric and positive")
            return

        plot_height_choice = self.DEM_plot_height_checkbox.isChecked()
        plot_slope_choice = self.DEM_plot_slope_checkbox.isChecked()
        if not (plot_height_choice or plot_slope_choice):
            self.warn("Neither height or slope plot options are selected")

        if not self.swap_profile_horiz_checkbox.isChecked():
            self.used_profile_line = self.source_profile
        else:
            self.used_profile_line = self.source_profile.swap_horiz()

        # calculates profiles if they do not exist
        self.profiles = self.calculate_profiles()

        # plot profiles
        if self.profiles is not None:
            self.plot_profile_elements(self.vertical_exaggeration)


    def calculate_dem_profiles(self):

        # get project CRS information
        on_the_fly_projection, project_crs = self.get_on_the_fly_projection() 

        resampled_line_2d = self.used_profile_line.densify(self.sample_distance) # line resampled by sample distance
       
        # calculate 3D profiles from DEMs
        profiles_lines3d = []
        for dem, dem_params in zip(self.selected_dems, self.selected_dem_parameters):
            profile_3d = self.create_3d_profile(resampled_line_2d, on_the_fly_projection, project_crs, dem, dem_params)
            profiles_lines3d.append(profile_3d)

        # setup profiles properties
        profiles = Profile_Elements(self.sample_distance)
        profiles.dems_params = [DEMParams(dem, params) for (dem, params) in zip(self.selected_dems, self.selected_dem_parameters)]
        profiles.resamp_src_line = resampled_line_2d
        for dem_name, line_3d in zip([dem.name() for dem in self.selected_dems], profiles_lines3d):
            profiles.add_topo_profile(TopoLine3D(dem_name, line_3d))
        
        return profiles


    def parse_DEM_results_for_export(self, profiles):
                
        # definition of output results         
        x_list = profiles.topo_profiles[0].x_list()
        y_list = profiles.topo_profiles[0].y_list() 
        elev_list = [topo_profile.z_list() for topo_profile in profiles.topo_profiles]              
        cumdist_2D_list = profiles.topo_profiles[0].get_increm_dist_2d()
        cumdist_3d_list = [topo_profile.get_increm_dist_3d() for topo_profile in profiles.topo_profiles]
        slopes = [topo_profile.slope_list() for topo_profile in profiles.topo_profiles]

        elev_list_zip = zip(*elev_list)
        cumdist_3d_list_zip = zip(*cumdist_3d_list) 
        slope_list_zip = zip(*slopes)

        result_data = []
        rec_id = 0
        for x, y, cum_2d_dist, zs, cum3d_dists, slopes in zip(x_list, y_list, cumdist_2D_list, elev_list_zip, cumdist_3d_list_zip, slope_list_zip):
            rec_id += 1
            record = [rec_id, x, y, cum_2d_dist]
            for z, cum3d_dist, slope in zip(zs, cum3d_dists, slopes):
                if isnan(z): z = ''
                if isnan(cum3d_dist): cum3d_dist = ''
                if isnan(slope): slope = ''
                record += [z, cum3d_dist, slope]
            result_data.append(record)
         
        return profiles.get_current_dem_names(), result_data

     
    def topography_export_all_dems(self, out_format, outfile_path):
        
        if not self.profiles:
            self.warn("No DEM-derived profile defined")
            return   
        
        # process results for data export         
        dem_names, export_data = self.parse_DEM_results_for_export(self.profiles)
                                  
        # definition of field names
        dem_headers = []
        cum3ddist_headers = []
        slopes_headers = []  
        for ndx in range(len(dem_names)):
            dem_headers.append(unicodedata.normalize('NFKD', unicode(dem_names[ndx][:10])).encode('ascii', 'ignore'))
            cum3ddist_headers.append("cds3d_"+str(ndx+1))
            slopes_headers.append("slopd_"+str(ndx+1))

        header_list = ["id", "x", "y", "cds2d"] + [name for sublist in zip(dem_headers, cum3ddist_headers, slopes_headers) for name in sublist]              
            
        if out_format == "csv":            
            self.write_topography_allDEMs_csv(outfile_path, header_list, export_data)
        elif out_format == "shapefile - point":
            self.write_topography_allDEMs_ptshp(outfile_path, header_list, dem_names, export_data)
        elif out_format == "shapefile - line":
            self.write_topography_allDEMs_lnshp(outfile_path, header_list, dem_names, export_data) 
        else:
            self.warn("Internal error in export all DEMs")
            return           
        
        self.info("Profile export completed")
        
                
    def topography_export_single_dem(self, out_format, ndx_dem_to_export, outfile_path):     

        if not self.profiles:
            self.warn("No DEM-derived profile defined")
            return   
        
        # process results for data export         
        _, export_data = self.parse_DEM_results_for_export(self.profiles)
        
        # definition of field names         
        header_list = ["id", "x", "y", "cds2d", "z", "cds3d", "slopdeg"]      
        
        if out_format == "csv":            
            self.write_topography_singleDEM_csv(outfile_path, header_list, export_data, ndx_dem_to_export)
        elif out_format == "shapefile - point":
            self.write_topography_singleDEM_ptshp(outfile_path, header_list, export_data, ndx_dem_to_export)
        elif out_format == "shapefile - line":
            self.write_topography_singleDEM_lnshp(outfile_path, header_list, export_data, ndx_dem_to_export) 
        else:
            self.warn("Internal error in export single DEM")
            return           
        
        self.info("Profile export completed")


    def topography_export_gpx_data(self, out_format, output_filepath):
            
        if not self.profile_GPX:
            self.warn("No GPX-derived profile defined")
            return   

        # process results from export         
        gpx_parsed_results = self.parse_GPX_results_for_export(self.profile_GPX)
                
        # definition of field names        
        header_list = ["id", "lat", "lon", "time", "elev", "cds2d", "cds3d", "slopdeg"]                
        # header_list = [unicodedata.normalize('NFKD', unicode(header)).encode('ascii', 'ignore') for header in header_list]
        
        if out_format == "csv":            
            self.write_generic_csv(output_filepath, header_list, gpx_parsed_results)
        elif out_format == "shapefile - point":
            self.write_topography_GPX_ptshp(output_filepath, header_list, gpx_parsed_results)
        elif out_format == "shapefile - line":
            self.write_topography_GPX_lnshp(output_filepath, header_list, gpx_parsed_results) 
        else:
            self.warn("Internal error in export single DEM")
            return           
        
        self.info("Profile export completed")
        
        
    def write_topography_allDEMs_csv(self, fileName, header_list, export_data, sep=","):

        with open(unicode(fileName), 'w') as f:
            f.write(sep.join(header_list)+'\n')
            for rec in export_data:
                out_rec_string = ''
                for val in rec:
                    out_rec_string += str(val) + sep
                f.write(out_rec_string[:-1]+'\n')
        

    def write_topography_singleDEM_csv(self, fileName, header_list, export_data, current_dem_ndx, sep=","):
                 
        with open(unicode(fileName), 'w') as f:            
            f.write(sep.join(header_list)+'\n')            
            for rec in export_data:
                rec_id, x, y, cum2ddist = rec[0], rec[1], rec[2], rec[3]                
                z = rec[3+current_dem_ndx*3+1]
                cum3ddist = rec[3+current_dem_ndx*3+2]
                slope = rec[3+current_dem_ndx*3+3]               
                
                outdata_list = [str(val) for val in [rec_id, x, y, cum2ddist, z, cum3ddist, slope]]
                f.write(sep.join(outdata_list) + "\n")
                
               
    def write_generic_csv(self, output_filepath, header_list, parsed_results, sep=","):
        
        with open(unicode(output_filepath), 'w') as f:
            f.write(sep.join(header_list)+'\n')
            for rec in parsed_results:
                out_rec_string = ''
                for val in rec:
                    out_rec_string += str(val) + sep
                f.write(out_rec_string[:-1]+'\n')


    def write_line_csv(self, output_filepath, header_list, parsed_results, sep=","):
        
        with open(unicode(output_filepath), 'w') as f:
            f.write(sep.join(header_list)+'\n')
            for classification, line3d, s_list in parsed_results:
                for pt, s in zip(line3d._pts, s_list):
                    out_values = [classification, s, pt._x, pt._y, pt._z]
                    out_val_strings = [str(val) for val in out_values]
                    f.write(sep.join(out_val_strings) + '\n')
                
                                      
    def write_topography_allDEMs_ptshp(self, fileName, header_list, dem_names, export_data):

        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName(shape_driver_name)
        if shape_driver is None:
            self.warn("%s driver is not available" % shape_driver_name)
            return           
        
        try:    
            shp_datasource = shape_driver.CreateDataSource(unicode(fileName))
        except TypeError:
            shp_datasource = shape_driver.CreateDataSource(str(fileName))
            
        if shp_datasource is None:
            self.warn("Creation of %s shapefile failed" % os.path.split(fileName)[1])
            return         
        
        ptshp_layer = shp_datasource.CreateLayer('profile', geom_type=ogr.wkbPoint)
        if ptshp_layer is None:
            self.warn("Output layer creation failed")
            return 
       
        # creates required fields         
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[0], ogr.OFTInteger))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[1], ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[2], ogr.OFTReal))       
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[3], ogr.OFTReal))

        for dem_ndx in range(len(dem_names)):       
            ptshp_layer.CreateField(ogr.FieldDefn(header_list[3+dem_ndx*3+1], ogr.OFTReal))       
            ptshp_layer.CreateField(ogr.FieldDefn(header_list[3+dem_ndx*3+2], ogr.OFTReal))        
            ptshp_layer.CreateField(ogr.FieldDefn(header_list[3+dem_ndx*3+3], ogr.OFTReal))        
        
        ptshp_featureDefn = ptshp_layer.GetLayerDefn()
        
        field_names = []
        for i in range(ptshp_featureDefn.GetFieldCount()):
            field_names.append(ptshp_featureDefn.GetFieldDefn(i).GetName())
            
        assert len(header_list) == len(field_names)
                  
        # loops through output records                       
        for rec in export_data:
            
            pt_feature = ogr.Feature(ptshp_featureDefn)
            
            pt = ogr.Geometry(ogr.wkbPoint)
            pt.SetPoint_2D(0, rec[1], rec[2])        
            pt_feature.SetGeometry(pt)

            pt_feature.SetField(field_names[0], rec[0])
            pt_feature.SetField(field_names[1], rec[1])   
            pt_feature.SetField(field_names[2], rec[2]) 
            pt_feature.SetField(field_names[3], rec[3])  
            for dem_ndx in range(len(dem_names)):
                dem_height = rec[3+dem_ndx*3+1]
                if dem_height != '': 
                    pt_feature.SetField(field_names[3+dem_ndx*3+1], dem_height)             
                cum3ddist = rec[3+dem_ndx*3+2]
                if cum3ddist != '': 
                    pt_feature.SetField(field_names[3+dem_ndx*3+2], cum3ddist)
                slope = rec[3+dem_ndx*3+3]
                if slope != '': 
                    pt_feature.SetField(field_names[3+dem_ndx*3+3], slope)                  
  
            ptshp_layer.CreateFeature(pt_feature)            
            pt_feature.Destroy()            
        shp_datasource.Destroy()
   
                                
    def write_topography_singleDEM_ptshp(self, fileName, header_list, export_data, current_dem_ndx): 
             
        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName(shape_driver_name)
        if shape_driver is None:
            self.warn("%s driver is not available" % shape_driver_name)
            return             
            
        try:
            ptshp_datasource = shape_driver.CreateDataSource(unicode(fileName))
        except TypeError:
            ptshp_datasource = shape_driver.CreateDataSource(str(fileName))
                        
        if ptshp_datasource is None:
            self.warn("Creation of %s shapefile failed" % os.path.split(fileName)[1])
            return         
        
        ptshp_layer = ptshp_datasource.CreateLayer('profile', geom_type = ogr.wkbPoint)
        if ptshp_layer is None:
            self.warn("Output layer creation failed")
            return     
  
        # creates required fields          
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[0], ogr.OFTInteger))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[1], ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[2], ogr.OFTReal)) 
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[3], ogr.OFTReal))       
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[4], ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[5], ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[6], ogr.OFTReal))     
    
        ptshp_featureDefn = ptshp_layer.GetLayerDefn()
        
        # loops through output records   
                          
        for rec in export_data:

            rec_id, x, y, cumdist2D = rec[0], rec[1], rec[2], rec[3]         
            z = rec[3+current_dem_ndx*3+1]
            cumdist3D = rec[3+current_dem_ndx*3+2]
            slopedegr = rec[3+current_dem_ndx*3+3]
            
            if z == "":
                continue
                               
            pt_feature = ogr.Feature(ptshp_featureDefn)
            
            pt = ogr.Geometry(ogr.wkbPoint)
            pt.SetPoint_2D(0, x, y)        
            pt_feature.SetGeometry(pt)

            pt_feature.SetField(header_list[0], rec_id)
            pt_feature.SetField(header_list[1], x)   
            pt_feature.SetField(header_list[2], y)
            pt_feature.SetField(header_list[3], cumdist2D)             
            pt_feature.SetField(header_list[4], z) 
            if cumdist3D != '': 
                pt_feature.SetField(header_list[5], cumdist3D)
            if slopedegr != '': 
                pt_feature.SetField(header_list[6], slopedegr)   
                            
            ptshp_layer.CreateFeature(pt_feature)            
            pt_feature.Destroy()            
        ptshp_datasource.Destroy()
      
        
    def write_topography_GPX_ptshp(self, output_filepath, header_list, gpx_parsed_results):
                
        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName(shape_driver_name)
        if shape_driver is None:
            self.warn("%s driver is not available" % shape_driver_name)
            return             
            
        try:
            shp_datasource = shape_driver.CreateDataSource(unicode(output_filepath))
        except TypeError:
            shp_datasource = shape_driver.CreateDataSource(str(output_filepath))
                        
        if shp_datasource is None:
            self.warn("Creation of %s shapefile failed" % os.path.split(output_filepath)[1])
            return         
        
        ptshp_layer = shp_datasource.CreateLayer('profile', geom_type=ogr.wkbPoint)
        if ptshp_layer is None:
            self.warn("Point layer creation failed")
            return 
                        
        # creates required fields         
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[0], ogr.OFTInteger))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[1], ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[2], ogr.OFTReal))
        time_field = ogr.FieldDefn(header_list[3], ogr.OFTString)
        time_field.SetWidth(20)  
        ptshp_layer.CreateField(time_field) 
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[4], ogr.OFTReal))      
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[5], ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[6], ogr.OFTReal))        
        ptshp_layer.CreateField(ogr.FieldDefn(header_list[7], ogr.OFTReal))        
        
        ptshp_featureDefn = ptshp_layer.GetLayerDefn()
        
        # loops through output records                       
        for rec in gpx_parsed_results:
            
            pt_feature = ogr.Feature(ptshp_featureDefn)
            
            pt = ogr.Geometry(ogr.wkbPoint)
            pt.SetPoint_2D(0, rec[2], rec[1])        
            pt_feature.SetGeometry(pt)
                    
            pt_feature.SetField(header_list[0], rec[0])
            pt_feature.SetField(header_list[1], rec[1])   
            pt_feature.SetField(header_list[2], rec[2])
                    
            pt_feature.SetField(header_list[3], str(rec[3]))
            if rec[4] != '': 
                pt_feature.SetField(header_list[4], str(rec[4])) 
            pt_feature.SetField(header_list[5], rec[5])
            if rec[6] != '': 
                pt_feature.SetField(header_list[6], rec[6])
            if rec[7] != '': 
                pt_feature.SetField(header_list[7], rec[7])
                                                              
            ptshp_layer.CreateFeature(pt_feature)
            
            pt_feature.Destroy()
            
        shp_datasource.Destroy()
                                
                                  
    def write_topography_allDEMs_lnshp(self, fileName, header_list, dem_names, export_data):

        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName(shape_driver_name)
        if shape_driver is None:
            self.warn("%s driver is not available" % shape_driver_name)
            return             
        
        try:    
            shp_datasource = shape_driver.CreateDataSource(unicode(fileName))
        except TypeError:
            shp_datasource = shape_driver.CreateDataSource(str(fileName))
            
        if shp_datasource is None:
            self.warn("Creation of %s shapefile failed" % os.path.split(fileName)[1])
            return         
        
        lnshp_layer = shp_datasource.CreateLayer('profile', geom_type = ogr.wkbLineString) 
        if lnshp_layer is None:
            self.warn("Output layer creation failed")
            return 
       
        # creates required fields         
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[0], ogr.OFTInteger))      
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[3], ogr.OFTReal))
        for dem_ndx in range(len(dem_names)):       
            lnshp_layer.CreateField(ogr.FieldDefn(header_list[3+dem_ndx*3+1], ogr.OFTReal)) 
            lnshp_layer.CreateField(ogr.FieldDefn(header_list[3+dem_ndx*3+2], ogr.OFTReal))       
            lnshp_layer.CreateField(ogr.FieldDefn(header_list[3+dem_ndx*3+3], ogr.OFTReal))
        
        lnshp_featureDefn = lnshp_layer.GetLayerDefn()

        field_names = []
        for i in range(lnshp_featureDefn.GetFieldCount()):
            field_names.append(lnshp_featureDefn.GetFieldDefn(i).GetName())
                
        # loops through output records                       
        for ndx in range(len(export_data) - 1):
            
            rec_a = export_data[ndx]
            rec_b = export_data[ndx+1]
            
            rec_a_x, rec_a_y = rec_a[1], rec_a[2]
            rec_b_x, rec_b_y = rec_b[1], rec_b[2]            
                        
            ln_feature = ogr.Feature(lnshp_featureDefn)
            
            segment_2d = ogr.CreateGeometryFromWkt('LINESTRING(%f %f, %f %f)' % (rec_a_x, rec_a_y, rec_b_x, rec_b_y))       
            ln_feature.SetGeometry(segment_2d) 
                      
            ln_feature.SetField(field_names[0], rec_a[0])
            ln_feature.SetField(field_names[1], rec_b[3])  
            for dem_ndx, dem_name in enumerate(dem_names):
                dem_height = rec_b[3+dem_ndx*3+1]
                if dem_height != '': 
                    ln_feature.SetField(field_names[1+dem_ndx*3+1], dem_height)
                cum3ddist = rec_b[3+dem_ndx*3+2]
                if cum3ddist != '': 
                    ln_feature.SetField(field_names[1+dem_ndx*3+2], cum3ddist)
                slope = rec_b[3+dem_ndx*3+3]
                if slope != '': 
                    ln_feature.SetField(field_names[1+dem_ndx*3+3], slope)                  
  
            lnshp_layer.CreateFeature(ln_feature)            
            ln_feature.Destroy()            
        shp_datasource.Destroy()
  

    def write_topography_singleDEM_lnshp(self, fileName, header_list, export_data, current_dem_ndx): 
             
        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName(shape_driver_name)
        if shape_driver is None:
            self.warn("%s driver is not available" % shape_driver_name)
            return             
            
        try:
            lnshp_datasource = shape_driver.CreateDataSource(unicode(fileName))
        except TypeError:
            lnshp_datasource = shape_driver.CreateDataSource(str(fileName))
                        
        if lnshp_datasource is None:
            self.warn("Creation of %s shapefile failed" % os.path.split(fileName)[1])
            return         
        
        lnshp_layer = lnshp_datasource.CreateLayer('profile', geom_type=ogr.wkbLineString25D)
        if lnshp_layer is None:
            self.warn("Output layer creation failed")
            return     
                      
        # creates required fields          
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[0], ogr.OFTInteger))      
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[3], ogr.OFTReal))
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[5], ogr.OFTReal))
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[6], ogr.OFTReal))     
    
        lnshp_featureDefn = lnshp_layer.GetLayerDefn()
        
        # loops through output records   
                          
        for ndx in range(len(export_data)-1):
                
            rec_a = export_data[ndx]
            rec_b = export_data[ndx+1]
 
            rec_id = rec_a[0]                           
            x0, y0, z0 = rec_a[1], rec_a[2], rec_a[3+current_dem_ndx*3+1]
            x1, y1, z1 = rec_b[1], rec_b[2], rec_b[3+current_dem_ndx*3+1]
            cum3ddist = rec_b[3 + current_dem_ndx*3 + 2]
            slope_degr = rec_b[3 + current_dem_ndx*3 + 3]
                        
            if z0 == '' or z1 == '': 
                continue

            ln_feature = ogr.Feature(lnshp_featureDefn)            
            segment_3d = ogr.CreateGeometryFromWkt('LINESTRING(%f %f %f, %f %f %f)' % (x0, y0, z0, x1, y1, z1))       
            ln_feature.SetGeometry(segment_3d) 
            
            ln_feature.SetField(header_list[0], rec_id)
            ln_feature.SetField(header_list[3], rec_b[3])              

            if cum3ddist != '': 
                ln_feature.SetField(header_list[5], cum3ddist)            

            if slope_degr != '': 
                ln_feature.SetField(header_list[6], slope_degr)       
                                       
            lnshp_layer.CreateFeature(ln_feature)            
            ln_feature.Destroy()            
        lnshp_datasource.Destroy()
      
        
    def write_topography_GPX_lnshp(self, output_filepath, header_list, gpx_parsed_results):
    
        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName(shape_driver_name)
        if shape_driver is None:
            self.warn("%s driver is not available" % shape_driver_name)
            return             
        
        try:    
            lnshp_datasource = shape_driver.CreateDataSource(unicode(output_filepath))
        except TypeError:
            lnshp_datasource = shape_driver.CreateDataSource(str(output_filepath))
                        
        if lnshp_datasource is None:
            self.warn("Creation of %s shapefile failed" % os.path.split(output_filepath)[1])
            return         
        
        lnshp_layer = lnshp_datasource.CreateLayer('profile', geom_type=ogr.wkbLineString25D)
        if lnshp_layer is None:
            self.warn("Output layer creation failed")
            return     
       
        # creates required fields         
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[0], ogr.OFTInteger))
        time_beg_field = ogr.FieldDefn('time_beg', ogr.OFTString)
        time_beg_field.SetWidth(20)  
        lnshp_layer.CreateField(time_beg_field)
        time_end_field = ogr.FieldDefn('time_end', ogr.OFTString)
        time_end_field.SetWidth(20)  
        lnshp_layer.CreateField(time_end_field)     
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[5], ogr.OFTReal))
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[6], ogr.OFTReal))
        lnshp_layer.CreateField(ogr.FieldDefn(header_list[7], ogr.OFTReal))     
    
        lnshp_featureDefn = lnshp_layer.GetLayerDefn()
        
        # loops through output records                     
        for ndx in range(len(gpx_parsed_results)-1):
                
            rec_a = gpx_parsed_results[ndx]
            rec_b = gpx_parsed_results[ndx+1]
                            
            lon0, lat0, z0 = rec_a[2], rec_a[1], rec_a[4]
            lon1, lat1, z1 = rec_b[2], rec_b[1], rec_b[4]
            
            if z0 == '' or z1 == '': 
                continue

            ln_feature = ogr.Feature(lnshp_featureDefn)            
            segment_3d = ogr.CreateGeometryFromWkt('LINESTRING(%f %f %f, %f %f %f)' % (lon0, lat0, z0, lon1, lat1, z1))       
            ln_feature.SetGeometry(segment_3d) 
              
            ln_feature.SetField(header_list[0], rec_a[0])
            ln_feature.SetField('time_beg', str(rec_a[3])) 
            ln_feature.SetField('time_end', str(rec_b[3]))           
            ln_feature.SetField(header_list[5], rec_b[5])  
            if rec_b[6] != '': 
                ln_feature.SetField(header_list[6], rec_b[6])
            if rec_b[7] != '': 
                ln_feature.SetField(header_list[7], rec_b[7])  
                            
            lnshp_layer.CreateFeature(ln_feature)
            
            ln_feature.Destroy()
            
        lnshp_datasource.Destroy()        

           
    def select_input_gpxFile(self):
            
        fileName = QFileDialog.getOpenFileName(self, 
                                                self.tr("Open GPX file"), 
                                                lastUsedDir(), 
                                                "GPX (*.gpx *.GPX)")
        if not fileName:
            return
        setLastUsedDir(fileName)    
        self.input_gpx_lineEdit.setText(fileName)


    def check_GPX_profile_parameters(self):
        
        source_gpx_path = unicode(self.input_gpx_lineEdit.text())
        if source_gpx_path == '':
            return False, 'Source GPX file is not set'

        plot_height_choice = self.GPX_plot_height_checkbox.isChecked()
        plot_slope_choice = self.GPX_plot_slope_checkbox.isChecked()
        
        if not (plot_height_choice or plot_slope_choice):
            return False, 'One of height or slope plot options are to be chosen'        
        
        return True, 'OK'
    
        
    def create_topo_profile_from_GPX(self):

        preliminar_check = self.check_GPX_profile_parameters()
        
        if not preliminar_check[0]:
            self.warn(preliminar_check[1])
            return   
        
        source_gpx_path = unicode(self.input_gpx_lineEdit.text())
         
        try:       
            self.profile_GPX = self.calculate_profile_from_GPX(source_gpx_path)
        except GPXIOException, msg:
            self.profile_GPX = None
            self.warn(msg)
            return 
        
        self.plot_GPX_profile(self.profile_GPX)  
        
 
    def calculate_profile_from_GPX(self, source_gpx_path):
                                 
        doc = xml.dom.minidom.parse(source_gpx_path)

        # define track name
        try:
            trkname = doc.getElementsByTagName('trk')[0].getElementsByTagName('name')[0].firstChild.data
        except:
            trkname = ''

        # get raw track point values (lat, lon, elev, time)
        track_raw_data = []
        for trk_node in doc.getElementsByTagName('trk'):
            for trksegment in trk_node.getElementsByTagName('trkseg'):
                for tkr_pt in trksegment.getElementsByTagName('trkpt'):
                    track_raw_data.append((tkr_pt.getAttribute("lat"),
                                       tkr_pt.getAttribute("lon"),
                                       tkr_pt.getElementsByTagName("ele")[0].childNodes[0].data,
                                       tkr_pt.getElementsByTagName("time")[0].childNodes[0].data))

        # filters out consecutive values with equal positions
        track_data = []
        for n, val in enumerate(track_raw_data):
            if n == 0:
                track_data.append(val)
            else:
                lat_curr, lon_curr = val[0], val[1]
                lat_prev, lon_prev = track_data[-1][0], track_data[-1][1]
                if lat_curr != lat_prev or lon_curr != lon_prev:
                    track_data.append(val)

        # create list of TrackPointGPX elements
        track_points = []
        for val in track_data:
            gpx_trackpoint = TrackPointGPX(*val)
            track_points.append(gpx_trackpoint)

        # check for the presence of track points
        if len(track_points) == 0:
            raise GPXIOException, "No track point found in this file"            
        
        # calculate delta elevations between consecutive points
        delta_elev_values = [np.nan]
        for ndx in range(1, len (track_points)):
            delta_elev_values.append(track_points[ndx].elev - track_points[ndx-1].elev)
        
        # covert values into ECEF values (x, y, z in ECEF global coordinate system)        
        trk_ECEFpoints = [trk_value.toPoint4D() for trk_value in  track_points]
        
        # calculate 3D distances between consecutive points
        dist_3D_values = [np.nan]
        for ndx in range(1, len (trk_ECEFpoints)):
            dist_3D_values.append(trk_ECEFpoints[ndx].distance(trk_ECEFpoints[ndx-1])) 
                    
        # calculate slope along track
        slopes = []
        for delta_elev, dist_3D in zip(delta_elev_values, dist_3D_values):
            try:
                slopes.append(degrees(asin(delta_elev / dist_3D)))
            except:
                slopes.append(np.nan) 
        
        # calculate horizontal distance along track
        horiz_dist_values = []
        for slope, dist_3D in zip(slopes, dist_3D_values):
            try:
                horiz_dist_values.append(dist_3D * cos(radians(slope)))
            except: 
                horiz_dist_values.append(np.nan)
                        
        # defines the cumulative 2D distance values
        cum_distances_2D = [0.0]
        for ndx in range(1, len(horiz_dist_values)):
            cum_distances_2D.append(cum_distances_2D[-1] + horiz_dist_values[ndx])          

        # defines the cumulative 3D distance values
        cum_distances_3D = [0.0]
        for ndx in range(1, len(dist_3D_values)):
            cum_distances_3D.append(cum_distances_3D[-1] + dist_3D_values[ndx]) 
            
        # define GPX names, elevations and slopes
        dataset_name = [trkname]
        lat_values = [track.lat for track in track_points]
        lon_values = [track.lon for track in track_points]
        time_values = [track.time for track in track_points]
        elevations = [track.elev for track in track_points]
        
        # define variable for plotting                
        profiles = dict( lats=lat_values,
                          lons=lon_values,
                          times=time_values,
                          dataset_names=dataset_name,
                          cum_distances_2D=cum_distances_2D,
                          cum_distances_3D=[cum_distances_3D], # [] required for compatibility with DEM plotting
                          elevations=[elevations], # [] required for compatibility with DEM plotting
                          slopes=[slopes]) # [] required for compatibility with DEM plotting

        return profiles


    def plot_GPX_profile(self, profiles):
 
        dataset_names = profiles['dataset_names']
        cum_distances_2D = profiles['cum_distances_2D']
        elevations = profiles['elevations']
        slopes = profiles['slopes']
                               
        # defines the extent for the plot window: s min and max     
        profiles_s_min, profiles_s_max = cum_distances_2D[0], cum_distances_2D[-1] 

        # defines z min and max values
        elev_list = [z for z_values in elevations for z in z_values if not isnan(z)]
        plot_z_min, plot_z_max = min(elev_list), max(elev_list)
        delta_z = plot_z_max - plot_z_min 
        plot_z_min, plot_z_max = plot_z_min - delta_z * 0.05, plot_z_max + delta_z * 0.05

        # defines slope min and max values
        slope_list = [slope for profile_slopes in slopes for slope in profile_slopes if not isnan(slope)]
        profiles_slope_min, profiles_slope_max = min(slope_list), max(slope_list)
        delta_slope = profiles_slope_max - profiles_slope_min 
        profiles_slope_min, profiles_slope_max = profiles_slope_min - delta_slope*0.2, profiles_slope_max + delta_slope*0.2 

        # map
        profile_window = MplWidget()  

        plot_height_choice = self.GPX_plot_height_checkbox.isChecked()
        plot_slope_choice = self.GPX_plot_slope_checkbox.isChecked() 
            
        if plot_height_choice and plot_slope_choice:
            mpl_code_list = [211, 212]
        else:
            mpl_code_list = [111]          

        s_2d_values_array = np.array(cum_distances_2D)
        
        subplot_code = mpl_code_list[0]   
        if plot_height_choice:                            
            axes_height = profile_window.canvas.fig.add_subplot(subplot_code)
            axes_height.set_xlim(profiles_s_min, profiles_s_max)
            axes_height.set_ylim(plot_z_min, plot_z_max) 
            axes_height.set_color_cycle(qprof_QWidget.colors)
            for dem_name, z_values, color in zip(dataset_names, elevations, qprof_QWidget.colors):              
                z_values_array = np.array(z_values)
                for val_int in valid_intervals(z_values_array):               
                    axes_height.fill_between(s_2d_values_array[val_int['start'] : val_int['end']+1], 
                                              plot_z_min, 
                                              z_values_array[val_int['start'] : val_int['end']+1], 
                                              facecolor=color, 
                                              alpha=0.1)                       
                axes_height.plot(cum_distances_2D, z_values,'-', label = unicode(dem_name))
                
            axes_height.grid(True)
            axes_height.legend(loc = 'upper left', shadow=True)              
  
        if plot_slope_choice:            
            if len(mpl_code_list) == 2: subplot_code = mpl_code_list[1]
            axes_slope = profile_window.canvas.fig.add_subplot(subplot_code)
            axes_slope.set_xlim(profiles_s_min, profiles_s_max)
            axes_slope.set_ylim(profiles_slope_min, profiles_slope_max)
            axes_slope.set_color_cycle(qprof_QWidget.colors)
            for dem_name, profile_slopes, color in zip(dataset_names, slopes, qprof_QWidget.colors):
                
                slope_values_array = np.array(profile_slopes) 
                for val_int in valid_intervals(slope_values_array):              
                    axes_slope.fill_between(s_2d_values_array[val_int['start'] : val_int['end']+1], 
                                             0, 
                                             slope_values_array[val_int['start'] : val_int['end']+1], 
                                             facecolor=color, 
                                             alpha=0.1)                
                axes_slope.plot(cum_distances_2D, profile_slopes,'-', label = unicode(dem_name))
                
            axes_slope.grid(True)
            axes_slope.legend(loc = 'upper left', shadow=True)  
                    
        profile_window.canvas.draw() 
        
        self.profile_windows.append(profile_window)
    
            
    def parse_GPX_results_for_export(self, GPXprofile):        

        # definition of output results        
        lat_list = GPXprofile['lats']
        lon_list = GPXprofile['lons'] 
        time_list = GPXprofile['times']          
        cumdist_2D_list = GPXprofile['cum_distances_2D']
        elev_list = GPXprofile['elevations'][0] # [0] required for compatibility with DEM processing                  
        cumdist_3d_list = GPXprofile['cum_distances_3D'][0] # [0] required for compatibility with DEM processing
        slope_list = GPXprofile['slopes'][0] # [0] required for compatibility with DEM processing

        result_data = []
        rec_id = 0
        for lat, lon, time, elev, cumdist_2D, cumdist_3D, slope in zip(lat_list, lon_list, time_list, elev_list, cumdist_2D_list, cumdist_3d_list, slope_list):
            rec_id += 1
            if isnan(elev): 
                elev = ''
            if isnan(cumdist_3D): 
                cumdist_3D = ''
            if isnan(slope): 
                slope = ''
            record = [rec_id, lat, lon, time, elev, cumdist_2D, cumdist_3D, slope]
            result_data.append(record)
        
        return result_data


    def update_point_layers_boxes(self):
        
        if len(self.pointLayers) == 0:
            return
        
        shape_qgis_ndx = self.prj_struct_point_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box
        if shape_qgis_ndx < 0: 
            return
        
        layer = self.pointLayers[shape_qgis_ndx]
        fields = layer.dataProvider().fields()     
        field_names = [field.name() for field in fields.toList()]
                
        for ndx, combobox in enumerate(self.flds_prj_point_comboBoxes):
            combobox.clear()
            if ndx == 0:
                combobox.addItems(["none"])
            combobox.addItems(field_names)


    def update_linepoly_layers_boxes(self):
        
        def update_field_combo_boxes():
            
            for combobox in field_combobox_list:
                combobox.clear()           
 
            if shape_qgis_ndx < 0 or len(layer_list) == 0: 
                return

            fields = layer_list[shape_qgis_ndx].dataProvider().fields()     
            field_names = [field.name() for field in fields.toList()]
                   
            for combobox in field_combobox_list:
                combobox.addItems(["none"] + field_names)            
        
        if self.sender() is self.prj_input_line_comboBox:
            shape_qgis_ndx = self.prj_input_line_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box
            field_combobox_list = self.flds_prj_line_comboBoxes 
            layer_list = self.current_line_layers           
        elif self.sender() is self.inters_input_line_comboBox:
            shape_qgis_ndx = self.inters_input_line_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box            
            field_combobox_list = self.flds_inters_line_comboBoxes   
            layer_list = self.current_line_layers     
        elif self.sender() is self.inters_input_polygon_comboBox:
            shape_qgis_ndx = self.inters_input_polygon_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box            
            field_combobox_list = self.flds_inters_polygon_comboBoxes   
            layer_list = self.current_polygon_layers   
                    
        update_field_combo_boxes()        
            
            
    def get_current_combobox_values(self, combobox_list):
        
        return [combobox.currentText() for combobox in combobox_list]


    def define_plot_structural_segment(self, structural_attitude, profile_length):
        
        slope_radians = structural_attitude.slope_rad
        intersection_downward_sense = structural_attitude.dwnwrd_sense
        intersection_point = structural_attitude.pt_3d
        horiz_distance = structural_attitude.sign_hor_dist        
        
        segment_horiz_scale_factor = 50.0   
        segment_emilength = profile_length / segment_horiz_scale_factor
        
        delta_height = segment_emilength * sin(float(slope_radians))
        delta_distance = segment_emilength * cos(float(slope_radians))
        
        z0 = intersection_point._z

        structural_segment_s = [horiz_distance - delta_distance, horiz_distance + delta_distance]
        structural_segment_z = [z0 + delta_height, z0 - delta_height]
                    
        if intersection_downward_sense == "left":
            structural_segment_z = [z0 - delta_height, z0 + delta_height]       
        
        return structural_segment_s, structural_segment_z
        

    def get_z_from_dem(self, struct_pts_2d, demObj):      
        
        z_list = []
        for point_2d in struct_pts_2d:
            interp_z = self.interpolate_z(demObj.layer, demObj.params, point_2d)
            z_list.append(interp_z)
            
        return z_list
            

    def calculate_pts_in_projection(self, pts_in_orig_crs, srcCrs, destCrs):

        pts_in_prj_crs = []
        for pt in pts_in_orig_crs:
            qgs_pt = qgs_point_2d(pt._x,pt._y)
            qgs_pt_prj_crs = project_qgs_point(qgs_pt, srcCrs, destCrs)
            pts_in_prj_crs.append( Point3D(qgs_pt_prj_crs.x(), qgs_pt_prj_crs.y()))        
        return pts_in_prj_crs
        

    def calculate_projected_3d_pts(self, struct_pts, structural_pts_crs, demObj):

        demCrs = demObj.params.crs
                        
        # check if on-the-fly-projection is set on
        on_the_fly_projection, project_crs = self.get_on_the_fly_projection()

        # set points in the project crs                    
        if on_the_fly_projection and structural_pts_crs != project_crs:
            struct_pts_in_prj_crs = self.calculate_pts_in_projection(struct_pts, structural_pts_crs, project_crs)
        else:
            struct_pts_in_prj_crs = copy.deepcopy(struct_pts)    
        
        # project the source points from point layer crs to DEM crs
        # if the two crs are different       
        if structural_pts_crs != demCrs:
            struct_pts_in_dem_crs = self.calculate_pts_in_projection(struct_pts, structural_pts_crs, demCrs)
        else:
            struct_pts_in_dem_crs = copy.deepcopy(struct_pts)    
            
        # - 3D structural points, with x, y, and z extracted from the current DEM
        struct_pts_z = self.get_z_from_dem(struct_pts_in_dem_crs, demObj)
        
        assert len(struct_pts_in_prj_crs) == len(struct_pts_z)
        
        return [Point3D(pt._x,pt._y,z) for (pt,z) in zip(struct_pts_in_prj_crs, struct_pts_z)] 
       

    def calculate_section_data(self):
        
        sect_pt_1, sect_pt_2 = self.used_profile_line._pts
        
        section_init_pt = Point3D(sect_pt_1._x, sect_pt_1._y, 0.0)
        section_final_pt = Point3D(sect_pt_2._x, sect_pt_2._y, 0.0)

        section_final_pt_up = Point3D(section_final_pt._x, section_final_pt._y, 1000.0) # arbitrary point on the same vertical as sect_pt_2    
        section_cartes_plane = CartesianPlane.from_points(section_init_pt, section_final_pt, section_final_pt_up)    
        section_vector = Segment3D(section_init_pt, section_final_pt).vector3d()
        
        return { 'init_pt': section_init_pt, 'cartes_plane': section_cartes_plane, 'vector': section_vector }
                             

    def get_mapping_method(self):
        
        if self.nearest_point_proj_choice.isChecked ():
            return { 'method': 'nearest' }
        
        if self.axis_common_point_proj_choice.isChecked ():
            return { 'method': 'common axis', 
                     'trend': float(self.common_axis_point_trend_SpinBox.value()),
                     'plunge': float(self.common_axis_point_plunge_SpinBox.value())}
        
        if self.axis_individual_point_proj_choice.isChecked ():
            return { 'method': 'individual axes', 
                     'trend field': unicode(self.proj_point_indivax_trend_fld_comboBox.currentText()),
                     'plunge field': unicode(self.proj_point_indivax_plunge_fld_comboBox.currentText())}          


    def check_struct_point_proj_parameters(self):
        
        # check if profile exists
        if self.used_profile_line is None:
            return False, "Profile not calculated"
        
        # check that section is made up of only two points
        if self.used_profile_line.num_points() != 2:
            return False, "Profile not made up by only two points"
                        
        # dem number
        if len(self.profiles.topo_profiles) > 1:           
            return False, "One DEM (and only one DEM) has to be in the profile section" 

        # get point structural layer with parameter fields
        prj_struct_point_qgis_ndx = self.prj_struct_point_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box
        if prj_struct_point_qgis_ndx < 0:            
            return False, "No defined point layer for structural data"
        
        return True, "OK"
    
                                                                         
    def create_struct_point_projection(self):

        parameters_check_ok, parameters_check_msg = self.check_struct_point_proj_parameters()
        if not parameters_check_ok:
            self.warn(parameters_check_msg)          
            return            

        # get color for projected points
        color = self.proj_point_color_comboBox.currentText()

        # define structural layer 
        prj_struct_point_qgis_ndx = self.prj_struct_point_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box       
        structural_layer = self.pointLayers[prj_struct_point_qgis_ndx]
        structural_layer_crs = structural_layer.crs()
        structural_field_list = self.get_current_combobox_values(self.flds_prj_point_comboBoxes) 
                  
        # retrieve selected structural points with their attributes        
        structural_pts_attrs = pt_geoms_attrs(structural_layer, structural_field_list) 
                             
        # list of structural points with original crs
        struct_pts_in_orig_crs = [Point3D(rec[0], rec[1]) for rec in structural_pts_attrs]
        
        # IDs of structural points
        struct_pts_ids = [rec[2] for rec in structural_pts_attrs]
        
        # - geological planes (3D), as geological planes
        try:
            structural_planes = [GeolPlane(rec[3], rec[4]) for rec in structural_pts_attrs]
        except:
            self.warn("Check defined fields for possible errors")          
            return
        
        struct_pts_3d = self.calculate_projected_3d_pts(struct_pts_in_orig_crs,
                                                        structural_layer_crs,
                                                        self.profiles.dems_params[0])

        # - zip together the point value data sets                     
        assert len(struct_pts_3d) == len(structural_planes)
        structural_data = zip(struct_pts_3d, structural_planes, struct_pts_ids)   
               
        ### map points onto section ###
        
        # calculation of Cartesian plane expressing section plane        
        self.section_data = self.calculate_section_data()
        
        # calculation of projected structural points
        
        # get chosen mapping method
        mapping_method = self.get_mapping_method()
        if mapping_method['method'] == 'individual axes':
            trend_field_name, plunge_field_name = mapping_method['trend field'], mapping_method['plunge field']
            # retrieve structural points mapping axes        
            mapping_method['individual_axes_values'] = vect_attrs(structural_layer, [trend_field_name, plunge_field_name]) 

        self.profiles.add_plane_attitudes(map_struct_pts_on_section(structural_data, self.section_data, mapping_method))
        self.plane_attitudes_colors.append(color)
        ### plot structural points in section ###
        self.plot_profile_elements(self.vertical_exaggeration)


    def reset_struct_point_projection(self):
        
        try:
            self.profiles.plane_attitudes = []
            self.plane_attitudes_colors = []
        except:
            pass


    def check_structural_line_projection_inputs(self):

        dem_check, msg = self.check_src_dem_for_geological_profile()        
        if not dem_check:
            return False, msg
                        
        profile_check, msg = self.check_src_profile_for_geological_profile()
        if not profile_check:
            return False, msg

        # line structural layer with parameter fields
        prj_struct_line_qgis_ndx = self.prj_input_line_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box
        if prj_struct_line_qgis_ndx < 0:            
            return False, "No defined structural line layer"

        try:
            densify_distance = float(self.project_line_densify_distance_lineedit.text())
        except:
            return False, "No valid numeric value for densify line distance"
        else:
            if densify_distance <= 0.0:
                return False, "Densify line distance must be larger than zero"                
                        
        return True, "OK"

                                                     
    def create_struct_line_projection(self):

        # check input values
        input_values_ok, msg = self.check_structural_line_projection_inputs()
        if not input_values_ok:   
            self.warn(msg)                
            return

        # input dem parameters
        demLayer = self.profiles.dems_params[0].layer
        demParams = self.profiles.dems_params[0].params

        # get line structural layer
        prj_struct_line_qgis_ndx = self.prj_input_line_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box
        
        # get id field
        prj_struct_line_id_field_ndx = self.id_fld_line_prj_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box
        
        # define structural layer        
        structural_line_layer = self.current_line_layers[prj_struct_line_qgis_ndx]
         
        on_the_fly_projection, project_crs = self.get_on_the_fly_projection()
                  
        # read structural line values
        id_list = field_values(structural_line_layer, prj_struct_line_id_field_ndx)                
        line_proj_crs_MultiLine2D_list = self.extract_multiline2d_list(structural_line_layer, on_the_fly_projection, project_crs)
               
        # densify with provided distance
        densify_proj_crs_distance = float(self.project_line_densify_distance_lineedit.text())
        densified_proj_crs_MultiLine2D_list = [multiline_2d.densify(densify_proj_crs_distance) for multiline_2d in line_proj_crs_MultiLine2D_list]
                    
        # project to Dem CRS
        if on_the_fly_projection and demParams.crs != project_crs:
            densified_dem_crs_MultiLine2D_list = [multiline_2d.crs_project(project_crs, demParams.crs) for multiline_2d in densified_proj_crs_MultiLine2D_list]
        else:
            densified_dem_crs_MultiLine2D_list = densified_proj_crs_MultiLine2D_list
        
        # interpolate z values from Dem
        z_list = [self.interpolate_z(demLayer, demParams, pt_2d) for multiline_2d in densified_dem_crs_MultiLine2D_list for line_2d in multiline_2d._lines for pt_2d in line_2d._pts]

        # extract x-y pairs for creation of 3D points 
        xy_list = [(pt_2d._x, pt_2d._y) for multiline_2d in densified_proj_crs_MultiLine2D_list for line_2d in multiline_2d._lines for pt_2d in line_2d._pts]
                            
        # replicate MultiLine list structure with 3D points with project CRS
        ndx = -1
        multiline_3d_proj_crs_list = []
        for multiline_2d in densified_proj_crs_MultiLine2D_list:
            multiline_3d_list = []
            for line_2d in multiline_2d._lines:
                line_3d_pts_list = []
                for pt_2d in line_2d._pts:
                    ndx += 1
                    line_3d_pts_list.append(Point3D(xy_list[ndx][0], xy_list[ndx][1], z_list[ndx]))
                multiline_3d_list.append(Line3D(line_3d_pts_list))
            multiline_3d_proj_crs_list.append(MultiLine3D(multiline_3d_list))

        # create projection vector        
        trend = float(self.common_axis_line_trend_SpinBox.value())
        plunge = float(self.common_axis_line_plunge_SpinBox.value())
        axis_versor = GeolAxis(trend, plunge).versor_3d()
        l, m, n = axis_versor._x, axis_versor._y, axis_versor._z
        
        # calculation of Cartesian plane expressing section plane        
        self.section_data = self.calculate_section_data()
                
        # project MultiLine3D points to section
        intersection_point_list = []
        for multiline_3d in multiline_3d_proj_crs_list:
            for line_3d in multiline_3d._lines:
                for pt_3d in line_3d._pts:
                    srcPt = pt_3d
                    param_line = ParamLine(srcPt, l, m, n)
                    intersection_point_list.append(param_line.intersect_cartes_plane(self.section_data['cartes_plane']))
                                     
        # replicate MultiLine list structure with 3D points with project CRS
        ndx = -1
        multiline_3d_proj_crs_section_list = []
        for multiline_3d in multiline_3d_proj_crs_list:
            multiline_3d_list = []
            for line_3d in multiline_3d._lines:
                line_3d_pts_list = []
                for pt_3d in line_3d._pts:
                    ndx += 1
                    line_3d_pts_list.append(intersection_point_list[ndx]) 
                multiline_3d_list.append(Line3D(line_3d_pts_list))
            multiline_3d_proj_crs_section_list.append(MultiLine3D(multiline_3d_list))
        

        section_start_point, section_vector = self.section_data['init_pt'], self.section_data['vector']
        curves_2d_list = []
        for multiline_3d in multiline_3d_proj_crs_section_list:
            multiline_2d_list = []
            for line_3d in multiline_3d._lines:
                line_2d_pts_list = []
                for pt_3d in line_3d._pts:
                    s = calculate_distance_with_sign(pt_3d, section_start_point, section_vector)
                    z = pt_3d._z
                    line_2d_pts_list.append(Point2D(s, z))
                multiline_2d_list.append(Line2D(line_2d_pts_list))
            curves_2d_list.append(MultiLine2D(multiline_2d_list))
        
                       
        self.profiles.add_curves(curves_2d_list, id_list)
                                       
        # plot new cross section
        self.plot_profile_elements(self.vertical_exaggeration)


    def reset_structural_lines_projection(self):
        
        try:
            self.profiles.curves = []
            self.profiles.curves_ids = []
            self.curve_colors = []
        except:
            pass
        

    def parse_geologicalattitudes_results_for_export(self, plane_attitudes_datasets):

        result_data = []  
              
        for dataset in plane_attitudes_datasets:  
                      
            for plane_attitude_rec in dataset:
                
                pt_id = plane_attitude_rec.id
                or_pt_x = plane_attitude_rec.src_pt_3d._x
                or_pt_y = plane_attitude_rec.src_pt_3d._y            
                or_pt_z = plane_attitude_rec.src_pt_3d._z            
                pr_pt_x = plane_attitude_rec.pt_3d._x
                pr_pt_y = plane_attitude_rec.pt_3d._y            
                pr_pt_z = plane_attitude_rec.pt_3d._z            
                s = plane_attitude_rec.sign_hor_dist
                or_dipdir = plane_attitude_rec.src_geol_plane._dipdir
                or_dipangle = plane_attitude_rec.src_geol_plane._dipangle
                tr_dipangle = degrees(plane_attitude_rec.slope_rad)
                tr_dipdir = plane_attitude_rec.dwnwrd_sense
                
                record = [pt_id, or_pt_x, or_pt_y, or_pt_z, pr_pt_x, pr_pt_y, pr_pt_z, s, or_dipdir, or_dipangle, tr_dipangle, tr_dipdir]

                result_data.append(record)
         
        return result_data


    def parse_geologicalcurves_for_export(self):
        
        data_list = []
        for curve_set, id_set in zip(self.profiles.curves, self.profiles.curves_ids):
            for curve, rec_id in zip(curve_set, id_set):
                for line in curve._lines:
                    for pt in line._pts:
                        data_list.append([rec_id, pt._x, pt._y])
        return data_list
     

               
    def write_geological_attitudes_ptshp(self, fileName, header_list, parsed_crosssect_results):


        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName(shape_driver_name)
        if shape_driver is None:
            self.warn("%s driver is not available" % shape_driver_name)
            return

        try:
            shp_datasource = shape_driver.CreateDataSource(unicode(fileName))
        except TypeError:
            shp_datasource = shape_driver.CreateDataSource(str(fileName))
            
        if shp_datasource is None:
            self.warn("Creation of %s shapefile failed" % os.path.split(fileName)[1])
            return

        ptshp_layer = shp_datasource.CreateLayer('profile', geom_type=ogr.wkbPoint25D)
        if ptshp_layer is None:
            self.warn("Output layer creation failed")
            return

        # creates required fields
        ptshp_layer.CreateField(ogr.FieldDefn('id', ogr.OFTString))
        ptshp_layer.CreateField(ogr.FieldDefn('or_pt_x', ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn('or_pt_y', ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn('or_pt_z', ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn('prj_pt_x', ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn('prj_pt_y', ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn('prj_pt_z', ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn('s', ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn('or_dpdir', ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn('or_dpang', ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn('tr_dpang', ogr.OFTReal))
        ptshp_layer.CreateField(ogr.FieldDefn('tr_dpdir', ogr.OFTString))

        ptshp_featureDefn = ptshp_layer.GetLayerDefn()

        # loops through output records
        for rec in parsed_crosssect_results:

            pt_id, or_pt_x, or_pt_y, or_pt_z, pr_pt_x, pr_pt_y, pr_pt_z, s, or_dipdir, or_dipangle, tr_dipangle, tr_dipdir = rec

            pt_feature = ogr.Feature(ptshp_featureDefn)

            pt = ogr.Geometry(ogr.wkbPoint25D)
            pt.SetPoint(0, pr_pt_x, pr_pt_y, pr_pt_z)
            pt_feature.SetGeometry(pt)

            pt_feature.SetField('id', str(pt_id))
            pt_feature.SetField('or_pt_x', or_pt_x)
            pt_feature.SetField('or_pt_y', or_pt_y)
            pt_feature.SetField('or_pt_z', or_pt_z)
            pt_feature.SetField('prj_pt_x', pr_pt_x)
            pt_feature.SetField('prj_pt_y', pr_pt_y)
            pt_feature.SetField('prj_pt_z', pr_pt_z)
            pt_feature.SetField('s', s)
            pt_feature.SetField('or_dpdir',or_dipdir)
            pt_feature.SetField('or_dpang', or_dipangle)
            pt_feature.SetField('tr_dpang', tr_dipangle)
            pt_feature.SetField('tr_dpdir', str(tr_dipdir))

            ptshp_layer.CreateFeature(pt_feature)

            pt_feature.Destroy()

        shp_datasource.Destroy()


    def plot_profile_elements(self, aspect_ratio_numerator, elev_type="DEM", z_padding = 0.2, slope_padding = 0.2):
         
        def min_wo_nan(float_list):

            return min([f for f in float_list if not isnan(f)])
        
        def max_wo_nan(float_list):
            
            return max([f for f in float_list if not isnan(f)])
        
                                      
        # defines the extent for the plot window: s min and max     
        plot_s_min, plot_s_max = 0, self.profiles.get_max_s() 

        # defines z min and max values
        if self.plot_min_value_user is None or \
         self.plot_max_value_user is None:
            profile_z_min = self.profiles.get_min_z()
            profile_z_max = self.profiles.get_max_z()
            delta_z = profile_z_max - profile_z_min

        if self.plot_min_value_user is None:
            plot_z_min = profile_z_min - delta_z * z_padding
        else:
            plot_z_min = self.plot_min_value_user

        if self.plot_max_value_user is None:
            plot_z_max = profile_z_max + delta_z * z_padding
        else:
            plot_z_max = self.plot_max_value_user

        if plot_z_max < plot_z_min:
            self.warn("Error: maximum plot value lower than minimum plot value")
            return

        # if slopes to be calculated and plotted
        if self.DEM_plot_slope_checkbox.isChecked():
            # defines slope value lists and the min and max values
            if self.DEM_plot_slope_absolute_qradiobutton.isChecked():
                slope_list = [topo_profile.profile_3d.slopes_absolute_list() for topo_profile in self.profiles.topo_profiles]
            else:
                slope_list = [topo_profile.profile_3d.slopes_list() for topo_profile in self.profiles.topo_profiles]

            profiles_slope_min, profiles_slope_max = min_wo_nan([min_wo_nan(slist) for slist in slope_list]), max_wo_nan([max_wo_nan(slist) for slist in slope_list])
            delta_slope = profiles_slope_max - profiles_slope_min
            plot_slope_min, plot_slope_max = profiles_slope_min - delta_slope*slope_padding, profiles_slope_max + delta_slope*slope_padding

        # map
        profile_window = MplWidget()  

        if elev_type == 'DEM':
            plot_height_choice = self.DEM_plot_height_checkbox.isChecked()
            plot_slope_choice = self.DEM_plot_slope_checkbox.isChecked() 
        elif elev_type == 'GPX':
            plot_height_choice = self.GPX_plot_height_checkbox.isChecked()
            plot_slope_choice = self.GPX_plot_slope_checkbox.isChecked() 

        if plot_height_choice and plot_slope_choice:
            mpl_code_list = [211, 212]
        else:
            mpl_code_list = [111]            
        subplot_code = mpl_code_list[0] 
  
        if plot_height_choice:
            
            self.axes_elevation = self.plot_topo_profile_lines(subplot_code, 
                                                                  profile_window, 
                                                                  self.profiles.topo_profiles, 
                                                                  'elevation', 
                                                                  (plot_s_min, plot_s_max), 
                                                                  (plot_z_min, plot_z_max),
                                                                  self.selected_dem_colors,
                                                                  self.DEM_plot_height_filled_checkbox.isChecked())
            
            self.axes_elevation.set_aspect(aspect_ratio_numerator)
            
        if plot_slope_choice:
                        
            if len(mpl_code_list) == 2: 
                subplot_code = mpl_code_list[1]  
                          
            self.axes_slopes = self.plot_topo_profile_lines(subplot_code, 
                                                              profile_window, 
                                                              self.profiles.topo_profiles, 
                                                              'slope', 
                                                              (plot_s_min, plot_s_max), 
                                                              (plot_slope_min, plot_slope_max), 
                                                              self.selected_dem_colors,
                                                              self.DEM_plot_slope_filled_checkbox.isChecked())
                                        
        if len(self.profiles.intersection_lines) > 0:
            
            for line_intersection_value in self.profiles.intersection_lines:
                self.plot_profile_polygon_intersection_line(self.axes_elevation, line_intersection_value)
                        
        if len(self.profiles.plane_attitudes) > 0: 
                       
            for plane_attitude_set, color in zip(self.profiles.plane_attitudes, self.plane_attitudes_colors):                
                self.plot_structural_attitude(self.axes_elevation, plot_s_max, plane_attitude_set, color)                   
                   
        if len(self.profiles.curves) > 0: 

            for curve_set, labels in zip(self.profiles.curves, self.profiles.curves_ids) :                
                self.plot_projected_line_set(self.axes_elevation, curve_set, labels)          

        if len(self.profiles.intersection_pts) > 0:
            
            self.plot_profile_lines_intersection_points(self.axes_elevation, self.profiles.intersection_pts)

        profile_window.canvas.draw() 
        
        self.profile_windows.append(profile_window)


    def plot_topo_profile_lines(self, subplot_code, profile_window, topo_profiles, topo_type, plot_x_range, plot_y_range, dem_colors, filled_choice):
        
        axes = self.create_axes(subplot_code,
                                  profile_window, 
                                  plot_x_range, 
                                  plot_y_range)

        if self.swap_xaxis_checkbox.isChecked():
            axes.invert_xaxis()
                
        # label = unicode(dem_name)
        for topo_profile, dem_color in zip(topo_profiles, dem_colors): 
            
            if topo_type == 'elevation':
                y_list = topo_profile.z_list()
                plot_y_min = plot_y_range[0]
            elif topo_type == 'slope':
                if self.DEM_plot_slope_absolute_qradiobutton.isChecked():
                    y_list = topo_profile.slope_absolute_list() 
                else:   
                    y_list = topo_profile.slope_list()
                
                plot_y_min = 0.0
            
            if filled_choice:    
                plot_filled_line(axes,
                                topo_profile.get_increm_dist_2d(), 
                                y_list, 
                                plot_y_min, 
                                dem_color)
                
            plot_line(axes,
                        topo_profile.get_increm_dist_2d(), 
                        y_list, 
                        dem_color) 

        return axes
    
    
    def create_axes(self, subplot_code, profile_window, plot_x_range, plot_y_range):

            x_min, x_max = plot_x_range
            y_min, y_max = plot_y_range
            axes = profile_window.canvas.fig.add_subplot(subplot_code)
            axes.set_xlim(x_min, x_max)
            axes.set_ylim(y_min, y_max)

            axes.grid(True)
                       
            return axes
                

    def plot_profile_lines_intersection_points(self, axes, profile_lines_intersection_points):

        for s, pt3d, intersection_id in profile_lines_intersection_points:
            axes.plot(s, pt3d._z,'o', color="blue") 
            if str(intersection_id).upper() != "NULL":
                axes.annotate(str(intersection_id), (s + 25, pt3d._z + 25))   
            

    def line_intersection_reset(self):
        
        self.profiles.intersection_pts = []
        
                            
    def polygon_intersection_reset(self):
        
        self.profiles.intersection_lines = []


    def plot_structural_attitude(self, axes, section_length, structural_attitude_list, color):
        
        # TODO:  manage case for possible nan z values
        projected_z = [structural_attitude.pt_3d._z for structural_attitude in structural_attitude_list if  0.0 <= structural_attitude.sign_hor_dist <= section_length]
                 
        # TODO:  manage case for possible nan z values
        projected_s = [structural_attitude.sign_hor_dist for structural_attitude in structural_attitude_list if 0.0 <= structural_attitude.sign_hor_dist <= section_length]
        
        projected_ids = [structural_attitude.id for structural_attitude in structural_attitude_list if 0.0 <= structural_attitude.sign_hor_dist <= section_length]
        
                
        axes.plot(projected_s, projected_z,'o', color=color) 
        
        # plot segments representing structural data       
        for structural_attitude in structural_attitude_list:
            if 0.0 <= structural_attitude.sign_hor_dist <= section_length:
                structural_segment_s, structural_segment_z = self.define_plot_structural_segment(structural_attitude, section_length)            
                
                axes.plot(structural_segment_s, structural_segment_z,'-', color=color)
        
        if self.plot_prj_add_trendplunge_label.isChecked() or self.plot_prj_add_pt_id_label.isChecked():
            
            src_dip_dirs = [structural_attitude.src_geol_plane._dipdir for structural_attitude in structural_attitude_list if 0.0 <= structural_attitude.sign_hor_dist <= section_length]
            src_dip_angs = [structural_attitude.src_geol_plane._dipangle for structural_attitude in structural_attitude_list if 0.0 <= structural_attitude.sign_hor_dist <= section_length]
        
            for rec_id, src_dip_dir, src_dip_ang, s, z in zip(projected_ids, src_dip_dirs, src_dip_angs, projected_s, projected_z):
                
                if self.plot_prj_add_trendplunge_label.isChecked() and self.plot_prj_add_pt_id_label.isChecked():
                    label = "%s-%03d/%02d" % (rec_id, src_dip_dir, src_dip_ang)
                elif self.plot_prj_add_pt_id_label.isChecked():
                    label = "%s" % rec_id
                elif self.plot_prj_add_trendplunge_label.isChecked():
                    label = "%03d/%02d" % (src_dip_dir, src_dip_ang)
                    
                axes.annotate(label, (s + 15, z + 15))                    
            

    def plot_projected_line_set(self, axes, curve_set, labels):
               
        colors = qprof_QWidget.colors_addit * (int(len(curve_set) / len(qprof_QWidget.colors_addit))  + 1)
        for multiline_2d, label, color in zip(curve_set, labels, colors):
            for line_2d in multiline_2d._lines:
                plot_line(axes, line_2d.x_list(), line_2d.y_list(), color, name = label)
                

    def plot_profile_polygon_intersection_line(self, axes, intersection_line_value):
        
        classification, line3d, s_list = intersection_line_value        
        z_list = [pt3d._z for pt3d in line3d._pts]
        
        if self.polygon_classification_colors == None:
            color = "red"
        else:
            color = self.polygon_classification_colors[unicode(classification)]
            
        plot_line(axes, s_list, z_list, color, linewidth=3.0, name = classification)
                
 
    def check_src_dem_for_geological_profile(self):
        
        # dem parameters
        try:
            num_dems_in_profile = len(self.profiles.topo_profiles)
        except:
            return False, "Profile has not been calculated"
        else:
            if num_dems_in_profile == 0:
                return False, "Profile has not been calculated"
            elif num_dems_in_profile > 1:
                return False, "One DEM (and only one DEM) has to be used in the profile section"    
            
        return True, "ok"    
        
  
    def check_src_profile_for_geological_profile(self):
            
        # check if profile exists
        if self.used_profile_line is None:
            return False, "Profile has not been calculated"
        
        # check that section is made up of only two points
        if self.used_profile_line.num_points() != 2:
            return False, "Current profile is not made up by only two points"
        
        return True, "ok"           


    def check_intersection_polygon_inputs(self):
        
        dem_check, msg = self.check_src_dem_for_geological_profile()        
        if not dem_check:
            return False, msg        

        profile_check, msg = self.check_src_profile_for_geological_profile()
        if not profile_check:
            return False, msg        
        
        # polygon layer with parameter fields
        intersection_polygon_qgis_ndx = self.inters_input_polygon_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box
        if intersection_polygon_qgis_ndx < 0:            
            return False, "No defined polygon layer"             
                        
        return True, "OK"        
        
                  
    def check_intersection_line_inputs(self):

        dem_check, msg = self.check_src_dem_for_geological_profile()        
        if not dem_check:
            return False, msg
                        
        profile_check, msg = self.check_src_profile_for_geological_profile()
        if not profile_check:
            return False, msg
        
        # line structural layer with parameter fields
        intersection_line_qgis_ndx = self.inters_input_line_comboBox.currentIndex() - 1 # minus 1 in order to account for initial text in combo box
        if intersection_line_qgis_ndx < 0:            
            return False, "No defined geological line layer"             
                        
        return True, "OK"


    def extract_multiline2d_list(self, structural_line_layer, on_the_fly_projection, project_crs):
        
        line_orig_crs_geoms_attrs = line_geoms_attrs(structural_line_layer)
    
        
        line_orig_geom_list3 = [geom_data[0] for geom_data in line_orig_crs_geoms_attrs]
        line_orig_crs_MultiLine2D_list = [xytuple_list2_to_MultiLine2D(xy_list2) for xy_list2 in line_orig_geom_list3]
        line_orig_crs_clean_MultiLine2D_list = [multiline_2d.remove_coincident_points() for multiline_2d in line_orig_crs_MultiLine2D_list]

        # get CRS information
        structural_line_layer_crs = structural_line_layer.crs()
                
        # project input line layer to project CRS
        if on_the_fly_projection:
            line_proj_crs_MultiLine2D_list = [multiline2d.crs_project(structural_line_layer_crs, project_crs) for multiline2d in line_orig_crs_clean_MultiLine2D_list]
        else:
            line_proj_crs_MultiLine2D_list = line_orig_crs_clean_MultiLine2D_list
            
        return line_proj_crs_MultiLine2D_list
  

    def do_polygon_intersection(self):
        
        # check input values
        input_values_ok, msg = self.check_intersection_polygon_inputs()
        if not input_values_ok:   
            self.warn(msg)                
            return
 
        # get dem parameters
        demLayer = self.profiles.dems_params[0].layer
        demParams = self.profiles.dems_params[0].params
        
        # profile line2d, in project CRS and densified 
        profile_line2d_prjcrs_densif = self.used_profile_line.densify(self.sample_distance)
        
        # polygon layer
        intersection_polygon_qgis_ndx = self.inters_input_polygon_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box
        inters_polygon_classifaction_field_ndx = self.inters_polygon_classifaction_field_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box    
        polygon_layer = self.current_polygon_layers[intersection_polygon_qgis_ndx]
        polygon_layer_crs = polygon_layer.crs()
        
        on_the_fly_projection, project_crs = self.get_on_the_fly_projection() 
        
        if on_the_fly_projection and polygon_layer_crs != project_crs:        
            profile_line2d_polycrs_densif = line2d_change_crs(profile_line2d_prjcrs_densif, project_crs, polygon_layer_crs)
        else:
            profile_line2d_polycrs_densif = profile_line2d_prjcrs_densif
        
        profile_qgsgeometry = QgsGeometry.fromPolyline([QgsPoint(pt2d._x,pt2d._y) for pt2d in profile_line2d_polycrs_densif._pts])
        
        intersection_polyline_polygon_crs_list = self.profile_polygon_intersection(profile_qgsgeometry, polygon_layer, inters_polygon_classifaction_field_ndx)
        if len(intersection_polyline_polygon_crs_list) == 0:
            self.warn("No intersection found")
            return
        
        # transform polyline intersections into prj crs line2d & classification list
        intersection_line2d_prj_crs_list = []
        for intersection_polyline_polygon_crs in intersection_polyline_polygon_crs_list:
            rec_classification, xy_tuple_list = intersection_polyline_polygon_crs
            intersection_polygon_crs_line2d = xytuple_list_to_Line2D(xy_tuple_list)
            if on_the_fly_projection and polygon_layer_crs != project_crs:
                intersection_prj_crs_line2d = line2d_change_crs(intersection_polygon_crs_line2d, polygon_layer_crs, project_crs)
            else:
                intersection_prj_crs_line2d = intersection_polygon_crs_line2d
            intersection_line2d_prj_crs_list.append([rec_classification, intersection_prj_crs_line2d])
            
        
        # create Point3D lists from intersection with source DEM     

        polygon_classification_set = set()
        sect_pt_1, sect_pt_2 = self.used_profile_line._pts
        formation_list = []
        intersection_line3d_list = []
        intersection_polygon_s_list2 = []
        intersection_polygon_z_list2 = []
        for polygon_classification, line2d in intersection_line2d_prj_crs_list:

            polygon_classification_set.add(polygon_classification)            
                        
            intersection_line3d = Line3D(self.intersect_with_dem(demLayer, demParams, on_the_fly_projection, project_crs, line2d._pts))
            
            s0_list = intersection_line3d.incremental_length_2d()
            s_start = sect_pt_1.distance(intersection_line3d._pts[0])            
            s_list = [s + s_start for s in s0_list]
            
            formation_list.append(polygon_classification)
            intersection_line3d_list.append(intersection_line3d)
            intersection_polygon_s_list2.append(s_list)

        # create windows for user_definition of intersection colors in profile
        if polygon_classification_set != set() and polygon_classification_set != set([None]):
            
            dialog = PolygonIntersectionRepresentationDialog(polygon_classification_set)    
            if dialog.exec_():
                polygon_classification_colors_dict = self.classification_colors(dialog)
            else:
                self.warn("No color chosen")
                return                
            if  len(polygon_classification_colors_dict) == 0: 
                self.warn("No defined colors")
                return      
            else:
                self.polygon_classification_colors = polygon_classification_colors_dict
        else:
            self.polygon_classification_colors = None        
        
        self.profiles.add_intersections_lines(formation_list, intersection_line3d_list, intersection_polygon_s_list2)

        self.plot_profile_elements(self.vertical_exaggeration)


    def classification_colors(self, dialog):   

        polygon_classification_colors_dict = dict() 
        for classification_ndx in range(dialog.polygon_classifications_treeWidget.topLevelItemCount ()):
            class_itemwidget = dialog.polygon_classifications_treeWidget.topLevelItem (classification_ndx)
            classification = unicode(class_itemwidget.text(0))
            polygon_classification_colors_dict[classification] = dialog.polygon_classifications_treeWidget.itemWidget(class_itemwidget, 1).currentText()
        
        return polygon_classification_colors_dict
    

    def profile_polygon_intersection(self, profile_qgsgeometry, polygon_layer, inters_polygon_classifaction_field_ndx):

        intersection_polyline_polygon_crs_list = []

        if polygon_layer.selectedFeatureCount() > 0:
            features = polygon_layer.selectedFeatures()
        else:
            features = polygon_layer.getFeatures()

        for polygon_feature in features:
            # retrieve every (selected) feature with its geometry and attributes

            # fetch geometry
            poly_geom = polygon_feature.geometry()

            intersection_qgsgeometry = poly_geom.intersection(profile_qgsgeometry)

            if intersection_qgsgeometry.isEmpty():
                continue

            if inters_polygon_classifaction_field_ndx >= 0:
                attrs = polygon_feature.attributes()
                polygon_classification = attrs[inters_polygon_classifaction_field_ndx]
            else:
                polygon_classification = None

            if intersection_qgsgeometry.isMultipart():
                lines = intersection_qgsgeometry.asMultiPolyline()
            else:
                lines = [intersection_qgsgeometry.asPolyline()]

            for line in lines:
                intersection_polyline_polygon_crs_list.append([polygon_classification,  line])

        return intersection_polyline_polygon_crs_list
                           
         
    def do_line_intersection(self):

        # check input values
        input_values_ok, msg = self.check_intersection_line_inputs()
        if not input_values_ok:   
            self.warn(msg)                
            return
        
        # get dem parameters
        demLayer = self.profiles.dems_params[0].layer
        demParams = self.profiles.dems_params[0].params

        # get line structural layer
        intersection_line_qgis_ndx = self.inters_input_line_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box
        
        # get id field
        intersection_line_id_field_ndx = self.inters_input_id_fld_line_comboBox.currentIndex() - 1 # minus 1 in order to account for initial text in combo box
        
        # define structural layer        
        structural_line_layer = self.current_line_layers[intersection_line_qgis_ndx]
         
        on_the_fly_projection, project_crs = self.get_on_the_fly_projection() 
                          
        # read structural line values
        id_list = field_values(structural_line_layer, intersection_line_id_field_ndx)         
        line_proj_crs_MultiLine2D_list = self.extract_multiline2d_list(structural_line_layer, on_the_fly_projection, project_crs)

        # calculated Point2D intersection list
        intersection_point_id_list = self.calculate_profile_lines_intersection(line_proj_crs_MultiLine2D_list, id_list, self.used_profile_line)
                                            
        # sort intersection points by distance from profile start point 
        distances_from_profile_start_list = self.intersection_distances_by_profile_start_list(self.used_profile_line, intersection_point_id_list)

        # create Point3D from intersection with source DEM
        intersection_point_list = [pt2d for pt2d, _ in intersection_point_id_list]
        intersection_id_list = [id for _, id in intersection_point_id_list]
        intersection_point3d_list = self.intersect_with_dem(demLayer, demParams, on_the_fly_projection, project_crs, intersection_point_list)

        self.profiles.add_intersections_pts(zip(distances_from_profile_start_list, intersection_point3d_list, intersection_id_list))

        self.plot_profile_elements(self.vertical_exaggeration)
        

    def intersect_with_dem(self, demLayer, demParams, on_the_fly_projection, project_crs, intersection_point_list):

        # project to Dem CRS
        if on_the_fly_projection and demParams.crs != project_crs:            
            qgs_point2d_list = [qgs_point_2d(point2D._x, point2D._y) for point2D in intersection_point_list]
            dem_crs_intersection_qgispoint_list = [project_qgs_point(qgsPt, project_crs, demParams.crs) for qgsPt in qgs_point2d_list]
            dem_crs_intersection_point_list = [Point2D(qgispt.x(), qgispt.y()) for qgispt in dem_crs_intersection_qgispoint_list]
        else:
            dem_crs_intersection_point_list = intersection_point_list

        # interpolate z values from Dem
        z_list = [self.interpolate_z(demLayer, demParams, pt_2d) for pt_2d in dem_crs_intersection_point_list]

        return [Point3D(pt2d._x, pt2d._y, z) for pt2d, z in zip(intersection_point_list, z_list)]

    
    def calculate_profile_lines_intersection(self, multilines2d_list, id_list, profile_line2d):
        
        # debug
        assert len(multilines2d_list) == len(id_list)
        
        profile_segment2d_list = profile_line2d.to_segments()        
        # debug
        assert len(profile_segment2d_list) == 1
        profile_segment2d = profile_segment2d_list[0]
        
        intersection_list = []        
        for multiline2d, multiline_id in zip(multilines2d_list, id_list):
            for line2d in multiline2d._lines:
                for line_segment2d in line2d.to_segments():
                    try:
                        intersection_point2d = profile_segment2d.intersection_pt(line_segment2d)
                    except ZeroDivisionError:
                        continue
                    if intersection_point2d is None:
                        continue
                    if line_segment2d.contains_pt(intersection_point2d) and \
                       profile_segment2d.contains_pt(intersection_point2d):
                        intersection_list.append([intersection_point2d, multiline_id])        
        
        return intersection_list
        
            
    def intersection_distances_by_profile_start_list(self, profile_line, intersection_list):

        # convert the profile line
        # from a Line2D to a Segment2D
        profile_segment2d_list = profile_line.to_segments()        
        # debug
        assert len(profile_segment2d_list) == 1
        profile_segment2d = profile_segment2d_list[0]        
    
        # determine distances for each point in intersection list
        # creating a list of float values
        distance_from_profile_start_list = []
        for intersection_res in intersection_list:
            distance_from_profile_start_list.append(profile_segment2d._start_pt.distance(intersection_res[0]))

        return distance_from_profile_start_list
 

         
    def do_export_image(self):
                

        try:
            profile_window = self.profile_windows[-1]        
        except:
            self.warn("No profile available")
            return              
              
                    
        dialog = FigureExportDialog()

        if dialog.exec_():
    
            try:
                fig_width_inches = float(dialog.figure_width_inches_QLineEdit.text())
            except:
                self.warn("Error in figure width value")
                return
            
            try:
                fig_resolution_dpi = int(dialog.figure_resolution_dpi_QLineEdit.text())
            except:
                self.warn("Error in figure resolution value")
                return
            
            try:
                fig_font_size_pts = float(dialog.figure_fontsize_pts_QLineEdit.text())
            except:
                self.warn("Error in font size value")
               
            try:
                fig_outpath = unicode(dialog.figure_outpath_QLineEdit.text())
            except:
                self.warn("Error in figure output path")
                return
            
            try:
                top_space_value = float(dialog.top_space_value_QDoubleSpinBox.value())
            except:
                self.warn("Error in figure top space value")
                return
            
            try:
                left_space_value = float(dialog.left_space_value_QDoubleSpinBox.value())
            except:
                self.warn("Error in figure left space value")
                return
            
            try:
                right_space_value = float(dialog.right_space_value_QDoubleSpinBox.value())
            except:
                self.warn("Error in figure right space value")
                return

            try:
                bottom_space_value = float(dialog.bottom_space_value_QDoubleSpinBox.value())
            except:
                self.warn("Error in figure bottom space value")
                return

            try:
                blank_width_space = float(dialog.blank_width_space_value_QDoubleSpinBox.value())
            except:
                self.warn("Error in figure blank widht space value")
                return

            try:
                blank_height_space = float(dialog.blank_height_space_value_QDoubleSpinBox.value())
            except:
                self.warn("Error in figure blank height space value")
                return
                                                                                
        else:
            
            self.warn("No export figure defined")
            return

        figure = profile_window.canvas.fig

        fig_current_width, fig_current_height = figure.get_size_inches()
        fig_scale_factor = fig_width_inches / fig_current_width
        figure.set_size_inches(fig_width_inches, fig_scale_factor*fig_current_height)

        for axis in figure.axes:            
            for label in (axis.get_xticklabels() + axis.get_yticklabels()):
                label.set_fontsize(fig_font_size_pts)
                
        figure.subplots_adjust(wspace=blank_width_space, hspace=blank_height_space, left=left_space_value, right=right_space_value, top=top_space_value, bottom=bottom_space_value)

        try:
            figure.savefig(str(fig_outpath), dpi = fig_resolution_dpi)
        except:
            self.warn("Error with image saving")
        else:
            self.info("Image saved")

    
                         
    def closeEvent(self, event):
        
        try:
            self.rubberband.reset(QGis.Line)
        except:
            pass
        
        try:
            self.disconnect_digitize_maptool()
        except:
            pass
                
        try:       
            QgsMapLayerRegistry.instance().layerWasAdded.disconnect(self.refresh_struct_polygon_lyr_combobox)
        except:
            pass
                  
        try:       
            QgsMapLayerRegistry.instance().layerWasAdded.disconnect(self.refresh_struct_line_lyr_combobox)
        except:
            pass

        try:       
            QgsMapLayerRegistry.instance().layerWasAdded.disconnect(self.refresh_struct_point_lyr_combobox)
        except:
            pass
                   
        try:
            QgsMapLayerRegistry.instance().layerRemoved.disconnect(self.refresh_struct_polygon_lyr_combobox) 
        except:
            pass               
            
        try:
            QgsMapLayerRegistry.instance().layerRemoved.disconnect(self.refresh_struct_line_lyr_combobox)
        except:
            pass
        
        try:
            QgsMapLayerRegistry.instance().layerRemoved.disconnect(self.refresh_struct_point_lyr_combobox) 
        except:
            pass  
     

        
class SourceDEMsDialog(QDialog):
    
    def __init__(self, raster_layers, parent=None):
        
        super(SourceDEMsDialog, self).__init__(parent)        
        
        self.singleband_raster_layers_in_project = raster_layers

                                       
        self.listDEMs_treeWidget = QTreeWidget()
        self.listDEMs_treeWidget.setColumnCount(2)
        self.listDEMs_treeWidget.setColumnWidth (0, 200)
        self.listDEMs_treeWidget.headerItem().setText(0, "Name")
        self.listDEMs_treeWidget.headerItem().setText(1, "Plot color")
        self.listDEMs_treeWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.listDEMs_treeWidget.setDragEnabled(False)
        self.listDEMs_treeWidget.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.listDEMs_treeWidget.setAlternatingRowColors(True)
        self.listDEMs_treeWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.listDEMs_treeWidget.setTextElideMode(Qt.ElideLeft)
         
        self.refresh_raster_layer_treewidget()
        
        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)
        
        layout = QGridLayout()

        layout.addWidget(self.listDEMs_treeWidget, 0, 0, 1, 3)                 
        layout.addLayout(buttonLayout, 1, 0, 1, 3)
        
        self.setLayout(layout)

        self.connect(okButton, SIGNAL("clicked()"),
                     self,  SLOT("accept()"))
        self.connect(cancelButton, SIGNAL("clicked()"),
                     self, SLOT("reject()"))
        
        self.setWindowTitle("Define source DEMs")
         

    def refresh_raster_layer_treewidget(self):

        self.listDEMs_treeWidget.clear() 
                                    
        for raster_layer in self.singleband_raster_layers_in_project:
            
            tree_item = QTreeWidgetItem(self.listDEMs_treeWidget)
            tree_item.setText(0, raster_layer.name())
            combo_box = QComboBox()
            combo_box.setSizeAdjustPolicy (0)
            combo_box.addItems(qprof_QWidget.colors)
            self.listDEMs_treeWidget.setItemWidget(tree_item, 1, combo_box)       
            tree_item.setFlags(tree_item.flags() | Qt.ItemIsUserCheckable)
            tree_item.setCheckState(0, 0)


        
class SourceLineLayerDialog(QDialog):
    
    def __init__(self, current_line_layers, parent=None):
                
        super(SourceLineLayerDialog, self).__init__(parent)
        
        self.current_line_layers = current_line_layers
 
        layout = QGridLayout()
                                              
        layout.addWidget(QLabel(self.tr("Line layer:")), 0, 0, 1, 1) 
        self.LineLayers_comboBox = QComboBox()                         
        layout.addWidget(self.LineLayers_comboBox, 0, 1, 1, 3)         
        self.refresh_input_profile_layer_combobox()

        layout.addWidget(QLabel(self.tr("Line order field:")), 1, 0, 1, 1) 
        
        self.Trace2D_order_field_comboBox = QComboBox()                        
        layout.addWidget(self.Trace2D_order_field_comboBox, 1, 1, 1, 3) 
                
        self.refresh_order_field_combobox()
        
        self.LineLayers_comboBox.currentIndexChanged[int].connect (self.refresh_order_field_combobox)
        
        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)
              
        layout.addLayout(buttonLayout, 2, 0, 1, 3)
        
        self.setLayout(layout)

        self.connect(okButton, SIGNAL("clicked()"),
                     self,  SLOT("accept()"))
        self.connect(cancelButton, SIGNAL("clicked()"),
                     self, SLOT("reject()"))
        
        self.setWindowTitle("Define source line layer")


    def refresh_input_profile_layer_combobox(self):
        
        self.LineLayers_comboBox.clear()
      
        for layer in self.current_line_layers:
            self.LineLayers_comboBox.addItem(layer.name())        

        shape_qgis_ndx = self.LineLayers_comboBox.currentIndex()
        self.line_shape = self.current_line_layers[shape_qgis_ndx]            
         
         
    def refresh_order_field_combobox(self):       
        
        self.Trace2D_order_field_comboBox.clear()
        self.Trace2D_order_field_comboBox.addItem('--optional--')  

        shape_qgis_ndx = self.LineLayers_comboBox.currentIndex()
        self.line_shape = self.current_line_layers[shape_qgis_ndx]
       
        line_layer_field_list = self.line_shape.dataProvider().fields().toList()        
        for field in line_layer_field_list:
            self.Trace2D_order_field_comboBox.addItem(field.name())      
 
    
    
class LoadPointListDialog(QDialog):
    
    def __init__(self, parent=None):
        
        super(LoadPointListDialog, self).__init__(parent)  

        layout = QGridLayout()
                                              
        layout.addWidget(QLabel(self.tr("Point list, with at least two points.")), 0, 0, 1, 1) 
        layout.addWidget(QLabel(self.tr("Each point is defined by a x-y coordinates pair, comma-separated, on a single row")), 1, 0, 1, 1) 
        layout.addWidget(QLabel(self.tr("Example:\n549242.7, 242942.2\n578370.3, 322634.5")), 2, 0, 1, 1) 
        
        self.point_list_qtextedit = QTextEdit()        
        layout.addWidget(self.point_list_qtextedit, 3, 0, 1, 1)         

        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)
        
        layout.addLayout(buttonLayout, 4, 0, 1, 3)

        self.setLayout(layout)        
        
        self.connect(okButton, SIGNAL("clicked()"),
                     self,  SLOT("accept()"))
        self.connect(cancelButton, SIGNAL("clicked()"),
                     self, SLOT("reject()"))
        
        self.setWindowTitle("Point list")
       


class PolygonIntersectionRepresentationDialog(QDialog):
    
    colors = ["darkseagreen", "darkgoldenrod","darkviolet", "hotpink", "powderblue", "yellowgreen", "palevioletred", 
                  "seagreen", "darkturquoise", "beige", "darkkhaki", "red", "yellow","magenta","blue","cyan","chartreuse"] 

    
    def __init__(self, polygon_classification_set, parent=None):
        
        super(PolygonIntersectionRepresentationDialog, self).__init__(parent)        
        
        self.polygon_classifications = list(polygon_classification_set)
                                       
        self.polygon_classifications_treeWidget = QTreeWidget()
        self.polygon_classifications_treeWidget.setColumnCount(2)
        self.polygon_classifications_treeWidget.setColumnWidth (0, 200)
        self.polygon_classifications_treeWidget.headerItem().setText(0, "Name")
        self.polygon_classifications_treeWidget.headerItem().setText(1, "Plot color")
        self.polygon_classifications_treeWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.polygon_classifications_treeWidget.setDragEnabled(False)
        self.polygon_classifications_treeWidget.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.polygon_classifications_treeWidget.setAlternatingRowColors(True)
        self.polygon_classifications_treeWidget.setTextElideMode(Qt.ElideLeft)
         
        self.refresh_classification_colors_treewidget()
        
        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)
        
        layout = QGridLayout()

        layout.addWidget(self.polygon_classifications_treeWidget, 0, 0, 1, 3)                 
        layout.addLayout(buttonLayout, 1, 0, 1, 3)
        
        self.setLayout(layout)

        self.connect(okButton, SIGNAL("clicked()"),
                     self,  SLOT("accept()"))
        self.connect(cancelButton, SIGNAL("clicked()"),
                     self, SLOT("reject()"))
        
        self.setWindowTitle("Polygon intersection colors")
         

    def refresh_classification_colors_treewidget(self):

        self.polygon_classifications_treeWidget.clear() 
                                    
        for classification_id in self.polygon_classifications:
            
            tree_item = QTreeWidgetItem(self.polygon_classifications_treeWidget)
            tree_item.setText(0, unicode(classification_id))
            combo_box = QComboBox()
            combo_box.setSizeAdjustPolicy (0)
            combo_box.addItems(PolygonIntersectionRepresentationDialog.colors)
            self.polygon_classifications_treeWidget.setItemWidget(tree_item, 1, combo_box)       




class FigureExportDialog(QDialog):
 
    def __init__(self, parent=None):
        
        super(FigureExportDialog, self).__init__(parent)  
        
        layout = QVBoxLayout() 

        # main parameters gropbox
        
        main_params_groupBox = QGroupBox("Main graphic parameters")
        
        main_params_layout = QGridLayout()           
    
        main_params_layout.addWidget(QLabel(self.tr("Figure width (inches)")), 0, 0, 1, 1)     
        self.figure_width_inches_QLineEdit = QLineEdit("10")
        main_params_layout.addWidget(self.figure_width_inches_QLineEdit, 0, 1, 1, 1)     

        main_params_layout.addWidget(QLabel(self.tr("Resolution (dpi)")), 0, 2, 1, 1)     
        self.figure_resolution_dpi_QLineEdit = QLineEdit("200")
        main_params_layout.addWidget(self.figure_resolution_dpi_QLineEdit, 0, 3, 1, 1)  

        main_params_layout.addWidget(QLabel(self.tr("Font size (pts)")), 0, 4, 1, 1)     
        self.figure_fontsize_pts_QLineEdit = QLineEdit("12")
        main_params_layout.addWidget(self.figure_fontsize_pts_QLineEdit, 0, 5, 1, 1)  

        main_params_groupBox.setLayout(main_params_layout) 
        
        layout.addWidget(main_params_groupBox) 
        
        
        # additional parameters groupbox
        
        add_params_groupBox = QGroupBox(self.tr("Subplot configuration tools parameters"))
        
        add_params_layout = QGridLayout()
        
        add_params_layout.addWidget(QLabel("Top space"), 0, 2, 1, 1)
        self.top_space_value_QDoubleSpinBox = QDoubleSpinBox()
        self.top_space_value_QDoubleSpinBox.setRange(0.0, 1.0)
        self.top_space_value_QDoubleSpinBox.setDecimals(2)        
        self.top_space_value_QDoubleSpinBox.setSingleStep(0.01)        
        self.top_space_value_QDoubleSpinBox.setValue(0.96)
        add_params_layout.addWidget(self.top_space_value_QDoubleSpinBox, 0, 3, 1, 1)

        add_params_layout.addWidget(QLabel("Left space"), 1, 0, 1, 1)
        self.left_space_value_QDoubleSpinBox = QDoubleSpinBox()
        self.left_space_value_QDoubleSpinBox.setRange(0.0, 1.0)
        self.left_space_value_QDoubleSpinBox.setDecimals(2)
        self.left_space_value_QDoubleSpinBox.setSingleStep(0.01)                 
        self.left_space_value_QDoubleSpinBox.setValue(0.1)
        add_params_layout.addWidget(self.left_space_value_QDoubleSpinBox, 1, 1, 1, 1)
                
        add_params_layout.addWidget(QLabel("Right space"), 1, 4, 1, 1)
        self.right_space_value_QDoubleSpinBox = QDoubleSpinBox()
        self.right_space_value_QDoubleSpinBox.setRange(0.0, 1.0)
        self.right_space_value_QDoubleSpinBox.setDecimals(2)
        self.right_space_value_QDoubleSpinBox.setSingleStep(0.01)   
        self.right_space_value_QDoubleSpinBox.setValue(0.96)
        add_params_layout.addWidget(self.right_space_value_QDoubleSpinBox, 1, 5, 1, 1)
                
        add_params_layout.addWidget(QLabel("Bottom space"), 2, 2, 1, 1)
        self.bottom_space_value_QDoubleSpinBox = QDoubleSpinBox()
        self.bottom_space_value_QDoubleSpinBox.setRange(0.0, 1.0)
        self.bottom_space_value_QDoubleSpinBox.setDecimals(2)
        self.bottom_space_value_QDoubleSpinBox.setSingleStep(0.01)   
        self.bottom_space_value_QDoubleSpinBox.setValue(0.06)
        add_params_layout.addWidget(self.bottom_space_value_QDoubleSpinBox, 2, 3, 1, 1)
        
        add_params_layout.addWidget(QLabel("Blank width space between subplots"), 3, 0, 1, 2)
        self.blank_width_space_value_QDoubleSpinBox = QDoubleSpinBox()
        self.blank_width_space_value_QDoubleSpinBox.setRange(0.0, 1.0)
        self.blank_width_space_value_QDoubleSpinBox.setDecimals(2)
        self.blank_width_space_value_QDoubleSpinBox.setSingleStep(0.01)   
        self.blank_width_space_value_QDoubleSpinBox.setValue(0.1)
        add_params_layout.addWidget(self.blank_width_space_value_QDoubleSpinBox, 3, 2, 1, 1)
                
        add_params_layout.addWidget(QLabel("Blank height space between subplots"), 3, 3, 1, 2)
        self.blank_height_space_value_QDoubleSpinBox = QDoubleSpinBox()
        self.blank_height_space_value_QDoubleSpinBox.setRange(0.0, 1.0)
        self.blank_height_space_value_QDoubleSpinBox.setDecimals(2)
        self.blank_height_space_value_QDoubleSpinBox.setSingleStep(0.01)   
        self.blank_height_space_value_QDoubleSpinBox.setValue(0.1)
        add_params_layout.addWidget(self.blank_height_space_value_QDoubleSpinBox, 3, 5, 1, 1)
        
        add_params_layout.setRowMinimumHeight (3, 50)
        
        add_params_groupBox.setLayout(add_params_layout) 
        
        layout.addWidget(add_params_groupBox) 


        # graphic parameters import and export
        
        graphic_params_io_groupBox = QGroupBox("Graphic parameters save/load")
        
        graphic_params_io_layout = QHBoxLayout() 
        
        self.graphic_params_save_QPushButton = QPushButton("Save")
        self.graphic_params_save_QPushButton.clicked.connect(self.output_graphic_params_save)
        graphic_params_io_layout.addWidget(self.graphic_params_save_QPushButton)
 
        self.graphic_params_load_QPushButton = QPushButton("Load")
        self.graphic_params_load_QPushButton.clicked.connect(self.output_graphic_params_load)
        graphic_params_io_layout.addWidget(self.graphic_params_load_QPushButton)
               
        graphic_params_io_groupBox.setLayout(graphic_params_io_layout) 
        
        layout.addWidget(graphic_params_io_groupBox) 
        
                
        
        # output file parameters
        
        output_file_groupBox = QGroupBox(self.tr("Output file"))
        
        output_file_layout = QGridLayout()           
                   
        self.figure_outpath_QLineEdit = QLineEdit()
        output_file_layout.addWidget(self.figure_outpath_QLineEdit, 3, 0, 1, 1)

        self.figure_outpath_QPushButton = QPushButton(self.tr("Choose"))
        self.figure_outpath_QPushButton.clicked.connect(self.define_figure_outpath)
        output_file_layout.addWidget(self.figure_outpath_QPushButton, 3, 1, 1, 1)
 
        output_file_groupBox.setLayout(output_file_layout) 
        
        layout.addWidget(output_file_groupBox)  

                                
        
        # execution buttons
        
        decide_QWiget = QWidget()

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()

        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)

        decide_QWiget.setLayout(buttonLayout)

        layout.addWidget(decide_QWiget)

        self.setLayout(layout)

        self.connect(okButton, SIGNAL("clicked()"),
                     self,  SLOT("accept()"))
        self.connect(cancelButton, SIGNAL("clicked()"),
                     self, SLOT("reject()"))
        
        
        self.setWindowTitle("Export figure")
        

    def output_graphic_params_save(self):
        
        output_file_path = new_file_path(self, "Define output configuration file", "*.txt", "txt")
        
        if not output_file_path:
            return
        
        out_configuration_string = """figure width = %f
resolution (dpi) = %d
font size (pts) = %f
top space = %f
left space = %f        
right space = %f        
bottom space = %f  
blank width space = %f
blank height space = %f""" % (float(self.figure_width_inches_QLineEdit.text()),
                              int(self.figure_resolution_dpi_QLineEdit.text()),
                              float(self.figure_fontsize_pts_QLineEdit.text()),
                              float(self.top_space_value_QDoubleSpinBox.value()),
                              float(self.left_space_value_QDoubleSpinBox.value()),
                              float(self.right_space_value_QDoubleSpinBox.value()),
                              float(self.bottom_space_value_QDoubleSpinBox.value()),
                              float(self.blank_width_space_value_QDoubleSpinBox.value()),
                              float(self.blank_height_space_value_QDoubleSpinBox.value()))  

        with open(output_file_path, "w") as ofile:
            ofile.write(out_configuration_string)
            
        self.info("Graphic parameters saved")

    
    def output_graphic_params_load(self):
        
        input_file_path = old_file_path(self, "Choose input configuration file", "*.txt", "txt")
        
        if not input_file_path:
            return
        
        with open(input_file_path, "r") as ifile:
            config_lines = ifile.readlines()
        
        try:
            figure_width_inches = float(config_lines[0].split("=")[1])
            figure_resolution_dpi = int(config_lines[1].split("=")[1])
            figure_fontsize_pts = float(config_lines[2].split("=")[1])
            top_space_value = float(config_lines[3].split("=")[1])
            left_space_value = float(config_lines[4].split("=")[1])
            right_space_value = float(config_lines[5].split("=")[1])
            bottom_space_value = float(config_lines[6].split("=")[1])
            blank_width_space = float(config_lines[7].split("=")[1])
            blank_height_space = float(config_lines[8].split("=")[1])
        except:
            self.warn("Error in configuration file")
            return
                    
        self.figure_width_inches_QLineEdit.setText(str(figure_width_inches))
        self.figure_resolution_dpi_QLineEdit.setText(str(figure_resolution_dpi))
        self.figure_fontsize_pts_QLineEdit.setText(str(figure_fontsize_pts))
        self.top_space_value_QDoubleSpinBox.setValue(top_space_value)
        self.left_space_value_QDoubleSpinBox.setValue(left_space_value)
        self.right_space_value_QDoubleSpinBox.setValue(right_space_value)
        self.bottom_space_value_QDoubleSpinBox.setValue(bottom_space_value)
        self.blank_width_space_value_QDoubleSpinBox.setValue(blank_width_space)
        self.blank_height_space_value_QDoubleSpinBox.setValue(blank_height_space)
                              
                              
                                     
    def define_figure_outpath(self):

        outfile_path = new_file_path(self, "Path", "*.svg; *.pdf; *.tif", "svg; pdf; tif")

        self.figure_outpath_QLineEdit.setText(outfile_path)
        

    def info(self, msg):
        
        QMessageBox.information(self,  "qProf", msg)
        
        
    def warn(self, msg):
    
        QMessageBox.warning(self,  "qProf", msg)
        
                 
    
class TopographicProfileExportDialog(QDialog):
    
    def __init__(self, selected_dem_list=[], parent=None):
        
        super(TopographicProfileExportDialog, self).__init__(parent)  

        layout = QVBoxLayout()
        
        ##
        # Profile source
                                                      
        source_groupBox = QGroupBox(self.tr("Profile sources"))
        
        source_layout = QGridLayout()
        
        self.src_allselecteddems_QRadioButton = QRadioButton(self.tr("All selected DEMs"))
        source_layout.addWidget(self.src_allselecteddems_QRadioButton, 1,0,1,2)
        self.src_allselecteddems_QRadioButton.setChecked(True)
        
        self.src_singledem_QRadioButton = QRadioButton(self.tr("Single DEM"))
        source_layout.addWidget(self.src_singledem_QRadioButton, 2,0,1,1)
        
        self.src_singledemlist_QComboBox = QComboBox()
        for qgsRasterLayer in selected_dem_list:
            self.src_singledemlist_QComboBox.addItem(qgsRasterLayer.name())
        source_layout.addWidget(self.src_singledemlist_QComboBox, 2,1,1,1)
                
        self.src_singlegpx_QRadioButton = QRadioButton(self.tr("GPX file"))
        source_layout.addWidget(self.src_singlegpx_QRadioButton, 3,0,1,1) 
        
        source_groupBox.setLayout(source_layout) 
        
        layout.addWidget(source_groupBox) 
        
        
        ##
        # Output type

        output_type_groupBox = QGroupBox(self.tr("Output format"))
        
        output_type_layout = QGridLayout()

        self.outtype_shapefile_point_QRadioButton = QRadioButton(self.tr("shapefile - point"))
        output_type_layout.addWidget(self.outtype_shapefile_point_QRadioButton, 0,0,1,1)
        self.outtype_shapefile_point_QRadioButton.setChecked(True)        
                
        self.outtype_shapefile_line_QRadioButton = QRadioButton(self.tr("shapefile - line"))
        output_type_layout.addWidget(self.outtype_shapefile_line_QRadioButton, 1,0,1,1)
   
        self.outtype_csv_QRadioButton = QRadioButton(self.tr("csv"))
        output_type_layout.addWidget(self.outtype_csv_QRadioButton, 2,0,1,1)
        
        output_type_groupBox.setLayout(output_type_layout)         
                
        layout.addWidget(output_type_groupBox)    
         
        
        ##
        # Output name/path

        output_path_groupBox = QGroupBox(self.tr("Output path"))
        
        output_path_layout = QGridLayout()
        
        self.outpath_QLineEdit = QLineEdit()
        output_path_layout.addWidget(self.outpath_QLineEdit, 0,0,1,1)
        
        self.outpath_QPushButton = QPushButton(self.tr("Choose"))
        self.outpath_QPushButton.clicked.connect(self.define_outpath)
        output_path_layout.addWidget(self.outpath_QPushButton, 0,1,1,1)
        
        output_path_groupBox.setLayout(output_path_layout)         
                
        layout.addWidget(output_path_groupBox)    


        decide_QWiget = QWidget()
        
        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
                
        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)
        
        decide_QWiget.setLayout(buttonLayout)
        
        layout.addWidget(decide_QWiget)

        self.setLayout(layout)        
        
        self.connect(okButton, SIGNAL("clicked()"),
                     self,  SLOT("accept()"))
        self.connect(cancelButton, SIGNAL("clicked()"),
                     self, SLOT("reject()"))
        
        self.setWindowTitle("Export topographic profile")
        
    
    def define_outpath(self):
    
        if self.outtype_shapefile_line_QRadioButton.isChecked() or self.outtype_shapefile_point_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Path", "*.shp", "Shapefile")
        elif self.outtype_csv_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Path", "*.csv", "Csv")
        else:
            self.warn(self.tr("Output type definiton error")) 
            return           
        
        self.outpath_QLineEdit.setText(outfile_path)
        
          

class PointDataExportDialog(QDialog):

    def __init__(self, parent=None):

        super(PointDataExportDialog, self).__init__(parent)

        layout = QVBoxLayout()

        ##
        # Output type

        output_type_groupBox = QGroupBox(self.tr("Output format"))

        output_type_layout = QGridLayout()

        self.outtype_shapefile_point_QRadioButton = QRadioButton(self.tr("shapefile - point"))
        output_type_layout.addWidget(self.outtype_shapefile_point_QRadioButton, 0,0,1,1)
        self.outtype_shapefile_point_QRadioButton.setChecked(True)

        self.outtype_csv_QRadioButton = QRadioButton(self.tr("csv"))
        output_type_layout.addWidget(self.outtype_csv_QRadioButton, 1,0,1,1)

        output_type_groupBox.setLayout(output_type_layout)

        layout.addWidget(output_type_groupBox)


        ##
        # Output name/path

        output_path_groupBox = QGroupBox(self.tr("Output path"))

        output_path_layout = QGridLayout()

        self.outpath_QLineEdit = QLineEdit()
        output_path_layout.addWidget(self.outpath_QLineEdit, 0,0,1,1)

        self.outpath_QPushButton = QPushButton(self.tr("Choose"))
        self.outpath_QPushButton.clicked.connect(self.define_outpath)
        output_path_layout.addWidget(self.outpath_QPushButton, 0,1,1,1)

        output_path_groupBox.setLayout(output_path_layout)

        layout.addWidget(output_path_groupBox)


        decide_QWiget = QWidget()

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()

        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)

        decide_QWiget.setLayout(buttonLayout)

        layout.addWidget(decide_QWiget)

        self.setLayout(layout)

        self.connect(okButton, SIGNAL("clicked()"),
                     self,  SLOT("accept()"))
        self.connect(cancelButton, SIGNAL("clicked()"),
                     self, SLOT("reject()"))

        self.setWindowTitle("Export")


    def define_outpath(self):

        if self.outtype_shapefile_point_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Path", "*.shp", "Shapefile")
        elif self.outtype_csv_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Path", "*.csv", "Csv")
        else:
            self.warn(self.tr("Output type definiton error"))
            return

        self.outpath_QLineEdit.setText(outfile_path)



class LineDataExportDialog(QDialog):

    def __init__(self, parent=None):

        super(LineDataExportDialog, self).__init__(parent)

        layout = QVBoxLayout()

        ##
        # Output type

        output_type_groupBox = QGroupBox(self.tr("Output format"))

        output_type_layout = QGridLayout()

        self.outtype_shapefile_line_QRadioButton = QRadioButton(self.tr("shapefile - line"))
        output_type_layout.addWidget(self.outtype_shapefile_line_QRadioButton, 0,0,1,1)
        self.outtype_shapefile_line_QRadioButton.setChecked(True)

        self.outtype_csv_QRadioButton = QRadioButton(self.tr("csv"))
        output_type_layout.addWidget(self.outtype_csv_QRadioButton, 1,0,1,1)

        output_type_groupBox.setLayout(output_type_layout)

        layout.addWidget(output_type_groupBox)


        ##
        # Output name/path

        output_path_groupBox = QGroupBox(self.tr("Output path"))

        output_path_layout = QGridLayout()

        self.outpath_QLineEdit = QLineEdit()
        output_path_layout.addWidget(self.outpath_QLineEdit, 0,0,1,1)

        self.outpath_QPushButton = QPushButton(self.tr("Choose"))
        self.outpath_QPushButton.clicked.connect(self.define_outpath)
        output_path_layout.addWidget(self.outpath_QPushButton, 0,1,1,1)

        output_path_groupBox.setLayout(output_path_layout)

        layout.addWidget(output_path_groupBox)


        decide_QWiget = QWidget()

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()

        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)

        decide_QWiget.setLayout(buttonLayout)

        layout.addWidget(decide_QWiget)

        self.setLayout(layout)

        self.connect(okButton, SIGNAL("clicked()"),
                     self,  SLOT("accept()"))
        self.connect(cancelButton, SIGNAL("clicked()"),
                     self, SLOT("reject()"))

        self.setWindowTitle("Export")


    def define_outpath(self):

        if self.outtype_shapefile_line_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Path", "*.shp", "Shapefile")
        elif self.outtype_csv_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Path", "*.csv", "Csv")
        else:
            self.warn(self.tr("Output type definiton error"))
            return

        self.outpath_QLineEdit.setText(outfile_path)


class StatisticsDialog(QDialog):

    def __init__(self, profiles_stats, parent=None):

        super(StatisticsDialog, self).__init__(parent)

        self.profiles_stats = profiles_stats

        layout = QVBoxLayout()

        self.text_widget = QTextEdit()
        self.text_widget.setReadOnly(True)

        stat_report = self.report_stats(profiles_stats)

        self.text_widget.setPlainText(stat_report)

        layout.addWidget(self.text_widget)

        self.setLayout(layout)

        self.setWindowTitle("Statistics")


    def report_stats(self, profiles_stats):

        report = ''
        for prof_stat in profiles_stats:
            report += 'dem: %s\n\n' % (prof_stat['dem_name'])
            report += 'min: %s\n' % (prof_stat['z_min'])
            report += 'max: %s\n' % (prof_stat['z_max'])
            report += 'mean: %s\n' % (prof_stat['z_mean'])
            report += 'variance: %s\n' % (prof_stat['z_var'])
            report += 'standard deviation: %s\n\n\n' % (prof_stat['z_std'])

        return report
