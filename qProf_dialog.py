# -*- coding: utf-8 -*-


import os
from math import isnan, sin, cos, asin, radians, degrees, floor, ceil
import numpy as np

import xml.dom.minidom

import unicodedata

from osgeo import ogr

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.core import QgsPoint, QgsRaster
from qgis.core import QgsMapLayerRegistry, QgsMapLayer, QGis

from qt_utils.utils import lastUsedDir, setLastUsedDir

from geosurf.spatial import Point, Vector, GeolPlane, CartesianPlane
from geosurf.geoio import QGisRasterParameters, read_line_shapefile
from geosurf.geodetic import TrackPointGPX
from geosurf.intersections import project_struct_pt_on_section

from qgs_tools.tools import get_current_raster_layers, get_current_line_layers, get_current_point_layers, \
                            get_selected_features_attr
            
from qProf_mplwidget import MplWidget


        
class qProfDialog( QDialog ):
    """
    Constructor
    
    """
    
    def __init__( self ):

        super( qProfDialog, self ).__init__()        
        self.current_directory = os.path.dirname(__file__)
        self.initialize_parameters()                 
        self.setup_gui()
        self.setWindowFlags( Qt.WindowStaysOnTopHint )       
           

    def initialize_parameters(self):
        
        self.rasterLayers = get_current_raster_layers() 
        self.lineLayers = get_current_line_layers()
        self.pointLayers = get_current_point_layers()

        self.line_shape_path = None
        self.profile_points = []
        
        self.selected_dems = []
        self.dem_parameters = []
       
        self.profile_windows = []
        self.cross_section_windows = []        
        self.profiles = None
        self.export_from_DEM = None
        
        self.projected_struct_dataset = None
        

    def setup_gui( self ): 

        self.dialog_layout = QVBoxLayout()

        self.main_widget = QTabWidget()
        
        profile_widget = self.setup_processing_tab()
        self.main_widget.addTab( profile_widget, "Profile" ) 
        
        cross_section_widget = self.setup_crosssection_tab()
        self.main_widget.addTab( cross_section_widget, "Geological cross-sections" )
        
        about_widget = self.setup_about_tab()
        self.main_widget.addTab( about_widget, "About" )

        QgsMapLayerRegistry.instance().layerWasAdded.connect( self.refresh_line_layer_combobox )
        QgsMapLayerRegistry.instance().layerWasAdded.connect( self.refresh_point_layer_comboboxes )
        QgsMapLayerRegistry.instance().layerWasAdded.connect( self.refresh_raster_layer_treewidget )        
                
        self.dialog_layout.addWidget(self.main_widget)                             
        self.setLayout(self.dialog_layout)            
        self.adjustSize()               
        self.setWindowTitle( 'qProf' )        
                
  
    def setup_processing_tab( self ):  

        profile_widget = QWidget() 
        profile_layout = QVBoxLayout()
 
        profile_toolbox = QToolBox()        
        
        ## input section
        
        input2DWidget = QWidget()
        input2DLayout = QGridLayout()        
        
        ## Shapefile input
                
        input2DLayout.addWidget( QLabel( self.tr("Line layer:") ), 0, 0, 1, 1)       

        self.Trace2D_comboBox = QComboBox()
        
        self.Trace2D_comboBox.currentIndexChanged[int].connect (self.get_path_source )
                 
        input2DLayout.addWidget(self.Trace2D_comboBox, 0, 1, 1, 3) 
        
        self.refresh_line_layer_combobox()


        ## Input from DEM
        
        # input DEM tree view 
                                    
        input2DLayout.addWidget(QLabel( "Use DEMs:" ), 1, 0, 1, 1)
       
        self.listDEMs_treeWidget = QTreeWidget()
        self.listDEMs_treeWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.listDEMs_treeWidget.setDragEnabled(False)
        self.listDEMs_treeWidget.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.listDEMs_treeWidget.setAlternatingRowColors(True)
        self.listDEMs_treeWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.listDEMs_treeWidget.setTextElideMode(Qt.ElideNone)
        self.listDEMs_treeWidget.headerItem().setText( 0, self.tr( "Files" ) )
        self.listDEMs_treeWidget.header().setVisible(False)

        self.listDEMs_treeWidget.itemClicked[ QTreeWidgetItem, int ].connect( self.get_DEM_sources )
        """
        QObject.connect( self.listDEMs_treeWidget, 
                         SIGNAL( " itemClicked ( QTreeWidgetItem * , int ) " ), 
                         self.get_DEM_sources itemClicked ( QTreeWidgetItem * , int ))
        """         
         
        self.refresh_raster_layer_treewidget()
            
        input2DLayout.addWidget(self.listDEMs_treeWidget, 1, 1, 1, 3 )           
           
        ## max sampling distance
         
        input2DLayout.addWidget( QLabel( self.tr("Max sampling distance") ), 2, 0, 1, 1 )         
        self.sample_distance_lineedit = QLineEdit()
        input2DLayout.addWidget( self.sample_distance_lineedit, 2, 1, 1, 3 )

        ## 'Calculate profile' push button
        
        self.CalcProf2D_pushbutton = QPushButton(self.tr("Calculate profile")) 
        self.CalcProf2D_pushbutton.clicked.connect( self.calculate_profiles_from_DEMs )
        """
        QObject.connect(self.CalcProf2D_pushbutton, 
                        SIGNAL("clicked()"), 
                        self.calculate_profiles_from_DEMs )
        """
                       
        input2DLayout.addWidget( self.CalcProf2D_pushbutton, 3, 0, 1, 4 )
                        
        input2DWidget.setLayout( input2DLayout )        
        profile_toolbox.addItem ( input2DWidget, "Elevations from DEM" )        
        
        ## Input from GPX
        
        input3DWidget = QWidget()
        input3DLayout = QGridLayout()        
        
        input3DLayout.addWidget( QLabel( self.tr("GPX file with track points:") ), 0, 0, 1, 1)       

        self.input_gpx_lineEdit = QLineEdit()
        self.input_gpx_lineEdit.setPlaceholderText("my_track.gpx")
        input3DLayout.addWidget(self.input_gpx_lineEdit, 0, 1, 1, 1)
        
        self.input_gpx_QPButt = QPushButton( "..." )
        self.input_gpx_QPButt.clicked.connect( self.select_input_gpxFile )
        # QObject.connect( self.input_gpx_QPButt, SIGNAL( "clicked()" ), self.select_input_gpxFile )
        input3DLayout.addWidget(self.input_gpx_QPButt, 0, 2, 1, 1)        

        self.CalcProf3D_pushbutton = QPushButton(self.tr("Calculate profile from track points")) 
        self.CalcProf3D_pushbutton.clicked.connect( self.calculate_profile_from_GPX )
        """
        QObject.connect(self.CalcProf3D_pushbutton, 
                        SIGNAL("clicked()"), 
                        self.calculate_profile_from_GPX ) 
        """              
        input3DLayout.addWidget( self.CalcProf3D_pushbutton, 1, 0, 1, 4 )                       
        
        input3DWidget.setLayout( input3DLayout )        
        profile_toolbox.addItem ( input3DWidget, 'Elevations from GPX' ) 
        
        # Plot QToolBox
        
        plotWidget = QWidget()
        plotLayout = QGridLayout()         
        
        self.PlotProf_pushbutton = QPushButton(self.tr("Plot")) 
        self.PlotProf_pushbutton.clicked.connect( self.plot_profiles )
        """
        QObject.connect(self.PlotProf_pushbutton, 
                        SIGNAL("clicked()"), 
                        self.plot_profiles )  
        """             
        plotLayout.addWidget( self.PlotProf_pushbutton, 1, 0, 1, 2 )        
     
        self.PlotHeight_checkbox = QCheckBox( self.tr( "height"))
        self.PlotHeight_checkbox.setChecked( True ) 
        plotLayout.addWidget( self.PlotHeight_checkbox, 1, 2, 1, 1 )  

        self.PlotSlope_checkbox = QCheckBox( self.tr( "slope"))
        self.PlotSlope_checkbox.setChecked( False )
        plotLayout.addWidget( self.PlotSlope_checkbox, 1, 3, 1, 1 )  
        
        plotWidget.setLayout( plotLayout )        
        profile_toolbox.addItem ( plotWidget, 'Plot profiles' )        
        
        
        # Export from DEM
        
        exportFromDEMWidget = QWidget()
        exportFromDEMLayout = QGridLayout()           
        
        self.Export_fromDEMData_pushbutton = QPushButton(self.tr("Export profiles as")) 
        self.Export_fromDEMData_pushbutton.clicked.connect( self.export_from_DEM_data )
        # QObject.connect(self.Export_fromDEMData_pushbutton, SIGNAL("clicked()"), self.export_from_DEM_data )               
        exportFromDEMLayout.addWidget( self.Export_fromDEMData_pushbutton, 0, 0, 1, 2 )        

        self.ExportfromDEM_asCSV_checkbox = QCheckBox( self.tr( "csv"))
        exportFromDEMLayout.addWidget( self.ExportfromDEM_asCSV_checkbox, 0, 2, 1, 1 )  

        self.ExportfromDEM_asPtShp_checkbox = QCheckBox( self.tr( "2D point shp"))
        exportFromDEMLayout.addWidget( self.ExportfromDEM_asPtShp_checkbox, 0, 3, 1, 1 ) 

        self.Export3DLine_pushbutton = QPushButton(self.tr("Export 3D line from DEM ")) 
        self.Export3DLine_pushbutton.clicked.connect( self.write_DEM_3D_lnshp )
        # QObject.connect(self.Export3DLine_pushbutton, SIGNAL("clicked()"), self.write_DEM_3D_lnshp )               
        exportFromDEMLayout.addWidget( self.Export3DLine_pushbutton, 1, 0, 1, 2 )
         
        self.DEM_3D_Export_comboBox = QComboBox()
        exportFromDEMLayout.addWidget(self.DEM_3D_Export_comboBox, 1, 2, 1, 2)
        
        exportFromDEMWidget.setLayout( exportFromDEMLayout )        
        profile_toolbox.addItem ( exportFromDEMWidget, 'Export DEM-derived profiles' ) 


        # Export from GPX
        
        exportFromGPXWidget = QWidget()
        exportFromGPXLayout = QGridLayout()           

        self.Export_fromGPXData_pushbutton = QPushButton(self.tr("Export profiles as:")) 
        self.Export_fromGPXData_pushbutton.clicked.connect( self.export_from_GPX_data )
        # QObject.connect(self.Export_fromGPXData_pushbutton, SIGNAL("clicked()"), self.export_from_GPX_data )               
        exportFromGPXLayout.addWidget( self.Export_fromGPXData_pushbutton, 0, 0, 1, 3 )         
        
        self.ExportfromGPX_asCSV_checkbox = QCheckBox( self.tr( "csv"))
        exportFromGPXLayout.addWidget( self.ExportfromGPX_asCSV_checkbox, 1, 0, 1, 1 ) 
        
        self.ExportfromGPX_asPtShp_checkbox = QCheckBox( self.tr( "2D point shp"))
        exportFromGPXLayout.addWidget( self.ExportfromGPX_asPtShp_checkbox, 1, 1, 1, 1 )         
        
        self.ExportfromGPX_asLnShp_checkbox = QCheckBox( self.tr( "3D line shp"))
        exportFromGPXLayout.addWidget( self.ExportfromGPX_asLnShp_checkbox, 1, 2, 1, 1 )         
                
        exportFromGPXWidget.setLayout( exportFromGPXLayout )        
        profile_toolbox.addItem ( exportFromGPXWidget, 'Export GPX-derived profile' ) 
                
                
        # widget final setup 
                       
        profile_layout.addWidget(profile_toolbox)
        profile_widget.setLayout(profile_layout) 
        
        return profile_widget     
        

    def setup_crosssection_tab( self ):
        
        cross_section_widget = QWidget()  
        cross_section_layout = QVBoxLayout( ) 

        cross_section_toolbox = QToolBox()

        # Input layers
        
        crosssect_create_widget = QWidget()
        crosssect_create_layout = QGridLayout() 
        crosssect_create_layout.setVerticalSpacing ( 40 )
       
        crosssect_create_layout.addWidget( QLabel("Note: you should have already created a profile.\nThis profile should derive from a path made up by two points only, i.e., start and end points."), 0, 0, 1, 4 )       
      
        crosssect_create_layout.addWidget( QLabel("Layer"), 1, 0, 1, 1 )
        self.stratif_layer_comboBox = QComboBox()
        self.stratif_layer_comboBox.currentIndexChanged[int].connect( self.set_stratification_layer )
        """
        QObject.connect( self.stratif_layer_comboBox, 
                         SIGNAL( " currentIndexChanged ( int ) " ), 
                         self.set_stratification_layer )  
        """               
        crosssect_create_layout.addWidget( self.stratif_layer_comboBox, 1, 1, 1, 3 )        
           
        crosssect_create_layout.addWidget( QLabel("Id"), 2, 0, 1, 1 )
        self.stratif_id_comboBox = QComboBox()
        crosssect_create_layout.addWidget( self.stratif_id_comboBox, 2, 1, 1, 3 )
                     
        crosssect_create_layout.addWidget( QLabel("Dip dir. field"), 3, 0, 1, 1 )
        self.stratif_dipdir_comboBox = QComboBox()
        crosssect_create_layout.addWidget( self.stratif_dipdir_comboBox, 3, 1, 1, 3 ) 
                
        crosssect_create_layout.addWidget( QLabel("Dip ang. field"), 4, 0, 1, 1 )
        self.stratif_dipang_comboBox = QComboBox()
        crosssect_create_layout.addWidget( self.stratif_dipang_comboBox, 4, 1, 1, 3 )        
                
        self.stratification_comboBoxes = [self.stratif_id_comboBox,
                                          self.stratif_dipdir_comboBox,
                                          self.stratif_dipang_comboBox]
                              
        self.refresh_point_layer_comboboxes()

        self.cross_section_calc_pushbutton = QPushButton(self.tr("Create cross-section"))
        self.cross_section_calc_pushbutton.clicked.connect( self.create_cross_section )
        # QObject.connect(self.cross_section_calc_pushbutton, SIGNAL("clicked()"), self.create_cross_section )               
        crosssect_create_layout.addWidget( self.cross_section_calc_pushbutton, 5, 0, 1, 4 )

        crosssect_create_widget.setLayout(crosssect_create_layout)
        cross_section_toolbox.addItem( crosssect_create_widget, "Create cross-section")
        

        ## output
        
        crosssect_output_widget = QWidget()
        crosssect_output_layout = QGridLayout()

        self.save_crosssect_results_pushbutton = QPushButton(self.tr("Export cross-section results as:")) 
        self.save_crosssect_results_pushbutton.clicked.connect( self.save_crosssect_results )
        # QObject.connect(self.save_crosssect_results_pushbutton, SIGNAL("clicked()"), self.save_crosssect_results )               
        crosssect_output_layout.addWidget( self.save_crosssect_results_pushbutton, 0, 0, 1, 3 )
      
        self.save_crosssect_results_asCSV_checkbox = QCheckBox( self.tr( "csv"))
        crosssect_output_layout.addWidget( self.save_crosssect_results_asCSV_checkbox, 1, 0, 1, 1 ) 
       
        self.save_crosssect_results_asPtShp_checkbox = QCheckBox( self.tr( "3D point shp"))
        crosssect_output_layout.addWidget( self.save_crosssect_results_asPtShp_checkbox, 1, 1, 1, 1 )         

        crosssect_output_widget.setLayout( crosssect_output_layout )        
        cross_section_toolbox.addItem ( crosssect_output_widget, 'Export cross-section results' ) 
        
        
        # widget final setup
                
        cross_section_layout.addWidget( cross_section_toolbox )
        cross_section_widget.setLayout( cross_section_layout )
        
        return cross_section_widget
                
  
    def setup_about_tab(self):
        
        about_widget = QWidget()  
        about_layout = QVBoxLayout( )
        
        htmlText = """
        <h3>qProf release 0.2.1 (2013-10-22)</h3>
        Created by M. Alberti (www.malg.eu) and M. Zanieri.
        <br />Concept: M. Zanieri and M. Alberti, implementation: M. Alberti.
        <br />We thank S. Peduzzi for his vigorous testing.
        <br />Plugin for creating profiles from DEM and GPX files, and as an aid in creating geological cross-sections.       
        <br />
        <h4>Profile</h4>
        It is possible to create a profile from one or more DEMs and a line shapefile, or
        from a GPX file storing track points. Be careful, when using DEMs, that both the line shapefile 
        and the DEMs must all be already projected in the same system, for instance UTM.
        <br /><br />When calculating a profile from DEM, you must set the 'max sampling distance',
        i.e. the distance between consecutive sampling point automatically added
        when the original vertices of the used path are distanced more than this value.
        It is advisable to use a value that is comparable to the resolution of the used DEM,
        for instance 30 m for Aster DEMs. 
        <br /><br />After having calculated the profile, you can plot its elevations and slopes,
        and save the results as a csv file, a 2D point shapefile or a 3D line shapefile.
        <br />
        <h4>Geological cross-section</h4>
        Having defined and calculated a profile as previously described,
        it is also possible to plot the traces of geological planes in a new profile window.
        <br />You must select one or more points in a layer representing geological planes, defined by dip direction and
        dip angle values (in addition to an id field).
        <br /><br />The results can be exported both as a csv file or as a 3D point shapefile (a 3D line
         will also be added in a future version).
        <br />
        """
        
        aboutQTextBrowser = QTextBrowser( about_widget )        
        aboutQTextBrowser.insertHtml( htmlText )
         
        about_layout.addWidget( aboutQTextBrowser )  
        about_widget.setLayout(about_layout) 
        
        return about_widget


    def refresh_line_layer_combobox(self):
        
        self.lineLayers = get_current_line_layers()        
        
        self.Trace2D_comboBox.clear()

        for layer in self.lineLayers:
            self.Trace2D_comboBox.addItem( layer.name() )        
        

    def refresh_point_layer_comboboxes(self):
        
        self.pointLayers = get_current_point_layers()        
        
        self.stratif_layer_comboBox.clear()
        
        message = "choose"
        self.stratif_layer_comboBox.addItem( message )
        for layer in self.pointLayers:
            self.stratif_layer_comboBox.addItem( layer.name() )              


    def refresh_raster_layer_treewidget( self ):
        
        self.rasterLayers = get_current_raster_layers()

        self.listDEMs_treeWidget.clear() 
                                    
        for layer in self.rasterLayers:
            tree_item = QTreeWidgetItem( self.listDEMs_treeWidget, [ layer.name() ] )       
            tree_item.setFlags( tree_item.flags() | Qt.ItemIsUserCheckable )
            tree_item.setCheckState( 0, 0 )
 
             
    def get_path_source(self):
        
        if len(self.lineLayers) == 0:
            self.line_shape_path = None
            return
        
        shape_qgis_ndx = self.Trace2D_comboBox.currentIndex()
        if shape_qgis_ndx < 0:           
            self.line_shape_path = None
            return
         
        self.line_shape_path = self.lineLayers[ shape_qgis_ndx ].source()      
        
 
    def get_DEM_sources(self):   
        # defining selected DEMs

        self.selected_dems = []
        self.dem_parameters = []
        
        for dem_qgis_ndx in range( self.listDEMs_treeWidget.topLevelItemCount () ):
            curr_DEM_item = self.listDEMs_treeWidget.topLevelItem ( dem_qgis_ndx ) 
            if curr_DEM_item.checkState ( 0 ) == 2:
                self.selected_dems.append( self.rasterLayers[ dem_qgis_ndx ] )
             
        if len( self.selected_dems ) > 0:
            self.dem_parameters = [ self.get_parameters( selected_dem ) for selected_dem in self.selected_dems ]
       
            
    def select_input_gpxFile( self ):
            
        fileName = QFileDialog.getOpenFileName( self, 
                                                self.tr( "Open GPX file" ), 
                                                lastUsedDir(), 
                                                "GPX (*.gpx *.GPX)" )
        if not fileName:
            return
        setLastUsedDir( fileName )
    
        self.input_gpx_lineEdit.setText( fileName )


    def get_parameters( self, layer ):

        dem_params = QGisRasterParameters()
        
        dem_params.rows = layer.height()
        dem_params.cols = layer.width()
        
        extent = layer.extent()
        
        dem_params.xMin = extent.xMinimum()
        dem_params.xMax = extent.xMaximum()        
        dem_params.yMin = extent.yMinimum()
        dem_params.yMax = extent.yMaximum()
            
        dem_params.cellsizeEW = (dem_params.xMax-dem_params.xMin) / float(dem_params.cols)
        dem_params.cellsizeNS = (dem_params.yMax-dem_params.yMin) / float(dem_params.rows)

        return dem_params


    def get_z(self, dem_layer, point ):
        
        identification = dem_layer.dataProvider().identify( QgsPoint( point.x, point.y ), QgsRaster.IdentifyFormatValue )
        if not identification.isValid(): 
            return np.nan
        else: 
            # assert len( ident.values() ) == 1
            result_map = identification.results()
            return float( result_map[1] )
                          

    def interpolate_bilinear(self, layer, layer_params, point):  
      
        array_coords_dict = layer_params.geogr2raster( point )
        floor_x_raster = floor( array_coords_dict["x"] )
        ceil_x_raster = ceil( array_coords_dict["x"] )
        floor_y_raster = floor( array_coords_dict["y"] )
        ceil_y_raster = ceil( array_coords_dict["y"] )                
         
        # bottom-left center
        p1 = layer_params.raster2geogr( dict(x=floor_x_raster,
                                             y=floor_y_raster))
        # bottom-right center       
        p2 = layer_params.raster2geogr( dict(x=ceil_x_raster,
                                             y=floor_y_raster))
        # top-left center
        p3 = layer_params.raster2geogr( dict(x=floor_x_raster,
                                             y=ceil_y_raster)) 
        # top-right center       
        p4 = layer_params.raster2geogr( dict(x=ceil_x_raster,
                                             y=ceil_y_raster))
         
        z1 = self.get_z( layer, p1 )
        z2 = self.get_z( layer, p2 )         
        z3 = self.get_z( layer, p3 )
        z4 = self.get_z( layer, p4 ) 
        
        delta_x = point.x - p1.x
        delta_y = point.y - p1.y 

        z_x_a = z1 + (z2-z1)*delta_x/layer_params.cellsizeEW
        z_x_b = z3 + (z4-z3)*delta_x/layer_params.cellsizeEW        
        
        return z_x_a + (z_x_b-z_x_a)*delta_y/layer_params.cellsizeNS
            
        
    def interpolate_point_z( self, layer, layer_params, point ):
        
        if layer_params.point_in_interpolation_area( point ):
            return self.interpolate_bilinear( layer, layer_params, point  )
        elif layer_params.point_in_dem_area( point ):
            return self.get_z( layer, point )
        else:
            return np.nan            
                        
                        
    def calculate_slopes_in_DEM_profile( self, profile_points3D ):
        
        slopes_list = []
        for ndx in range( len( profile_points3D ) - 1 ):            
            vector = profile_points3D[ndx].to_vector( profile_points3D[ndx+1] )
            slopes_list.append( degrees( vector.slope_radians() ) ) 
        slopes_list.append( np.nan ) # slope value for last point is unknown         
        return slopes_list


    def get_sample_distance(self, lineedit):
        
        if lineedit.text() == '':
            return np.nan, "Input window is empty" 
        try:
            sample_distance = float( lineedit.text() )
        except:
            return np.nan, "Input cannot be converted to a float value"        
        if not sample_distance > 0.0:
            return np.nan, "Input value is negative or zero"
        return sample_distance, "OK"
        

    def get_input_profile(self, line_shape_path):        
                     
        if line_shape_path is None:            
            return [], "No selected shapefile"          
            
        try: 
            result = read_line_shapefile( line_shape_path )
            if not result['success']:
                return [], str( result['error_message'] )    
            lines_points = result['vertices']           
        except:                    
            return [], "Error while reading input shapefile" 

        if len( lines_points ) != 1: 
            return [], "Path is not a single line"
                      
        input_profile_points = lines_points[ 0 ] 
               
        if len( input_profile_points ) < 2:
            return [], "Path is not a line" 
        
        return input_profile_points, "OK"
        
        
    def calculate_profiles_from_DEMs(self):
        
        self.profiles = None
        self.export_from_DEM = None
        
        # get sample distance
        sample_distance, message = self.get_sample_distance( self.sample_distance_lineedit )
        if sample_distance == np.nan:
            QMessageBox.critical( self, 
                                  "Error while reading sample distance", 
                                  message )
            return  
             
        # get profile path from input shapefile
        self.profile_points, message = self.get_input_profile( self.line_shape_path )
        if self.profile_points == []:
            QMessageBox.critical( self, 
                                  "Error while reading shapefile path", 
                                  message ) 
            
        # check if there are available DEMs selected
        
        if self.selected_dems == [] or \
           self.dem_parameters == []:
            QMessageBox.critical( self, "Error in input DEMs", "No DEM chosen" )
            return 
                        
        # cycles through path points and determines 3D points
        # checks if the distance between current and previous path points is larger than threshold
        # if it is, determines intermediate 3D points
        # finally, determines 3D points for current path point
        
        profiles_points3D = []       
        for point_ndx in xrange( 0, len( self.profile_points ) ):
                        
            curr_point = self.profile_points[ point_ndx ]             
            if point_ndx == 0: prev_point = curr_point                        
            inter_2Dvertices_dist, _, inter_2Dvertices_versor, _ = prev_point.distance_uvector( curr_point ) 
            
            if inter_2Dvertices_dist == 0.0 and point_ndx > 0: continue # skip coincident points
            
            # determines intermediate points          
            if inter_2Dvertices_dist > sample_distance:
                num_iter = 1 
                while num_iter * sample_distance < inter_2Dvertices_dist:                
                    offset_vector_2d = inter_2Dvertices_versor.scale( num_iter * sample_distance )
                    interm_point = prev_point.displaced_by_vector( offset_vector_2d )
                    points_3D = []                   
                    for layer, layer_params in zip( self.selected_dems, self.dem_parameters ):
                        interp_z = self.interpolate_point_z( layer, layer_params, interm_point )
                        points_3D.append( Point(interm_point.x, 
                                                interm_point.y, 
                                                interp_z ) ) 
                    profiles_points3D.append( points_3D )
                    num_iter += 1
                               
            # determines current point
            points_3D = []                   
            for layer, layer_params in zip( self.selected_dems, self.dem_parameters ):
                interp_z = self.interpolate_point_z( layer, layer_params, curr_point )
                points_3D.append( Point( curr_point.x,
                                         curr_point.y,
                                         interp_z ) )
            profiles_points3D.append( points_3D )
            
            # updates previous point for next cycle start
            prev_point = curr_point
                
        # list of profiles, each one made up of the DEM name and its list of 3Dpoints
        profiles_points = []
        for ndx, layer in enumerate( self.selected_dems ):
            profile_points = [ points_3D[ndx] for points_3D in profiles_points3D ]
            if len ( [ point3D for point3D in profile_points if not isnan( point3D.z ) ] ) == 0:
                QMessageBox.critical( self, "Profiles from DEM", "No profile created for DEM source %s" % layer.name() )
            else:                                
                profiles_points.append( [ layer.name(), profile_points ] )

        # check if no profile exists
        if len( profiles_points ) == 0:
            QMessageBox.critical( self, "Profiles from DEM", "No profiles created" )
            return
        
        # uses the first profile as a template for getting common x, y and cumulative 2D distances
        first_profile_points = profiles_points[0][1]
        
        # define x values as a separate list
        x_values = [ points3D.x for points3D in first_profile_points]

        # define x values as a separate list
        y_values = [ points3D.y for points3D in first_profile_points]
        
        # define 2D distance values as separate list        
        cum_distances_2D = [ 0.0 ]
        for ndx in range( len( first_profile_points ) - 1 ):
            incr_2Ddist, _, _, _ = ( first_profile_points[ndx] ).distance_uvector( first_profile_points[ndx+1] )
            cum_distances_2D.append( cum_distances_2D[-1] + incr_2Ddist )
            
        # extract DEM names, elevations and slopes as separate lists
        dataset_names = []; elevations = []; slopes = []; cum_distances_3D = []              
        for dem_name, profile_points3D  in profiles_points:
            dataset_names.append( dem_name )
            elevations.append( [ point3D.z for point3D in profile_points3D ] )
            slopes.append( self.calculate_slopes_in_DEM_profile( profile_points3D ) )
            dist3D = [ 0.0 ]
            for ndx in range( len( profile_points3D ) - 1 ):
                _, incr_3Ddist, _, _ = ( profile_points3D[ndx] ).distance_uvector( profile_points3D[ndx+1] )
                dist3D.append( dist3D[-1] + incr_3Ddist )
            cum_distances_3D.append(dist3D)            
               
        # define variable for plotting                
        self.profiles = dict( tag='DEM',
                              dataset_names=dataset_names,
                              x_values=x_values,
                              y_values=y_values,
                              cum_distances_2D=cum_distances_2D,
                              cum_distances_3D=cum_distances_3D,
                              elevations=elevations,
                              slopes=slopes)
        
        # process results for export         
        self.export_from_DEM = self.parse_DEM_results_for_export()
        
        # update combobox for 3D line export        
        self.DEM_3D_Export_comboBox.clear()        
        self.DEM_3D_Export_comboBox.addItems( dataset_names )
            
            
        QMessageBox.information( self, "Profiles calculated", "Now you can plot/export" )



    def calculate_profile_from_GPX(self):

        self.profiles = None
               
        source_gpx_path = unicode( self.input_gpx_lineEdit.text() )
        
        doc = xml.dom.minidom.parse( source_gpx_path )

        # get track point values (lat, lon, elev, time)
        trk_measures = []
        for trk_node in doc.getElementsByTagName( 'trk'):
            trkname = trk_node.getElementsByTagName( 'name' )[0].firstChild.data
            trksegments = trk_node.getElementsByTagName( 'trkseg' )
            for trksegment in trksegments:
                trk_pts = trksegment.getElementsByTagName( 'trkpt' )
                for tkr_pt in trk_pts:               
                    gpx_trackpoint = TrackPointGPX( tkr_pt.getAttribute("lat"),
                                                    tkr_pt.getAttribute("lon"),
                                                    tkr_pt.getElementsByTagName("ele")[0].childNodes[0].data,
                                                    tkr_pt.getElementsByTagName("time")[0].childNodes[0].data )
                    trk_measures.append( gpx_trackpoint )
        
        # check for the presence of track points
        if len( trk_measures ) == 0:
            QMessageBox.critical( self, "GPX profile", "No track point found in this file" )
            return            
        
        # calculate delta elevations between consecutive points
        delta_elev_values = [ np.nan ]
        for ndx in range( 1, len ( trk_measures ) ):
            delta_elev_values.append( trk_measures[ndx].elev - trk_measures[ndx-1].elev )        
        
        # covert values into ECEF values (x, y, z in ECEF global coordinate system)        
        trk_ECEFpoints = [ trk_value.toPoint4D() for trk_value in  trk_measures ]
        
        # calculate 3D distances between consecutive points
        dist_3D_values = [ np.nan ]
        for ndx in range( 1, len ( trk_ECEFpoints ) ):
            dist_3D_values.append( trk_ECEFpoints[ndx].distance( trk_ECEFpoints[ndx-1] ) ) 
                    
        # calculate slope along track
        slopes = [ ]
        for delta_elev, dist_3D in zip( delta_elev_values, dist_3D_values ):
            try:
                slopes.append( degrees( asin( delta_elev / dist_3D ) ) )
            except:
                slopes.append( np.nan ) 
        
        # calculate horizontal distance along track
        horiz_dist_values = []
        for slope, dist_3D in zip( slopes, dist_3D_values ):
            try:
                horiz_dist_values.append( dist_3D * cos( radians( slope ) ) )
            except: 
                horiz_dist_values.append( np.nan )
                        
        # defines the cumulative 2D distance values
        cum_distances_2D = [ 0.0 ]
        for ndx in range( 1, len( horiz_dist_values ) ):
            cum_distances_2D.append( cum_distances_2D[-1] + horiz_dist_values[ndx] )          

        # defines the cumulative 3D distance values
        cum_distances_3D = [ 0.0 ]
        for ndx in range( 1, len( dist_3D_values ) ):
            cum_distances_3D.append( cum_distances_3D[-1] + dist_3D_values[ndx] ) 
            
        # define GPX names, elevations and slopes
        dataset_name = [ trkname ]
        lat_values = [ track.lat for track in trk_measures ]
        lon_values = [ track.lon for track in trk_measures ]
        time_values = [ track.time for track in trk_measures ]        
        elevations = [ track.elev for track in trk_measures ]           
        
        # define variable for plotting                
        self.profiles = dict( tag='GPX',
                              lats=lat_values,
                              lons=lon_values,
                              times=time_values,
                              dataset_names=dataset_name,
                              cum_distances_2D=cum_distances_2D,
                              cum_distances_3D=[cum_distances_3D], # [] required for compatibility with DEM plotting
                              elevations=[elevations], # [] required for compatibility with DEM plotting
                              slopes=[slopes]) # [] required for compatibility with DEM plotting

        
        self.export_from_GPX = True
        
        QMessageBox.information( self, "Profile calculated", "Now you can plot/export" )

        
    def parse_DEM_results_for_export(self):

        assert  self.profiles['tag'] == 'DEM'
                
        # definition of output results         
        x_list = self.profiles['x_values']
        y_list = self.profiles['y_values']  
        elev_list = self.profiles['elevations']              
        cumdist_2D_list = self.profiles['cum_distances_2D']
        cumdist_3d_list = self.profiles['cum_distances_3D']
        slope_list = self.profiles['slopes']

        elev_list_zip = zip( *elev_list )
        cumdist_3d_list_zip = zip( *cumdist_3d_list ) 
        slope_list_zip = zip( *slope_list )  

        result_data = []
        for x, y, cum_2d_dist, zs, cum3d_dists, slopes in zip( x_list, y_list, cumdist_2D_list, elev_list_zip, cumdist_3d_list_zip, slope_list_zip ):
            record = [ x, y, cum_2d_dist]
            for z, cum3d_dist, slope in zip( zs, cum3d_dists, slopes ):
                if isnan(z): z = ''
                if isnan(cum3d_dist): cum3d_dist = ''
                if isnan(slope): slope = ''
                record += [z, cum3d_dist, slope ]
            result_data.append( record )
         
        return result_data


        
    def parse_GPX_results_for_export(self):
        

        assert  self.profiles['tag'] == 'GPX'

        # definition of output results        
        lat_list = self.profiles['lats']
        lon_list = self.profiles['lons'] 
        time_list = self.profiles['times']          
        cumdist_2D_list = self.profiles['cum_distances_2D']
        elev_list = self.profiles['elevations'][0] # [0] required for compatibility with DEM processing                  
        cumdist_3d_list = self.profiles['cum_distances_3D'] [0] # [0] required for compatibility with DEM processing
        slope_list = self.profiles['slopes'][0] # [0] required for compatibility with DEM processing

        result_data = []
        for lat, lon, time, elev, cumdist_2D, cumdist_3D, slope in zip( lat_list, lon_list, time_list, elev_list, cumdist_2D_list, cumdist_3d_list, slope_list ):
            if isnan( elev ): elev = ''
            if isnan( cumdist_3D ): cumdist_3D = ''
            if isnan( slope ): slope = ''
            record = [ lat, lon, time, elev, cumdist_2D, cumdist_3D, slope ]
            result_data.append( record )
         
        return result_data


    def valid_profiles_for_plot( self ):
        
        if self.profiles is None or \
           self.profiles['dataset_names'] is None or \
           self.profiles['cum_distances_2D'] is None or \
           self.profiles['elevations'] is None or \
           self.profiles['slopes'] is None:
            return False
            
        return True


    def valid_intervals( self,  values_array_1D ):
        
        assert values_array_1D.ndim == 1
        assert values_array_1D.shape[0] > 0

        valid_list = []
        interval = []
        for i in range( values_array_1D.shape[0] ):
            if isnan( values_array_1D[i] ):
                if len( interval ) > 0: 
                    valid_list.append( interval )
                    interval = []
            else: interval.append( i )
        else:
            if len( interval ) > 0:
                valid_list.append( interval )
         
        intdict_list = []       
        for interval in valid_list:
            if len( interval ) > 1:
                int_dict = dict( start= interval[0], end = interval[-1] )
                intdict_list.append( int_dict )
                
        return intdict_list        
        

    def plot_profiles( self ):
 
        # check state for plotting
        if not self.valid_profiles_for_plot():            
            QMessageBox.critical( self, "Plotting profile", "No profile is available for plotting" )
            return  
        elif not ( self.PlotHeight_checkbox.isChecked() or self.PlotSlope_checkbox.isChecked() ):
            QMessageBox.critical( self, "Plotting profile", "Neither height or slope options are selected" )
            return         

        dataset_names = self.profiles['dataset_names']
        cum_distances_2D = self.profiles['cum_distances_2D']
        elevations = self.profiles['elevations']
        slopes = self.profiles['slopes']
                               
        # defines the extent for the plot window: s min and max     
        profiles_s_min, profiles_s_max = cum_distances_2D[0], cum_distances_2D[-1] 

        # defines z min and max values
        elev_list = [ z for z_values in elevations for z in z_values if not isnan( z ) ]
        plot_z_min, plot_z_max = min( elev_list ), max( elev_list )
        delta_z = plot_z_max - plot_z_min 
        plot_z_min, plot_z_max = plot_z_min - delta_z * 0.05, plot_z_max + delta_z * 0.05

        # defines slope min and max values
        slope_list = [ slope for profile_slopes in slopes for slope in profile_slopes if not isnan( slope ) ]
        profiles_slope_min, profiles_slope_max = min( slope_list ), max( slope_list )
        delta_slope = profiles_slope_max - profiles_slope_min 
        profiles_slope_min, profiles_slope_max = profiles_slope_min - delta_slope*0.2, profiles_slope_max + delta_slope*0.2 

        # map
        profile_window = MplWidget()  

        if self.PlotHeight_checkbox.isChecked() and self.PlotSlope_checkbox.isChecked():
            mpl_code_list = [ 211, 212 ]
        else:
            mpl_code_list = [ 111 ]          

        # for mpl_code in mpl_code_list:
        colors = [ 'orange', 'Green', 'b', 'r', 'g', 'y', 'c', 'k', 'm' ]  

        s_2d_values_array = np.array( cum_distances_2D )
        
        subplot_code = mpl_code_list[0]   
        if self.PlotHeight_checkbox.isChecked():                            
            axes_height = profile_window.canvas.fig.add_subplot( subplot_code )
            axes_height.set_xlim( profiles_s_min, profiles_s_max )
            axes_height.set_ylim( plot_z_min, plot_z_max ) 
            axes_height.set_color_cycle( colors )
            for dem_name, z_values, color in zip( dataset_names, elevations, colors ):              
                z_values_array = np.array( z_values )
                #valid_s_2d_values = s_2d_values_array[ np.isfinite( z_values_array ) ]
                #valid_z_values = z_values_array[ np.isfinite( z_values_array ) ] 
                for val_int in self.valid_intervals( z_values_array ):               
                    axes_height.fill_between( s_2d_values_array[ val_int['start'] : val_int['end']+1 ], 
                                              plot_z_min, 
                                              z_values_array[ val_int['start'] : val_int['end']+1 ], 
                                              facecolor=color, 
                                              alpha=0.1 )                       
                axes_height.plot(cum_distances_2D, z_values,'-', label = unicode(dem_name) )
                
            axes_height.grid(True)
            axes_height.legend(loc = 'upper left', shadow=True)              
  
        if self.PlotSlope_checkbox.isChecked():            
            if len(mpl_code_list) == 2: subplot_code = mpl_code_list[1]
            axes_slope = profile_window.canvas.fig.add_subplot( subplot_code )
            axes_slope.set_xlim( profiles_s_min, profiles_s_max )
            axes_slope.set_ylim( profiles_slope_min, profiles_slope_max )
            axes_slope.set_color_cycle( colors )
            for dem_name, profile_slopes, color in zip( dataset_names, slopes, colors):
                
                slope_values_array = np.array( profile_slopes )
                #valid_s_2d_values = s_2d_values_array[ np.isfinite( slope_values_array ) ]
                #valid_slope_values = slope_values_array[ np.isfinite( slope_values_array ) ]  
                for val_int in self.valid_intervals( slope_values_array ): 
                    #if val_int['end'] == len()              
                    axes_slope.fill_between( s_2d_values_array[ val_int['start'] : val_int['end']+1 ], 
                                             0, 
                                             slope_values_array[ val_int['start'] : val_int['end']+1 ], 
                                             facecolor=color, 
                                             alpha=0.1 )                
                #axes_slope.fill_between( valid_s_2d_values, 0, valid_slope_values, facecolor=color, alpha=0.1 )
                axes_slope.plot(cum_distances_2D, profile_slopes,'-', label = unicode(dem_name) )
                
            axes_slope.grid(True)
            axes_slope.legend(loc = 'upper left', shadow=True)  
                    
        profile_window.canvas.draw() 
        
        self.profile_windows.append(profile_window)

     
    def export_from_DEM_data(self):

        if self.profiles is None or \
           self.profiles['tag'] != 'DEM' or \
           self.export_from_DEM is None:            
            QMessageBox.critical( self, "Saving results", "No DEM-derived profile is available for export" )
            return 
        
        if not ( self.ExportfromDEM_asCSV_checkbox.isChecked() or self.ExportfromDEM_asPtShp_checkbox.isChecked() ):
            QMessageBox.critical( self, "Saving results", "No output format is selected" )
            return   
                          
        # definition of field names        
        dem_names = self.profiles['dataset_names']  
        cum3ddist_headers = ['cumulated_3d_distance']*len(dem_names)
        slopes_headers = ['slopes (degr)']*len(dem_names)
        header_list = ['x', 'y', 'cumulated_2d_distance'] + [ name for sublist in zip(dem_names, cum3ddist_headers, slopes_headers) for name in sublist ]              

        # output for csv file
        if self.ExportfromDEM_asCSV_checkbox.isChecked():            
            self.write_DEM_2D_csv( header_list )

        # output for 2D pt shapefile            
        if self.ExportfromDEM_asPtShp_checkbox.isChecked():
            self.write_DEM_2D_ptshp( dem_names )
        
        QMessageBox.information( self, "Profile export", "Finished" )
        

    def write_DEM_2D_csv( self, header_list ):
               
        fileName = QFileDialog.getSaveFileName(self, 
                                               self.tr("Save results"),
                                                "*.csv",
                                                self.tr("csv (*.csv)"))

        if fileName is None or fileName == '':
            QMessageBox.critical( self, "Saving results", "No file has been defined" )
            return   
        
        header_list = [ unicodedata.normalize('NFKD', unicode(header)).encode('ascii', 'ignore') for header in header_list]
        with open( unicode( fileName ), 'w') as f:
            f.write( ','.join( header_list )+'\n' )
            for rec in self.export_from_DEM:
                out_rec_string = ''
                for val in rec:
                    out_rec_string += str( val ) + ','
                f.write( out_rec_string[:-1]+'\n' )
                
                      
    def write_DEM_2D_ptshp( self, dem_names ):
        
        fileName = QFileDialog.getSaveFileName(self, 
                                               self.tr("Save results as 2D point shapefile"),
                                                "*.shp",
                                                self.tr("shapefile (*.shp)"))

        if fileName is None or fileName == '':
            QMessageBox.critical( self, "Saving results", "No file has been defined" )
            return           

        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName( shape_driver_name )
        if shape_driver is None:
            QMessageBox.critical( self, "Saving results", "%s driver is not available" % shape_driver_name )
            return             
            
        ptshp_datasource = shape_driver.CreateDataSource( unicode( fileName ) )
        if ptshp_datasource is None:
            QMessageBox.critical( self, "Saving results", "Creation of %s shapefile failed" % os.path.split( fileName )[1] )
            return         
        
        ptshp_layer = ptshp_datasource.CreateLayer( 'profile', geom_type=ogr.wkbPoint )
        if ptshp_layer is None:
            QMessageBox.critical( self, "Saving results", "Layer creation failed" )
            return 
                  
        # creates required fields         
        ptshp_layer.CreateField( ogr.FieldDefn( 'id', ogr.OFTInteger ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'x', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'y', ogr.OFTReal ) )       
        ptshp_layer.CreateField( ogr.FieldDefn( 'cum2dis', ogr.OFTReal ) )
        for dem_ndx, dem_name in enumerate( dem_names ):       
            ptshp_layer.CreateField( ogr.FieldDefn( unicodedata.normalize('NFKD', unicode( dem_name[:10] )).encode('ascii', 'ignore'), ogr.OFTReal ) )       
            ptshp_layer.CreateField( ogr.FieldDefn( 'cum3dis'+str(dem_ndx+1), ogr.OFTReal ) )        
            ptshp_layer.CreateField( ogr.FieldDefn( 'slope'+str(dem_ndx+1), ogr.OFTReal ) )        
        
        ptshp_featureDefn = ptshp_layer.GetLayerDefn()
        
        # loops through output records                       
        for ndx, rec in enumerate( self.export_from_DEM ):
            
            pt_feature = ogr.Feature( ptshp_featureDefn )
            
            pt = ogr.Geometry(ogr.wkbPoint)
            pt.SetPoint_2D( 0, rec[0], rec[1] )        
            pt_feature.SetGeometry( pt )
            
            pt_feature.SetField('id', ndx+1 )
            pt_feature.SetField('x', rec[0] )   
            pt_feature.SetField('y', rec[1] ) 
            pt_feature.SetField('cum2dis', rec[2] )  
            for dem_ndx, dem_name in enumerate( dem_names ):
                dem_height = rec[3+dem_ndx*3+0]
                if dem_height != '': pt_feature.SetField( unicodedata.normalize('NFKD', unicode( dem_name[:10] )).encode('ascii', 'ignore'), dem_height )
                cum3ddist = rec[3+dem_ndx*3+1]
                if cum3ddist != '': pt_feature.SetField( 'cum3dis'+str(dem_ndx+1), cum3ddist )
                slope = rec[3+dem_ndx*3+2]
                if slope != '': pt_feature.SetField( 'slope'+str(dem_ndx+1), slope )                  
  
            ptshp_layer.CreateFeature( pt_feature )
            
            pt_feature.Destroy()
            
        ptshp_datasource.Destroy()
                                
                
    def write_DEM_3D_lnshp(self):

        if self.profiles is None or \
           self.profiles['tag'] != 'DEM' or \
           self.export_from_DEM is None:            
            QMessageBox.critical( self, "Saving results", "No DEM-derived profile is available for export" )
            return
                   
        fileName = QFileDialog.getSaveFileName(self, 
                                               self.tr("Save results as line shapefile"),
                                                "*.shp",
                                                self.tr("shapefile (*.shp)"))

        if fileName is None or fileName == '':
            QMessageBox.critical( self, "Saving results", "No file has been defined" )
            return       
    
        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName( shape_driver_name )
        if shape_driver is None:
            QMessageBox.critical( self, "Saving results", "%s driver is not available" % shape_driver_name )
            return             
            
        lnshp_datasource = shape_driver.CreateDataSource( unicode( fileName ) )
        if lnshp_datasource is None:
            QMessageBox.critical( self, "Saving results", "Creation of %s shapefile failed" % os.path.split( fileName )[1] )
            return         
        
        lnshp_layer = lnshp_datasource.CreateLayer( 'profile', geom_type=ogr.wkbLineString25D )
        if lnshp_layer is None:
            QMessageBox.critical( self, "Saving results", "Layer creation failed" )
            return     

        current_dem_ndx = self.DEM_3D_Export_comboBox.currentIndex()
            
        # creates required fields         
        lnshp_layer.CreateField( ogr.FieldDefn( 'id', ogr.OFTInteger ) )      
        lnshp_layer.CreateField( ogr.FieldDefn( 'cum2dis', ogr.OFTReal ) )
        lnshp_layer.CreateField( ogr.FieldDefn( 'cum3dis', ogr.OFTReal ) )
        lnshp_layer.CreateField( ogr.FieldDefn( 'slope', ogr.OFTReal ) )     
    
        lnshp_featureDefn = lnshp_layer.GetLayerDefn()
        
        # loops through output records                     
        for ndx in range( len( self.export_from_DEM )-1 ):
                
            rec_a = self.export_from_DEM[ndx]
            rec_b = self.export_from_DEM[ndx+1]
                            
            x0, y0, z0 = rec_a[0], rec_a[1], rec_a[3+current_dem_ndx*3]
            x1, y1, z1 = rec_b[0], rec_b[1], rec_b[3+current_dem_ndx*3]
            
            if z0 == '' or z1 == '': continue

            ln_feature = ogr.Feature( lnshp_featureDefn )            
            segment_3d = ogr.CreateGeometryFromWkt('LINESTRING(%f %f %f, %f %f %f)' % (x0, y0, z0, x1, y1, z1))       
            ln_feature.SetGeometry( segment_3d ) 
            
            ln_feature.SetField('id', ndx+1 )
            ln_feature.SetField('cum2dis', rec_b[2] )  
            cum3ddist = rec_b[3+current_dem_ndx*3+1]
            if cum3ddist != '': ln_feature.SetField( 'cum3dis', cum3ddist )
            slope = rec_b[3+current_dem_ndx*3+2]
            if slope != '': ln_feature.SetField( 'slope', slope )  
                            
            lnshp_layer.CreateFeature( ln_feature )
            
            ln_feature.Destroy()
            
        lnshp_datasource.Destroy()
        
        QMessageBox.information( self, "Saving 3d line", "Shapefile saved" )
 
 
    def export_from_GPX_data( self ):
        
        if self.profiles is None or \
           self.profiles['tag'] != 'GPX' or \
           self.export_from_GPX is False:            
            QMessageBox.critical( self, "Saving results", "No GPX-derived profile is available for export" )
            return 
    
        if not ( self.ExportfromGPX_asCSV_checkbox.isChecked() or \
                 self.ExportfromGPX_asPtShp_checkbox.isChecked() or \
                 self.ExportfromGPX_asLnShp_checkbox.isChecked()):
            QMessageBox.critical( self, "Saving results", "No output format is selected" )
            return  

        # process results from export         
        gpx_parsed_results = self.parse_GPX_results_for_export()
                
        # definition of field names        
        # track_name = self.profiles['dataset_names']  
        header_list = ['lat', 'lon', 'time', 'elev', 'cumulated_2d_distance', 'cumulated_3d_distance', 'slopes (degr)' ]              
        
        # output for csv file
        if self.ExportfromGPX_asCSV_checkbox.isChecked():         
            self.write_results_as_csv( header_list, gpx_parsed_results )

        # output for 2D pt shapefile            
        if self.ExportfromGPX_asPtShp_checkbox.isChecked():
            self.write_GPX_2D_ptshp( gpx_parsed_results )

        if self.ExportfromGPX_asLnShp_checkbox.isChecked():
            self.write_GPX_3D_lnshp( gpx_parsed_results )
                    
        QMessageBox.information( self, "Profile export", "Finished" )        
        
                      
    def write_GPX_2D_ptshp( self, gpx_parsed_results ):
                
        fileName = QFileDialog.getSaveFileName(self, 
                                               self.tr("Save results as 2D point shapefile"),
                                                "*.shp",
                                                self.tr("shapefile (*.shp)"))

        if fileName is None or fileName == '':
            QMessageBox.critical( self, "Saving results", "No file has been defined" )
            return           

        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName( shape_driver_name )
        if shape_driver is None:
            QMessageBox.critical( self, "Saving results", "%s driver is not available" % shape_driver_name )
            return             
            
        ptshp_datasource = shape_driver.CreateDataSource( unicode( fileName ) )
        if ptshp_datasource is None:
            QMessageBox.critical( self, "Saving results", "Creation of %s shapefile failed" % os.path.split( fileName )[1] )
            return         
        
        ptshp_layer = ptshp_datasource.CreateLayer( 'profile', geom_type=ogr.wkbPoint )
        if ptshp_layer is None:
            QMessageBox.critical( self, "Saving results", "Layer creation failed" )
            return 
                  
        # creates required fields         
        ptshp_layer.CreateField( ogr.FieldDefn( 'id', ogr.OFTInteger ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'lat', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'lon', ogr.OFTReal ) )
        time_field = ogr.FieldDefn( 'time', ogr.OFTString )
        time_field.SetWidth(20)  
        ptshp_layer.CreateField( time_field ) 
        ptshp_layer.CreateField( ogr.FieldDefn( 'elev', ogr.OFTReal ) )      
        ptshp_layer.CreateField( ogr.FieldDefn( 'cum2dist', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'cum3dist', ogr.OFTReal ) )        
        ptshp_layer.CreateField( ogr.FieldDefn( 'slope', ogr.OFTReal ) )        
        
        ptshp_featureDefn = ptshp_layer.GetLayerDefn()
        
        # loops through output records                       
        for ndx, rec in enumerate( gpx_parsed_results ):
            
            pt_feature = ogr.Feature( ptshp_featureDefn )
            
            pt = ogr.Geometry(ogr.wkbPoint)
            pt.SetPoint_2D( 0, rec[1], rec[0] )        
            pt_feature.SetGeometry( pt )
            
            pt_feature.SetField('id', ndx+1 )
            pt_feature.SetField('lon', rec[1] )   
            pt_feature.SetField('lat', rec[0] )
                    
            pt_feature.SetField('time', str( rec[2] ) )
            if rec[3] != '': pt_feature.SetField('elev', rec[3] ) 
            pt_feature.SetField('cum2dist', rec[4] )
            if rec[5] != '': pt_feature.SetField('cum3dist', rec[5] )
            if rec[6] != '': pt_feature.SetField('slope', rec[6] )
                                                              
            ptshp_layer.CreateFeature( pt_feature )
            
            pt_feature.Destroy()
            
        ptshp_datasource.Destroy()
                                
       
    def write_GPX_3D_lnshp( self, gpx_parsed_results ):
     
        fileName = QFileDialog.getSaveFileName(self, 
                                               self.tr("Save results as line shapefile"),
                                                "*.shp",
                                                self.tr("shapefile (*.shp)"))

        if fileName is None or fileName == '':
            QMessageBox.critical( self, "Saving results", "No file has been defined" )
            return       
    
        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName( shape_driver_name )
        if shape_driver is None:
            QMessageBox.critical( self, "Saving results", "%s driver is not available" % shape_driver_name )
            return             
            
        lnshp_datasource = shape_driver.CreateDataSource( unicode( fileName ) )
        if lnshp_datasource is None:
            QMessageBox.critical( self, "Saving results", "Creation of %s shapefile failed" % os.path.split( fileName )[1] )
            return         
        
        lnshp_layer = lnshp_datasource.CreateLayer( 'profile', geom_type=ogr.wkbLineString25D )
        if lnshp_layer is None:
            QMessageBox.critical( self, "Saving results", "Layer creation failed" )
            return     
 
        # creates required fields         
        lnshp_layer.CreateField( ogr.FieldDefn( 'id', ogr.OFTInteger ) )
        time_beg_field = ogr.FieldDefn( 'time_beg', ogr.OFTString )
        time_beg_field.SetWidth(20)  
        lnshp_layer.CreateField( time_beg_field )
        time_end_field = ogr.FieldDefn( 'time_end', ogr.OFTString )
        time_end_field.SetWidth(20)  
        lnshp_layer.CreateField( time_end_field )     
        lnshp_layer.CreateField( ogr.FieldDefn( 'cum2dist', ogr.OFTReal ) )
        lnshp_layer.CreateField( ogr.FieldDefn( 'cum3dist', ogr.OFTReal ) )
        lnshp_layer.CreateField( ogr.FieldDefn( 'slope', ogr.OFTReal ) )     
    
        lnshp_featureDefn = lnshp_layer.GetLayerDefn()
        
        # loops through output records                     
        for ndx in range( len( gpx_parsed_results )-1 ):
                
            rec_a = gpx_parsed_results[ndx]
            rec_b = gpx_parsed_results[ndx+1]
                            
            lon0, lat0, z0 = rec_a[1], rec_a[0], rec_a[3]
            lon1, lat1, z1 = rec_b[1], rec_b[0], rec_b[3]
            
            if z0 == '' or z1 == '': continue

            ln_feature = ogr.Feature( lnshp_featureDefn )            
            segment_3d = ogr.CreateGeometryFromWkt('LINESTRING(%f %f %f, %f %f %f)' % (lon0, lat0, z0, lon1, lat1, z1))       
            ln_feature.SetGeometry( segment_3d ) 
            
            ln_feature.SetField('id', ndx+1 )
            ln_feature.SetField('time_beg', str( rec_a[2] ) ) 
            ln_feature.SetField('time_end', str( rec_b[2] ) )           
            ln_feature.SetField('cum2dist', rec_b[4] )  
            if rec_b[5] != '': ln_feature.SetField( 'cum3dist', rec_b[5] )
            if rec_b[6] != '': ln_feature.SetField( 'slope', rec_b[6] )  
                            
            lnshp_layer.CreateFeature( ln_feature )
            
            ln_feature.Destroy()
            
        lnshp_datasource.Destroy()        


    def set_layer_params_in_comboboxes( self, layer_comboBox, comboBoxes ):
        
        if len(self.pointLayers) == 0:
            return
        
        shape_qgis_ndx = self.stratif_layer_comboBox.currentIndex() - 1 # minus 1 to account for initial text in combo box
        if shape_qgis_ndx < 0: 
            return
        
        layer = self.pointLayers[ shape_qgis_ndx ]
        fields = layer.dataProvider().fields()     
        field_names = [ field.name() for field in fields.toList()]
                
        for ndx, combobox in enumerate( comboBoxes ):
            combobox.clear()
            if ndx == 0:
                combobox.addItems( ["none"])
            combobox.addItems( field_names )
          
        return layer
                   
            
    def set_stratification_layer(self):        
                
        self.stratification_layer = self.set_layer_params_in_comboboxes( self.stratif_layer_comboBox, self.stratification_comboBoxes )
 

    def get_current_combobox_values( self, combobox_list ):
        
        return [ combobox.currentText() for combobox in combobox_list ]


    def define_structural_segment( self, solution, profile_length ):
        
        slope_radians = solution[ 'slope_radians' ]
        intersection_downward_sense = solution[ 'intersection_downward_sense' ]
        projected_point = solution[ 'projected_point' ]
        horiz_distance = solution[ 'horizontal_distance' ]        
        
        segment_horiz_scale_factor = 50.0   
        segment_emilength = profile_length / segment_horiz_scale_factor
        
        delta_height = segment_emilength * sin( float( slope_radians ) )
        delta_distance = segment_emilength * cos( float( slope_radians ) )
        
        z0 = projected_point.z

        structural_segment_s = [ horiz_distance - delta_distance, horiz_distance + delta_distance ]
        structural_segment_z = [ z0 + delta_height, z0 - delta_height ]
                    
        if intersection_downward_sense == "left":
            structural_segment_z = [ z0 - delta_height, z0 + delta_height ]       
        
        return structural_segment_s, structural_segment_z
        
                
    def plot_cross_section( self ):
         
        # check state for plotting
        if not self.valid_profiles_for_plot():            
            QMessageBox.critical( self, "Plotting cross_section", "No profile is available for plotting" )
            return

        # TODO:  manage case for possible nan z values
        projected_z = [ solution[ 'projected_point' ].z for solution in self.projected_struct_dataset if  0.0 <= solution[ 'horizontal_distance' ] <= self.section_length ]
        
        dem_name = self.profiles['dataset_names'][-1]
        cum_distances_2D = self.profiles['cum_distances_2D']
        elevations = self.profiles['elevations'][-1]
                               
        # defines the extent for the plot window: s min and max     
        profiles_s_min, profiles_s_max = cum_distances_2D[0], cum_distances_2D[-1] 

        # defines z min and max values
        elev_list = [ z for z in elevations if not isnan( z ) ]
        plot_z_min, plot_z_max = min( elev_list + projected_z ), max( elev_list + projected_z )
        
        delta_z = plot_z_max - plot_z_min 
        plot_z_min, plot_z_max = plot_z_min - delta_z * 0.05, plot_z_max + delta_z * 0.05

        # cross-section window
        cross_section_window = MplWidget( 'Cross-section')  
        
        subplot_code = 111  
        axes_height = cross_section_window.canvas.fig.add_subplot( subplot_code )
        axes_height.set_xlim( profiles_s_min, profiles_s_max )
        axes_height.set_ylim( plot_z_min, plot_z_max ) 
       
        axes_height.plot( cum_distances_2D, elevations,'-', color='orange', label = unicode(dem_name) )        

        # TODO:  manage case for possible nan z values
        projected_s = [ solution[ 'horizontal_distance' ] for solution in self.projected_struct_dataset if 0.0 <= solution[ 'horizontal_distance' ] <= self.section_length ]
        axes_height.plot( projected_s, projected_z,'o', color='red' ) 
        
        # plot segments representing structural data       
        for solution in self.projected_struct_dataset:
            if 0.0 <= solution[ 'horizontal_distance' ] <= self.section_length:
                structural_segment_s, structural_segment_z = self.define_structural_segment( solution, self.section_length )            
                axes_height.plot( structural_segment_s, structural_segment_z,'-', color='red' )
                      
        axes_height.grid( True )        
        axes_height.set_aspect('equal')
         
        cross_section_window.canvas.draw()         
        self.cross_section_windows.append( cross_section_window )

  
    def conditions_for_cross_section(self):

        # check if only one dem selected
        if len( self.selected_dems ) != 1 or len( self.dem_parameters ) != 1:
            return False, "One DEM (and only one DEM) has to be used in the profile section"        
        # check if profile exists
        if self.profile_points == []:               
            return False, "Profile has not been calculated"
        # check that section is made up of only two points
        if len( self.profile_points ) != 2:        
            return False, "Profile is not made up by only two points"
        
        return True, ''        
          

    def get_3d_points( self, struct_pts_2d, selected_dem, dem_parameters ):      
        
        struct_pts_3d = []
        for point_2d in struct_pts_2d:
            interp_z = self.interpolate_point_z( selected_dem, dem_parameters, point_2d )
            struct_pts_3d.append( Point(point_2d.x, point_2d.y, interp_z ) )
            
        return struct_pts_3d
            
                      
    def create_cross_section(self):
        
        # check pre-conditions
        conditions, msg = self.conditions_for_cross_section()
        if not conditions:
            QMessageBox.critical( self, 
                                  "Error while creating cross-section", 
                                  msg )            
            return                

        # extract the names of the required fields for the stratification layer
        stratification_field_list = self.get_current_combobox_values( self.stratification_comboBoxes )
           
        # retrieve selected points with attributes        
        success, result = get_selected_features_attr( self.stratification_layer, stratification_field_list ) 
        if not success:
            QMessageBox.critical( self, "Error while creating cross-section", result )            
            return
        else:
            feature_attrs =  result                  

        ### process point attributes to obtain ###
        
        # - IDs of structural points
        struct_pts_ids = [ rec[2] for rec in feature_attrs ]
        
        # - 3D structural points, with x, y, and z extracted from the current DEM
        struct_pts_3d = self.get_3d_points( [ Point(rec[0], rec[1]) for rec in feature_attrs ],
                                            self.selected_dems[0], 
                                            self.dem_parameters[0] ) 

        # - structural planes (3D), as geological planes
        try:
            structural_planes = [ GeolPlane( rec[3], rec[4] ) for rec in feature_attrs ]
        except:
            QMessageBox.critical( self, "Error while creating cross-section", "Check chosen fields for possible errors" )            
            return
        
        # - zip together the two data sets                     
        assert len( struct_pts_3d ) == len( structural_planes )
        structural_data = zip( struct_pts_3d, structural_planes, struct_pts_ids )   
               
        ### map points onto section ###
        
        # calculation of Cartesian plane expressing section plane
        sect_pt_1, sect_pt_2 = self.profile_points
        
        section_init_pt = Point( sect_pt_1.x, sect_pt_1.y, 0.0 )
        section_final_pt = Point( sect_pt_2.x, sect_pt_2.y, 0.0 )

        section_final_pt_up = Point( section_final_pt.x, section_final_pt.y, 1000.0 ) # arbitrary point on the same vertical as sect_pt_2    
        section_cartes_plane = CartesianPlane().from_points(section_init_pt, section_final_pt, section_final_pt_up)    
        section_vector = section_init_pt.to_vector( section_final_pt )
        self.section_length = section_vector.lenght_hor()
        
        self.projected_struct_dataset = project_struct_pt_on_section( structural_data, section_init_pt, section_cartes_plane, section_vector )
        
        ### draw points onto section ###
        self.plot_cross_section( )
                                         
                                         
    def save_crosssect_results(self):
        
        if self.projected_struct_dataset is None:            
            QMessageBox.critical( self, "Saving results", "No cross-section is available for export" )
            return 
    
        if not ( self.save_crosssect_results_asCSV_checkbox.isChecked() or \
                 self.save_crosssect_results_asPtShp_checkbox.isChecked()):
            QMessageBox.critical( self, "Saving results", "No output format is selected" )
            return  
        
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
                                               
        parsed_crosssect_results = self.parse_crosssect_results_for_export( self.projected_struct_dataset )

        # output for csv file
        if self.save_crosssect_results_asCSV_checkbox.isChecked():
            self.write_results_as_csv( header_list, parsed_crosssect_results )

        # output for 3D pt shapefile            
        if self.save_crosssect_results_asPtShp_checkbox.isChecked():
            self.write_crosssect_result_ptshp( header_list, parsed_crosssect_results )
                    
        QMessageBox.information( self, "Saving cross-section results", "Completed" )
          

    def parse_crosssect_results_for_export( self, projected_struct_dataset ):
        
        # definition of output results        
        result_data = []
        for projected_datum in projected_struct_dataset:            
            pt_id = projected_datum['id']
            or_pt_x = projected_datum['structural_pt'].x
            or_pt_y = projected_datum['structural_pt'].y            
            or_pt_z = projected_datum['structural_pt'].z            
            pr_pt_x = projected_datum['projected_point'].x
            pr_pt_y = projected_datum['projected_point'].y            
            pr_pt_z = projected_datum['projected_point'].z            
            s = projected_datum['horizontal_distance']
            or_dipdir = projected_datum['structural_plane']._dipdir
            or_dipangle = projected_datum['structural_plane']._dipangle
            tr_dipangle = degrees( projected_datum['slope_radians'] )
            tr_dipdir = projected_datum['intersection_downward_sense']
            
            record = [ pt_id, or_pt_x, or_pt_y, or_pt_z, pr_pt_x, pr_pt_y, pr_pt_z, s, or_dipdir, or_dipangle, tr_dipangle, tr_dipdir ]
            result_data.append( record )
         
        return result_data

           
    def write_results_as_csv( self, header_list, parsed_crosssect_results ):
        
        fileName = QFileDialog.getSaveFileName(self, 
                                               self.tr("Save results"),
                                                "*.csv",
                                                self.tr("csv (*.csv)"))

        if fileName is None or fileName == '':
            QMessageBox.critical( self, "Saving results", "No file has been defined" )
            return   

        header_list = [ unicodedata.normalize('NFKD', unicode(header)).encode('ascii', 'ignore') for header in header_list]
        with open( unicode( fileName ), 'w') as f:
            f.write( ','.join( header_list )+'\n' )
            for rec in parsed_crosssect_results:
                out_rec_string = ''
                for val in rec:
                    out_rec_string += str( val ) + ','
                f.write( out_rec_string[:-1]+'\n' )
    

    def write_crosssect_result_ptshp( self, header_list, parsed_crosssect_results ):

        fileName = QFileDialog.getSaveFileName(self,
                                               self.tr("Save results as a 3D point shapefile"),
                                                "*.shp",
                                                self.tr("shapefile (*.shp)"))

        if fileName is None or fileName == '':
            QMessageBox.critical( self, "Saving results", "No file has been defined" )
            return

        shape_driver_name = "ESRI Shapefile"
        shape_driver = ogr.GetDriverByName( shape_driver_name )
        if shape_driver is None:
            QMessageBox.critical( self, "Saving results", "%s driver is not available" % shape_driver_name )
            return

        ptshp_datasource = shape_driver.CreateDataSource( unicode( fileName ) )
        if ptshp_datasource is None:
            QMessageBox.critical( self, "Saving results", "Creation of %s shapefile failed" % os.path.split( fileName )[1] )
            return

        ptshp_layer = ptshp_datasource.CreateLayer( 'profile', geom_type=ogr.wkbPoint25D )
        if ptshp_layer is None:
            QMessageBox.critical( self, "Saving results", "Layer creation failed" )
            return

        # creates required fields
        ptshp_layer.CreateField( ogr.FieldDefn( 'id', ogr.OFTString ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'or_pt_x', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'or_pt_y', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'or_pt_z', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'prj_pt_x', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'prj_pt_y', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'prj_pt_z', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 's', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'or_dpdir', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'or_dpang', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'tr_dpang', ogr.OFTReal ) )
        ptshp_layer.CreateField( ogr.FieldDefn( 'tr_dpdir', ogr.OFTString ) )

        ptshp_featureDefn = ptshp_layer.GetLayerDefn()

        # loops through output records
        for ndx, rec in enumerate( parsed_crosssect_results ):

            pt_id, or_pt_x, or_pt_y, or_pt_z, pr_pt_x, pr_pt_y, pr_pt_z, s, or_dipdir, or_dipangle, tr_dipangle, tr_dipdir = rec

            pt_feature = ogr.Feature( ptshp_featureDefn )

            pt = ogr.Geometry( ogr.wkbPoint25D )
            pt.SetPoint( 0, pr_pt_x, pr_pt_y, pr_pt_z )
            pt_feature.SetGeometry( pt )

            pt_feature.SetField( 'id', str( pt_id ) )
            pt_feature.SetField( 'or_pt_x', or_pt_x )
            pt_feature.SetField( 'or_pt_y', or_pt_y )
            pt_feature.SetField( 'or_pt_z', or_pt_z )
            pt_feature.SetField( 'prj_pt_x', pr_pt_x )
            pt_feature.SetField( 'prj_pt_y', pr_pt_y )
            pt_feature.SetField( 'prj_pt_z', pr_pt_z )
            pt_feature.SetField( 's', s )
            pt_feature.SetField( 'or_dpdir',or_dipdir )
            pt_feature.SetField( 'or_dpang', or_dipangle )
            pt_feature.SetField( 'tr_dpang', tr_dipangle )
            pt_feature.SetField( 'tr_dpdir', str( tr_dipdir ) )

            ptshp_layer.CreateFeature( pt_feature )

            pt_feature.Destroy()

        ptshp_datasource.Destroy()


    
    
