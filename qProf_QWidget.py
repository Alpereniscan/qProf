
from typing import Tuple

import unicodedata

import pickle


from .gsf.array_utils import *
from .gsf.sorting import *

from .gis_utils.intersections import *
from .gis_utils.profile import *
from .gis_utils.qgs_tools import *
from .gis_utils.statistics import *
from .gis_utils.errors import *

from .qt_utils.filesystem import *
from .qt_utils.tools import *

from .string_utils.utils_string import *

from .config.settings import *
from .config.output import *

from .qProf_plotting import *
from .qProf_export import *


marker_mapping = dict(
    circle="o",
    point=".",
    square="s",
    star="*",
    plus="+",
    x="x",
    diamond="D",
    nothing="None",
)

def extract_values_from_layer(
        layer,
        field_ndx,
selectedfeaturesonly=False) -> Union[str, List[Any]]:

    try:
        if selectedfeaturesonly:
            features = layer.selectedFeatures()
        else:
            features = layer.getFeatures()

        return [feature[field_ndx] for feature in features]

    except Exception as e:

        return str(e)


def extract_from_line3d(
        line_layer,
        field_indices,
) -> Union[str, List[Tuple[List[Any], List[Union[MultiLine, Line]]]]]:

    try:

        if line_layer.selectedFeatureCount() > 0:
            features = line_layer.selectedFeatures()
        else:
            features = line_layer.getFeatures()

        geodataframe = []

        for feature in features:

            values = [feature[ndx] for ndx in field_indices]

            geom = feature.geometry()

            if geom.isMultipart():

                lines = []

                for part in geom.parts():

                    points = []

                    for point in part.vertices():
                        points.append(Point(point.x(), point.y(), point.z()))

                    line = Line(points)
                    lines.append(line)

                geometry = MultiLine(lines)

            else:

                points = []

                for point in part.vertices():
                    points.append(Point(point.x(), point.y(), point.z()))

                geometry = Line(points)

            geodataframe.append((values, geometry))

        return geodataframe

    except Exception as e:

        return str(e)


def create_line_in_project_crs(
        profile_processed_line,
        line_layer_crs,
        on_the_fly_projection,
        project_crs
):

    if not on_the_fly_projection:
        return profile_processed_line
    else:
        return profile_processed_line.crs_project(line_layer_crs, project_crs)


def line_traces_with_order_and_labels(
        line_shape,
        label_field_ndx: Optional[numbers.Integral],
        order_field_ndx: Optional[numbers.Integral]
):

    try:

        profile_orig_lines, label_values, order_values = line2d_geoms_with_infos(
            line_shape,
            label_field_ndx,
            order_field_ndx
        )

    except VectorInputException as error_msg:

        return False, error_msg

    return True, (profile_orig_lines, label_values, order_values)


def line2d_layer_params(dialog):

    line_layer = dialog.line_shape
    multiple_profiles = dialog.qrbtLineIsMultiProfile.isChecked()
    label_field_ndx = dialog.Trace2D_label_field_comboBox.currentIndex()
    order_field_ndx = dialog.Trace2D_order_field_comboBox.currentIndex()

    return line_layer, multiple_profiles, label_field_ndx, order_field_ndx


def extract_2d_lines_laying_on_dem(
        structural_line_layer,
        densify_proj_crs_distance,
        on_the_fly_projection,
        project_crs,
        demLayer,
        demParams,
) -> List[MultiLine]:

    multilines2d_project_crs = extract_multiline2d_list(
        structural_line_layer,
        on_the_fly_projection,
        project_crs
    )

    # densify with provided densify distance

    densified_proj_crs_MultiLine2D_list = [multiline_2d.densify_2d_multiline(densify_proj_crs_distance) for
                                           multiline_2d in
                                           multilines2d_project_crs]

    # project to DEM CRS

    if on_the_fly_projection and demParams.crs != project_crs:

        densified_dem_crs_MultiLine2D_list = [multiline_2d.crs_project(project_crs, demParams.crs) for
                                              multiline_2d in densified_proj_crs_MultiLine2D_list]

    else:

        densified_dem_crs_MultiLine2D_list = densified_proj_crs_MultiLine2D_list

    # interpolate z values from DEM

    z_list = [interpolate_z(demLayer, demParams, pt_2d) for multiline_2d in densified_dem_crs_MultiLine2D_list
              for line_2d in multiline_2d.lines for pt_2d in line_2d.pts]

    # extract x-y pairs for creation of 3D points
    xy_list = [(pt_2d.x, pt_2d.y) for multiline_2d in densified_proj_crs_MultiLine2D_list for line_2d in
               multiline_2d.lines for pt_2d in line_2d.pts]

    # re-create MultiLine list structure with 3D points having project CRS

    ndx = -1

    multiline_3d_proj_crs_list = []

    for multiline_2d in densified_proj_crs_MultiLine2D_list:

        multiline_3d_list = []

        for line_2d in multiline_2d.lines:

            line_3d_pts_list = []

            for _ in line_2d.pts:
                ndx += 1
                line_3d_pts_list.append(Point(xy_list[ndx][0], xy_list[ndx][1], z_list[ndx]))

            multiline_3d_list.append(Line(line_3d_pts_list))

        multiline_3d_proj_crs_list.append(MultiLine(multiline_3d_list))

    return multiline_3d_proj_crs_list


def distance_projected_pts(x, y, delta_x, delta_y, src_crs, dest_crs):

    qgspt_start_src_crs = qgs_pt(x, y)
    qgspt_end_src_crs = qgs_pt(x + delta_x, y + delta_y)

    qgspt_start_dest_crs = project_qgs_point(qgspt_start_src_crs, src_crs, dest_crs)
    qgspt_end_dest_crs = project_qgs_point(qgspt_end_src_crs, src_crs, dest_crs)

    pt2_start_dest_crs = Point(qgspt_start_dest_crs.x(), qgspt_start_dest_crs.y())
    pt2d_end_dest_crs = Point(qgspt_end_dest_crs.x(), qgspt_end_dest_crs.y())

    return pt2_start_dest_crs.dist_2d(pt2d_end_dest_crs)


class QProfQWidget(QWidget):

    colors = [
        'orange',
        'green',
        'red',
        'grey',
        'brown',
        'yellow',
        'magenta',
        'black',
        'blue',
        'white',
        'cyan',
        'chartreuse'
    ]

    map_digitations = 0

    def __init__(self, plugin_name, canvas):

        super(QProfQWidget, self).__init__()

        self.plugin_name = plugin_name
        self.canvas = canvas

        self.current_directory = os.path.dirname(__file__)

        self.settings = QSettings("alberese", self.plugin_name)
        self.settings_gpxdir_key = "gpx/last_used_dir"

        self.choose_message = "choose"

        self.demline_source = "demline"
        self.gpxfile_source = "gpxfile"

        self.digitized_profile_line2dt = None

        self.projected_lines_classification_colors = dict()
        self.intersected_polygon_classification_colors = dict()

        self.input_geoprofiles = GeoProfilesSet()  # main instance for the geoprofiles

        self.profile_windows = []  # used to maintain alive the plots, i.e. to avoid the C++ objects being destroyed

        self.plane_attitudes_styles = []

        self.setup_gui()

    def init_line2d_topo_labels(self):
        """
        Initialize topographic label and order parameters.

        :return:
        """

        self.profiles_labels = None
        self.profiles_order = None

    def setup_gui(self):

        self.dialog_layout = QVBoxLayout()
        self.main_widget = QTabWidget()

        self.main_widget.addTab(self.setup_topoprofile_tab(), "Topography")
        self.main_widget.addTab(self.setup_geology_section_tab(), "Geology")
        self.main_widget.addTab(self.setup_export_section_tab(), "Export")
        self.main_widget.addTab(self.setup_about_tab(), "Help")

        self.prj_input_line_comboBox.currentIndexChanged.connect(self.update_linepoly_layers_boxes)
        self.inters_input_line_comboBox.currentIndexChanged.connect(self.update_linepoly_layers_boxes)
        self.inters_input_polygon_comboBox.currentIndexChanged.connect(self.update_linepoly_layers_boxes)

        self.struct_line_refresh_lyr_combobox()
        self.struct_polygon_refresh_lyr_combobox()

        QgsProject.instance().layerWasAdded.connect(self.struct_point_refresh_lyr_combobox)
        QgsProject.instance().layerWasAdded.connect(self.struct_line_refresh_lyr_combobox)
        QgsProject.instance().layerWasAdded.connect(self.struct_polygon_refresh_lyr_combobox)

        QgsProject.instance().layerRemoved.connect(self.struct_point_refresh_lyr_combobox)
        QgsProject.instance().layerRemoved.connect(self.struct_line_refresh_lyr_combobox)
        QgsProject.instance().layerRemoved.connect(self.struct_polygon_refresh_lyr_combobox)

        self.dialog_layout.addWidget(self.main_widget)
        self.setLayout(self.dialog_layout)
        self.adjustSize()
        self.setWindowTitle(self.plugin_name)

    def setup_topoprofile_tab(self):

        topoprofile_widget = QWidget()
        topoprofile_layout = QVBoxLayout()

        ## Input data

        toposources_groupbox = QGroupBox(topoprofile_widget)
        toposources_groupbox.setTitle("Topographic profile sources")

        toposources_layout = QVBoxLayout()

        ####

        data_input_toolbox = QToolBox()

        dem_input_widget = QWidget()
        dem_input_layout = QVBoxLayout()

        ## input DEM section

        dem_input_groupbox = QGroupBox()
        dem_input_groupbox.setTitle("Input DEMs")

        inputDEM_Layout = QVBoxLayout()
        self.DefineSourceDEMs_pushbutton = QPushButton(self.tr("Define source DEMs"))
        self.DefineSourceDEMs_pushbutton.clicked.connect(self.define_source_DEMs)
        inputDEM_Layout.addWidget(self.DefineSourceDEMs_pushbutton)
        dem_input_groupbox.setLayout(inputDEM_Layout)

        dem_input_layout.addWidget(dem_input_groupbox)

        ## input Line layer section

        input_line2d_groupbox = QGroupBox()
        input_line2d_groupbox.setTitle("Input line")
        input_line2d_layout = QGridLayout()

        self.digitized_line_source_radiobutton = QRadioButton(self.tr("Digitized line"))
        self.digitized_line_source_radiobutton.setChecked(True)
        input_line2d_layout.addWidget(self.digitized_line_source_radiobutton, 0, 0, 1, 1)

        #

        self.digitize_line_pushbutton = QPushButton(self.tr("Digitize line"))
        self.digitize_line_pushbutton.clicked.connect(self.digitize_line)
        self.digitize_line_pushbutton.setToolTip("Digitize a line on the map.\n"
                                                     "Left click: add point\n"
                                                     "Right click: end adding point\n"
                                                     "From: Define topographic sources (below)\n"
                                                     "you can use also an existing line\n"
                                                     "or a point list")
        input_line2d_layout.addWidget(self.digitize_line_pushbutton, 0, 1, 1, 1)

        self.clear_digitized_line_pushbutton = QPushButton(self.tr("Clear"))
        self.clear_digitized_line_pushbutton.clicked.connect(self.clear_rubberband)
        input_line2d_layout.addWidget(self.clear_digitized_line_pushbutton, 0, 2, 1, 1)

        self.save_digitized_line_pushbutton = QPushButton(self.tr("Save"))
        self.save_digitized_line_pushbutton.clicked.connect(self.save_rubberband)
        input_line2d_layout.addWidget(self.save_digitized_line_pushbutton, 0, 3, 1, 1)

        #

        self.load_line2d_layer_radiobutton = QRadioButton(self.tr("Line layer"))
        input_line2d_layout.addWidget(self.load_line2d_layer_radiobutton, 1, 0, 1, 1)

        self.choose_line2d_layer_pushbutton = QPushButton(self.tr("Choose layer"))
        self.choose_line2d_layer_pushbutton.clicked.connect(self.load_line2d_layer)
        input_line2d_layout.addWidget(self.choose_line2d_layer_pushbutton, 1, 1, 1, 3)

        self.points2d_list_radiobutton = QRadioButton(self.tr("Point list"))
        input_line2d_layout.addWidget(self.points2d_list_radiobutton, 2, 0, 1, 1)
        self.points2d_create_list_pushbutton = QPushButton(self.tr("Create list"))
        self.points2d_create_list_pushbutton.clicked.connect(self.load_points2d_list)
        input_line2d_layout.addWidget(self.points2d_create_list_pushbutton, 2, 1, 1, 3)

        # trace sampling distance

        input_line2d_layout.addWidget(QLabel(self.tr("line densify distance")), 3, 0, 1, 1)
        self.profile_densify_distance_lineedit = QLineEdit()
        input_line2d_layout.addWidget(self.profile_densify_distance_lineedit, 3, 1, 1, 3)

        input_line2d_groupbox.setLayout(input_line2d_layout)

        dem_input_layout.addWidget(input_line2d_groupbox)

        dem_input_widget.setLayout(dem_input_layout)

        data_input_toolbox.addItem(dem_input_widget, "DEM input")

        # GPX widget

        gpx_input_qwidget = QWidget()
        gpx_input_layout = QGridLayout()

        gpx_input_layout.addWidget(QLabel(self.tr("Choose input file:")), 0, 0, 1, 1)

        self.gpx_file_lineedit = QLineEdit()
        self.gpx_file_lineedit.setPlaceholderText("my_track.gpx")
        gpx_input_layout.addWidget(self.gpx_file_lineedit, 0, 1, 1, 1)

        self.gpx_file_select_pushbutton = QPushButton("...")
        self.gpx_file_select_pushbutton.clicked.connect(self.select_input_gpx_file)
        gpx_input_layout.addWidget(self.gpx_file_select_pushbutton, 0, 2, 1, 1)

        gpx_input_qwidget.setLayout(gpx_input_layout)

        data_input_toolbox.addItem(gpx_input_qwidget, "GPX input")

        #

        toposources_layout.addWidget(data_input_toolbox)

        #

        read_topo_data_widget = QWidget()
        read_topo_data_layout = QGridLayout()

        self.dem_line_source_radiobutton = QRadioButton("DEM input")
        self.dem_line_source_radiobutton.setChecked(True)
        read_topo_data_layout.addWidget(self.dem_line_source_radiobutton, 0, 0, 1, 1)

        self.gpx_source_radiobutton = QRadioButton("GPX input")
        read_topo_data_layout.addWidget(self.gpx_source_radiobutton, 0, 1, 1, 1)

        self.invert_profile_checkbox = QCheckBox("Invert orientation")
        read_topo_data_layout.addWidget(self.invert_profile_checkbox, 1, 0, 1, 1)

        self.read_source_data_pushbutton = QPushButton("Read source data")
        self.read_source_data_pushbutton.clicked.connect(self.create_topo_profiles)
        read_topo_data_layout.addWidget(self.read_source_data_pushbutton, 2, 0, 1, 3)

        read_topo_data_widget.setLayout(read_topo_data_layout)

        ##

        toposources_layout.addWidget(read_topo_data_widget)

        toposources_groupbox.setLayout(toposources_layout)

        topoprofile_layout.addWidget(toposources_groupbox)

        ## Profile statistics

        profile_statistics_groupbox = QGroupBox(topoprofile_widget)
        profile_statistics_groupbox.setTitle("Profile statistics")

        profile_statistics_layout = QGridLayout()

        self.calculate_profile_statistics_pushbutton = QPushButton(self.tr("Calculate profile statistics"))
        self.calculate_profile_statistics_pushbutton.clicked.connect(self.calculate_profile_statistics)

        profile_statistics_layout.addWidget(self.calculate_profile_statistics_pushbutton, 0, 0, 1, 3)

        profile_statistics_groupbox.setLayout(profile_statistics_layout)

        topoprofile_layout.addWidget(profile_statistics_groupbox)

        ## Create profile section

        plot_profile_groupbox = QGroupBox(topoprofile_widget)
        plot_profile_groupbox.setTitle('Profile plot')

        plot_profile_layout = QGridLayout()

        self.create_topographic_profile_pushbutton = QPushButton(self.tr("Create topographic profile"))
        self.create_topographic_profile_pushbutton.clicked.connect(self.plot_topo_profiles)

        plot_profile_layout.addWidget(self.create_topographic_profile_pushbutton, 0, 0, 1, 4)

        plot_profile_groupbox.setLayout(plot_profile_layout)

        topoprofile_layout.addWidget(plot_profile_groupbox)

        ###################

        topoprofile_widget.setLayout(topoprofile_layout)

        return topoprofile_widget

    def setup_geology_section_tab(self):

        section_geology_QWidget = QWidget()
        section_geology_layout = QVBoxLayout()

        geology_toolbox = QToolBox()

        ### Point project toolbox

        xs_point_proj_QWidget = QWidget()
        qlytXsPointProj = QVBoxLayout()

        ## input section

        qgbxXsInputPointProj = QGroupBox(xs_point_proj_QWidget)
        qgbxXsInputPointProj.setTitle('Input')

        qlytXsInputPointProj = QGridLayout()

        # input point geological layer

        qlytXsInputPointProj.addWidget(QLabel("Layer "),
                                       0, 0, 1, 1)

        self.prj_struct_point_comboBox = QComboBox()
        self.prj_struct_point_comboBox.currentIndexChanged.connect(self.update_point_layers_boxes)

        qlytXsInputPointProj.addWidget(self.prj_struct_point_comboBox, 0, 1, 1, 6)
        self.struct_point_refresh_lyr_combobox()

        qlytXsInputPointProj.addWidget(QLabel("Fields:"), 1, 0, 1, 1)

        qlytXsInputPointProj.addWidget(QLabel("Id"), 1, 1, 1, 1)

        self.proj_point_id_fld_comboBox = QComboBox()
        qlytXsInputPointProj.addWidget(self.proj_point_id_fld_comboBox, 1, 2, 1, 1)

        self.qrbtPlotPrjUseDipDir = QRadioButton("Dip dir.")
        self.qrbtPlotPrjUseDipDir.setChecked(True)
        qlytXsInputPointProj.addWidget(self.qrbtPlotPrjUseDipDir, 1, 3, 1, 1)

        self.qrbtPlotPrjUseRhrStrike = QRadioButton("RHR str.")
        qlytXsInputPointProj.addWidget(self.qrbtPlotPrjUseRhrStrike, 2, 3, 1, 1)

        self.qcbxProjPointOrientFld = QComboBox()
        qlytXsInputPointProj.addWidget(self.qcbxProjPointOrientFld, 1, 4, 1, 1)

        qlytXsInputPointProj.addWidget(QLabel("Dip"), 1, 5, 1, 1)
        self.qcbxProjPointDipAngFld = QComboBox()
        qlytXsInputPointProj.addWidget(self.qcbxProjPointDipAngFld, 1, 6, 1, 1)

        qgbxXsInputPointProj.setLayout(qlytXsInputPointProj)
        qlytXsPointProj.addWidget(qgbxXsInputPointProj)

        ## interpolation method

        xs_method_point_proj_QGroupBox = QGroupBox(xs_point_proj_QWidget)
        xs_method_point_proj_QGroupBox.setTitle('Project along')

        xs_method_point_proj_Layout = QGridLayout()

        self.nearest_point_proj_choice = QRadioButton("nearest intersection")
        self.nearest_point_proj_choice.setChecked(True)
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
        qlytXsPointProj.addWidget(xs_method_point_proj_QGroupBox)

        ## Plot groupbox

        xs_plot_proj_QGroupBox = QGroupBox(xs_point_proj_QWidget)
        xs_plot_proj_QGroupBox.setTitle('Plot geological attitudes')

        xs_plot_proj_Layout = QGridLayout()

        xs_plot_proj_Layout.addWidget(QLabel("Labels"), 0, 0, 1, 1)

        self.plot_prj_add_trendplunge_label = QCheckBox("or./dip")
        xs_plot_proj_Layout.addWidget(self.plot_prj_add_trendplunge_label, 0, 1, 1, 1)

        self.plot_prj_add_pt_id_label = QCheckBox("id")
        xs_plot_proj_Layout.addWidget(self.plot_prj_add_pt_id_label, 0, 3, 1, 1)

        xs_plot_proj_Layout.addWidget(QLabel("Markers"), 1, 0, 1, 1)

        xs_plot_proj_Layout.addWidget(QLabel("color"), 1, 1, 1, 1)
        self.proj_point_color_QgsColorButton = QgsColorButton()
        self.proj_point_color_QgsColorButton.setColor(QColor('red'))
        xs_plot_proj_Layout.addWidget(self.proj_point_color_QgsColorButton, 1, 2, 1, 1)

        xs_plot_proj_Layout.addWidget(QLabel("symbol"), 1, 3, 1, 1)
        self.proj_point_marker_symbol_QComboBox = QComboBox()
        self.proj_point_marker_symbol_QComboBox.addItems(marker_mapping.keys())
        xs_plot_proj_Layout.addWidget(self.proj_point_marker_symbol_QComboBox, 1, 4, 1, 1)


        xs_plot_proj_Layout.addWidget(QLabel("size"), 1, 5, 1, 1)
        self.proj_point_marker_size_QSpinBox = QSpinBox()
        self.proj_point_marker_size_QSpinBox.setMaximum(10)
        self.proj_point_marker_size_QSpinBox.setValue(5)
        xs_plot_proj_Layout.addWidget(self.proj_point_marker_size_QSpinBox, 1, 6, 1, 1)

        xs_plot_proj_Layout.addWidget(QLabel("line width"), 2, 1, 1, 1)
        self.proj_point_line_width_QSpinBox = QSpinBox()
        self.proj_point_line_width_QSpinBox.setMaximum(10)
        self.proj_point_line_width_QSpinBox.setValue(1)
        xs_plot_proj_Layout.addWidget(self.proj_point_line_width_QSpinBox, 2, 2, 1, 1)

        xs_plot_proj_Layout.addWidget(QLabel("opacity"), 2, 3, 1, 1)

        self.proj_point_opacity_QSpinBox = QSpinBox()
        self.proj_point_opacity_QSpinBox.setMaximum(100)
        self.proj_point_opacity_QSpinBox.setValue(100)
        xs_plot_proj_Layout.addWidget(self.proj_point_opacity_QSpinBox, 2, 4, 1, 1)

        self.project_point_pushbutton = QPushButton(self.tr("Plot"))
        self.project_point_pushbutton.clicked.connect(self.project_attitudes)
        xs_plot_proj_Layout.addWidget(self.project_point_pushbutton, 3, 0, 1, 4)

        self.reset_point_pushbutton = QPushButton(self.tr("Reset plot"))
        self.reset_point_pushbutton.clicked.connect(self.reset_struct_point_projection)

        xs_plot_proj_Layout.addWidget(self.reset_point_pushbutton, 3, 4, 1, 3)

        xs_plot_proj_QGroupBox.setLayout(xs_plot_proj_Layout)
        qlytXsPointProj.addWidget(xs_plot_proj_QGroupBox)

        self.flds_prj_point_comboBoxes = [self.proj_point_id_fld_comboBox,
                                          self.qcbxProjPointOrientFld,
                                          self.qcbxProjPointDipAngFld,
                                          self.proj_point_indivax_trend_fld_comboBox,
                                          self.proj_point_indivax_plunge_fld_comboBox]

        ##

        xs_point_proj_QWidget.setLayout(qlytXsPointProj)
        geology_toolbox.addItem(xs_point_proj_QWidget,
                                "Project geological attitudes")

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

        xs_input_line_proj_Layout.addWidget(QLabel("Derive elevation information from"), 1, 0, 1, 1)
        self.project_line_2d_choice = QRadioButton("DEM")
        self.project_line_2d_choice.setChecked(True)
        self.project_line_3d_choice = QRadioButton("layer (has to be 3D)")
        xs_input_line_proj_Layout.addWidget(self.project_line_2d_choice, 1, 1, 1, 1)
        xs_input_line_proj_Layout.addWidget(self.project_line_3d_choice, 1, 2, 1, 1)

        xs_input_line_proj_Layout.addWidget(QLabel("Line classification field"), 2, 0, 1, 1)
        self.id_fld_line_prj_comboBox = QComboBox()
        xs_input_line_proj_Layout.addWidget(self.id_fld_line_prj_comboBox, 2, 1, 1, 3)

        xs_input_line_proj_Layout.addWidget(QLabel("Line densify distance"), 3, 0, 1, 1)
        self.project_line_densify_distance_lineedit = QLineEdit()
        xs_input_line_proj_Layout.addWidget(self.project_line_densify_distance_lineedit, 3, 1, 1, 3)

        self.flds_prj_line_comboBoxes = [self.id_fld_line_prj_comboBox]

        xs_input_line_proj_QGroupBox.setLayout(xs_input_line_proj_Layout)
        xs_line_proj_Layout.addWidget(xs_input_line_proj_QGroupBox)

        ## interpolation method

        xs_method_line_proj_QGroupBox = QGroupBox(xs_line_proj_QWidget)
        xs_method_line_proj_QGroupBox.setTitle('Project')

        xs_method_line_proj_Layout = QGridLayout()

        xs_method_line_proj_Layout.addWidget(QLabel("Projection axis:"), 0, 0, 1, 1)

        xs_method_line_proj_Layout.addWidget(QLabel("trend (degrees)"), 0, 1, 1, 1)

        self.common_axis_line_trend_SpinBox = QDoubleSpinBox()
        self.common_axis_line_trend_SpinBox.setMinimum(0.0)
        self.common_axis_line_trend_SpinBox.setMaximum(359.9)
        self.common_axis_line_trend_SpinBox.setDecimals(1)
        xs_method_line_proj_Layout.addWidget(self.common_axis_line_trend_SpinBox, 0, 2, 1, 1)

        xs_method_line_proj_Layout.addWidget(QLabel("plunge (degrees)"), 0, 3, 1, 1)

        self.common_axis_line_plunge_SpinBox = QDoubleSpinBox()
        self.common_axis_line_plunge_SpinBox.setMinimum(0.0)
        self.common_axis_line_plunge_SpinBox.setMaximum(89.9)
        self.common_axis_line_plunge_SpinBox.setDecimals(1)
        xs_method_line_proj_Layout.addWidget(self.common_axis_line_plunge_SpinBox, 0, 4, 1, 1)

        # colors options

        self.projected_lines_define_style_pushbutton = QPushButton("Define line style as:")
        xs_method_line_proj_Layout.addWidget(self.projected_lines_define_style_pushbutton, 1, 0, 1, 1)

        self.projected_lines_define_style_pushbutton.clicked.connect(self.define_line_projection_style)

        self.unique_color_choice_radiobutton = QRadioButton("unique color")
        self.classified_colors_choice_radiobutton = QRadioButton("categorized")

        self.unique_color_choice_radiobutton.setChecked(True)

        xs_method_line_proj_Layout.addWidget(self.unique_color_choice_radiobutton, 1, 1, 1, 1)
        xs_method_line_proj_Layout.addWidget(self.classified_colors_choice_radiobutton, 1, 2, 1, 1)

        self.projected_lines_save_style_pushbutton = QPushButton("Save style")
        self.projected_lines_load_style_pushbutton = QPushButton("Load style")

        xs_method_line_proj_Layout.addWidget(self.projected_lines_save_style_pushbutton, 1, 3, 1, 1)
        xs_method_line_proj_Layout.addWidget(self.projected_lines_load_style_pushbutton, 1, 4, 1, 1)

        self.projected_lines_save_style_pushbutton.clicked.connect(self.save_projected_line_styles)
        self.projected_lines_load_style_pushbutton.clicked.connect(self.load_projected_line_styles)

        # calculate profile

        self.project_line_pushbutton = QPushButton(self.tr("Plot traces"))
        self.project_line_pushbutton.clicked.connect(self.plot_projected_lines)
        xs_method_line_proj_Layout.addWidget(self.project_line_pushbutton, 2, 0, 1, 4)

        self.project_line_add_labels = QCheckBox("with labels")
        xs_method_line_proj_Layout.addWidget(self.project_line_add_labels, 2, 4, 1, 1)

        self.reset_curves_pushbutton = QPushButton(self.tr("Reset traces"))
        self.reset_curves_pushbutton.clicked.connect(self.reset_structural_lines_projection)

        xs_method_line_proj_Layout.addWidget(self.reset_curves_pushbutton, 3, 0, 1, 5)

        xs_method_line_proj_QGroupBox.setLayout(xs_method_line_proj_Layout)
        xs_line_proj_Layout.addWidget(xs_method_line_proj_QGroupBox)

        ## 

        xs_line_proj_QWidget.setLayout(xs_line_proj_Layout)
        geology_toolbox.addItem(xs_line_proj_QWidget,
                                "Project geological traces")

        ## END Line project toolbox

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
        self.struct_line_refresh_lyr_combobox()

        inters_line_input_Layout.addWidget(QLabel("Id field"), 1, 0, 1, 1)
        self.inters_input_id_fld_line_comboBox = QComboBox()
        inters_line_input_Layout.addWidget(self.inters_input_id_fld_line_comboBox, 1, 1, 1, 3)

        self.flds_inters_line_comboBoxes = [self.inters_input_id_fld_line_comboBox]

        inters_line_input_Layout.addWidget(QLabel("Color"), 2, 0, 1, 1)
        self.inters_line_point_color_QgsColorButton = QgsColorButton()
        self.inters_line_point_color_QgsColorButton.setColor(QColor('blue'))
        inters_line_input_Layout.addWidget(self.inters_line_point_color_QgsColorButton, 2, 1, 1, 1)

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
        self.line_inters_reset_pushbutton.clicked.connect(self.reset_lineaments_intersections)
        inters_line_do_Layout.addWidget(self.line_inters_reset_pushbutton, 2, 0, 1, 4)

        inters_line_do_QGroupBox.setLayout(inters_line_do_Layout)
        line_intersect_Layout.addWidget(inters_line_do_QGroupBox)

        # END do section

        line_intersect_QWidget.setLayout(line_intersect_Layout)
        geology_toolbox.addItem(line_intersect_QWidget,
                                "Intersect line layer")

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
        self.struct_polygon_refresh_lyr_combobox()

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

        self.inters_polygon_define_styles_pushbutton = QPushButton(self.tr("Define polygon style"))
        self.inters_polygon_save_styles_pushbutton = QPushButton(self.tr("Save style"))
        self.inters_polygon_load_styles_pushbutton = QPushButton(self.tr("Load style"))

        self.inters_polygon_define_styles_pushbutton.clicked.connect(self.define_polygon_styles)
        self.inters_polygon_save_styles_pushbutton.clicked.connect(self.save_polygon_styles)
        self.inters_polygon_load_styles_pushbutton.clicked.connect(self.load_polygon_styles)

        inters_polygon_do_Layout.addWidget(self.inters_polygon_define_styles_pushbutton, 0, 0, 1, 2)
        inters_polygon_do_Layout.addWidget(self.inters_polygon_save_styles_pushbutton, 0, 2, 1, 1)
        inters_polygon_do_Layout.addWidget(self.inters_polygon_load_styles_pushbutton, 0, 3, 1, 1)

        self.inters_polygon_do_pushbutton = QPushButton(self.tr("Intersect"))
        self.inters_polygon_do_pushbutton.clicked.connect(self.do_polygon_intersection)
        inters_polygon_do_Layout.addWidget(self.inters_polygon_do_pushbutton, 1, 0, 1, 4)

        self.polygon_inters_reset_pushbutton = QPushButton(self.tr("Reset intersections"))
        self.polygon_inters_reset_pushbutton.clicked.connect(self.reset_polygon_intersections)
        inters_polygon_do_Layout.addWidget(self.polygon_inters_reset_pushbutton, 2, 0, 1, 4)

        inters_polygon_do_QGroupBox.setLayout(inters_polygon_do_Layout)
        polygon_intersect_Layout.addWidget(inters_polygon_do_QGroupBox)

        # END do section

        polygon_intersect_QWidget.setLayout(polygon_intersect_Layout)
        geology_toolbox.addItem(polygon_intersect_QWidget,
                                "Intersect polygon layer")

        # END Polygon intersection section

        # widget final setup

        section_geology_layout.addWidget(geology_toolbox)

        section_geology_QWidget.setLayout(section_geology_layout)

        return section_geology_QWidget

    def define_polygon_styles(self):

        try:

            # get structural layer index

            layer_qgis_ndx = self.inters_input_polygon_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box

            # get id field

            layer_id_field_ndx = self.inters_polygon_classifaction_field_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box

            # define structural layer

            qgis_layer = self.current_polygon_layers[layer_qgis_ndx]

            values = extract_values_from_layer(
                layer=qgis_layer,
                field_ndx=layer_id_field_ndx,
            )

            if not isinstance(values, List):

                if isinstance(values, str):
                    err_msg = "Error in style definitin. Is input defined?"
                else:
                    err_msg = "Error while getting layer id values"

                warn(
                    self,
                    self.plugin_name,
                    err_msg
                )
                return

            features_classification_set = set(values)

            # define classification colors

            dialog = ClassificationColorsDialog(
                self.plugin_name,
                features_classification_set,
                self.intersected_polygon_classification_colors,
            )

            if dialog.exec_():
                features_classification_colors_dict = self.classification_colors(dialog)
            else:
                warn(self,
                     self.plugin_name,
                     "No color chosen")
                return

            if len(features_classification_colors_dict) == 0:

                warn(self,
                     self.plugin_name,
                     "No defined colors")
                return

            else:

                self.intersected_polygon_classification_colors = features_classification_colors_dict

        except Exception as e:

            return f"Error with polygon style definition: {e}"

    def save_polygon_styles(self):

        try:

            file_pth = new_file_path(
                self,
                "Save graphical parameters as file",
                "*.pkl",
                "pickle (*.pkl *.PKL)"
            )

            if not file_pth:
                return

            with open(file_pth, 'wb') as handle:
                pickle.dump(
                    self.intersected_polygon_classification_colors,
                    handle,
                    protocol=pickle.HIGHEST_PROTOCOL
                )

            info(
                self,
                self.plugin_name,
                f"Graphical parameters saved in {file_pth}"
            )

        except Exception as e:

            warn(
                self,
                self.plugin_name,
                f"Error: {e}"
            )

    def load_polygon_styles(self):

        try:

            file_pth = old_file_path(
                self,
                "Load graphical parameters from file",
                "*.pkl",
                "pickle (*.pkl *.PKL)"
            )

            if not file_pth:
                return

            with open(file_pth, 'rb') as handle:
                self.intersected_polygon_classification_colors = pickle.load(handle)

            info(
                self,
                self.plugin_name,
                f"Graphical parameters loaded from {file_pth}"
            )

        except Exception as e:

            warn(
                self,
                self.plugin_name,
                f"Error: {e}"
            )

    def do_export_image(self):

        try:
            profile_window = self.profile_windows[-1]
        except:
            warn(self,
                 self.plugin_name,
                 "Profile not yet calculated")
            return

        dialog = FigureExportDialog(self.plugin_name)

        if dialog.exec_():

            try:
                fig_width_inches = float(dialog.figure_width_inches_QLineEdit.text())
            except:
                warn(self,
                     self.plugin_name,
                     "Error in figure width value")
                return

            try:
                fig_resolution_dpi = int(dialog.figure_resolution_dpi_QLineEdit.text())
            except:
                warn(self,
                     self.plugin_name,
                     "Error in figure resolution value")
                return

            try:
                fig_font_size_pts = float(dialog.figure_fontsize_pts_QLineEdit.text())
            except:
                warn(self,
                     self.plugin_name,
                     "Error in font size value")

            try:
                fig_outpath = str(dialog.figure_outpath_QLineEdit.text())
            except:
                warn(self,
                     self.plugin_name,
                     "Error in figure output path")
                return

            try:
                top_space_value = float(dialog.top_space_value_QDoubleSpinBox.value())
            except:
                warn(self,
                     self.plugin_name,
                     "Error in figure top space value")
                return

            try:
                left_space_value = float(dialog.left_space_value_QDoubleSpinBox.value())
            except:
                warn(self,
                     self.plugin_name,
                     "Error in figure left space value")
                return

            try:
                right_space_value = float(dialog.right_space_value_QDoubleSpinBox.value())
            except:
                warn(self,
                     self.plugin_name,
                     "Error in figure right space value")
                return

            try:
                bottom_space_value = float(dialog.bottom_space_value_QDoubleSpinBox.value())
            except:
                warn(self,
                     self.plugin_name,
                     "Error in figure bottom space value")
                return

            try:
                blank_width_space = float(dialog.blank_width_space_value_QDoubleSpinBox.value())
            except:
                warn(self,
                     self.plugin_name,
                     "Error in figure blank width space value")
                return

            try:
                blank_height_space = float(dialog.blank_height_space_value_QDoubleSpinBox.value())
            except:
                warn(self,
                     self.plugin_name,
                     "Error in figure blank height space value")
                return

        else:

            warn(self,
                 self.plugin_name,
                 "No export figure defined")
            return

        figure = profile_window.canvas.fig

        fig_current_width, fig_current_height = figure.get_size_inches()
        fig_scale_factor = fig_width_inches / fig_current_width
        figure.set_size_inches(fig_width_inches, fig_scale_factor * fig_current_height)

        for axis in figure.axes:
            for label in (axis.get_xticklabels() + axis.get_yticklabels()):
                label.set_fontsize(fig_font_size_pts)

        figure.subplots_adjust(wspace=blank_width_space, hspace=blank_height_space, left=left_space_value,
                               right=right_space_value, top=top_space_value, bottom=bottom_space_value)

        try:
            figure.savefig(str(fig_outpath), dpi=fig_resolution_dpi,bbox_inches= 'tight')
        except:
            warn(self,
                 self.plugin_name,
                 "Error with image saving")
        else:
            info(self,
                 self.plugin_name,
                 "Image saved")

    def do_export_topo_profiles(self):

        def get_source_type():

            if dialog.src_allselecteddems_QRadioButton.isChecked():
                return ["all_dems"]
            elif dialog.src_singledem_QRadioButton.isChecked():
                return ["single_dem", dialog.src_singledemlist_QComboBox.currentIndex()]
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

        def export_topography():

            def parse_geoprofile_data(
                geoprofile
            ):

                # definition of output results

                xs = geoprofile.topo_profiles.planar_xs
                ys = geoprofile.topo_profiles.planar_ys
                elev_list = geoprofile.topo_profiles.profile_zs
                cumdist2Ds = geoprofile.topo_profiles.profile_s
                cumdist3Ds = geoprofile.topo_profiles.profile_s3ds
                slopes = geoprofile.topo_profiles.profile_dirslopes

                elevs_zipped = list(zip(*elev_list))
                cumdist3Ds_zipped = list(zip(*cumdist3Ds))
                slopes_zipped = list(zip(*slopes))

                parsed_data = []
                rec_id = 0
                for x, y, cum_2d_dist, zs, cum3d_dists, slopes \
                        in zip(
                    xs,
                    ys,
                    cumdist2Ds,
                    elevs_zipped,
                    cumdist3Ds_zipped,
                    slopes_zipped):

                    rec_id += 1
                    record = [rec_id, x, y, cum_2d_dist]
                    for z, cum3d_dist, slope in zip(zs, cum3d_dists, slopes):
                        if isnan(z):
                            z = ''
                        if isnan(cum3d_dist):
                            cum3d_dist = ''
                        if isnan(slope):
                            slope = ''
                        record += [z, cum3d_dist, slope]
                    parsed_data.append(record)

                return parsed_data

            def export_topography_all_dems(
                out_format,
                outfile_path,
                proj_sr
            ):

                geoprofile = self.input_geoprofiles.geoprofile(0)
                if geoprofile.source_data_type != self.demline_source:
                    warn(self,
                         self.plugin_name,
                         "No DEM-derived profile defined")
                    return

                # definition of field names

                dem_names = geoprofile.get_current_dem_names()

                dem_headers = []
                cum3ddist_headers = []
                slopes_headers = []
                for ndx in range(len(dem_names)):
                    dem_headers.append(
                        unicodedata.normalize('NFKD', str(dem_names[ndx][:10])).encode('ascii', 'ignore').decode("utf-8") )
                    cum3ddist_headers.append("cds3d_" + str(ndx + 1))
                    slopes_headers.append("slopd_" + str(ndx + 1))

                multi_dem_header_list = dem_header_common + [name for sublist in
                                                             zip(dem_headers, cum3ddist_headers, slopes_headers) for
                                                             name in
                                                             sublist]

                # extraction of results

                geoprofiles_topography_data = []
                for geoprofile in self.input_geoprofiles.geoprofiles:
                    geoprofiles_topography_data.append(parse_geoprofile_data(geoprofile))

                if out_format == "csv":
                    success, msg = write_topography_multidems_csv(
                        outfile_path,
                        multi_dem_header_list,
                        self.profiles_labels,
                        self.profiles_order,
                        geoprofiles_topography_data)
                    if not success:
                        warn(self,
                             self.plugin_name,
                             msg)
                elif out_format == "shapefile - point":
                    success, msg = write_topography_multidems_ptshp(
                        outfile_path,
                        multi_dem_header_list,
                        dem_names,
                        self.profiles_labels,
                        self.profiles_order,
                        geoprofiles_topography_data,
                        proj_sr)
                    if not success:
                        warn(self,
                             self.plugin_name,
                             msg)
                elif out_format == "shapefile - line":
                    success, msg = write_topography_multidems_lnshp(
                        outfile_path,
                        multi_dem_header_list,
                        dem_names,
                        self.profiles_labels,
                        self.profiles_order,
                        geoprofiles_topography_data,
                        proj_sr)
                    if not success:
                        warn(self,
                             self.plugin_name,
                             msg)
                else:
                    error(
                        parent=self,
                        header=self.plugin_name,
                        msg="Debug: error in export all DEMs")
                    return

                if success:
                    info(self,
                         self.plugin_name,
                         "Profiles export completed")

            def export_topography_single_dem(
                    out_format,
                    ndx_dem_to_export,
                    outfile_path,
                    prj_srs
            ):

                geoprofile = self.input_geoprofiles.geoprofile(0)
                if geoprofile.source_data_type != self.demline_source:
                    warn(
                        self,
                        self.plugin_name,
                        "No DEM-derived profile defined")
                    return

                # process results for data export

                geoprofiles_topography_data = []
                for geoprofile in self.input_geoprofiles.geoprofiles:
                    geoprofiles_topography_data.append(parse_geoprofile_data(geoprofile))

                # definition of field names
                header_list = dem_header_common + dem_single_dem_header

                if out_format == "csv":
                    success, msg = write_topography_singledem_csv(
                        outfile_path,
                        header_list,
                        self.profiles_labels,
                        self.profiles_order,
                        geoprofiles_topography_data,
                        ndx_dem_to_export)
                    if not success:
                        warn(
                            self,
                             self.plugin_name,
                             msg
                        )
                elif out_format == "shapefile - point":
                    success, msg = write_topography_singledem_ptshp(
                        outfile_path,
                        header_list,
                        self.profiles_labels,
                        self.profiles_order,
                        geoprofiles_topography_data,
                        ndx_dem_to_export,
                        prj_srs)
                    if not success:
                        warn(self,
                             self.plugin_name,
                             msg)
                elif out_format == "shapefile - line":
                    success, msg = write_topography_singledem_lnshp(
                        outfile_path,
                        header_list,
                        self.profiles_labels,
                        self.profiles_order,
                        geoprofiles_topography_data,
                        ndx_dem_to_export,
                        prj_srs)
                    if not success:
                        warn(self,
                             self.plugin_name,
                             msg)
                else:
                    error(self,
                          self.plugin_name,
                          "Debug: error in export single DEM")
                    return

                if success:
                    info(self,
                         self.plugin_name,
                         "Profile export completed")

            def export_topography_gpx_data(
                out_format,
                output_filepath,
                prj_srs
            ):

                def export_parse_gpx_results():

                    # definition of output results

                    geoprofile = self.input_geoprofiles.geoprofile(0)
                    topo_profile = geoprofile.topo_profiles
                    lats = topo_profile.lats
                    lons = topo_profile.lons
                    times = topo_profile.times
                    cumdist2Ds = topo_profile.profile_s
                    elevs = topo_profile.profile_zs[0]  # [0] required for compatibility with DEM processing
                    cumdist3Ds = topo_profile.profile_s3ds[0]  # [0] required for compatibility with DEM processing
                    dirslopes = topo_profile.profile_dirslopes[
                        0]  # [0] required for compatibility with DEM processing

                    result_data = []
                    rec_id = 0
                    for lat, lon, time, elev, cumdist_2D, cumdist_3D, slope in \
                            zip(lats,
                                lons,
                                times,
                                elevs,
                                cumdist2Ds,
                                cumdist3Ds,
                                dirslopes):

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

                geoprofile = self.input_geoprofiles.geoprofile(0)
                if geoprofile.source_data_type != self.gpxfile_source:
                    warn(self,
                         self.plugin_name,
                         "No GPX-derived profile defined")
                    return

                # process results from export
                gpx_parsed_results = export_parse_gpx_results()

                # definition of field names
                gpx_header = ["id", "lat", "lon", "time", "elev", "cds2d", "cds3d", "dirslop"]

                if out_format == "csv":
                    success, msg = write_generic_csv(
                        output_filepath,
                        gpx_header,
                        gpx_parsed_results)
                    if not success:
                        warn(self,
                             self.plugin_name,
                             msg)
                elif out_format == "shapefile - point":
                    success, msg = write_topography_gpx_ptshp(
                        output_filepath,
                        gpx_header,
                        gpx_parsed_results,
                        prj_srs)
                    if not success:
                        warn(self,
                             self.plugin_name,
                             msg)
                elif out_format == "shapefile - line":
                    success, msg = write_topography_gpx_lnshp(
                        output_filepath,
                        gpx_header,
                        gpx_parsed_results,
                        prj_srs)
                    if not success:
                        warn(self,
                             self.plugin_name,
                             msg)
                else:
                    error(self,
                          self.plugin_name,
                          "Debug: error in export single DEM")
                    return

                if success:
                    info(self,
                         self.plugin_name,
                         "Profile export completed")

            if output_source[0] == "all_dems":
                export_topography_all_dems(
                    output_format,
                    output_filepath,
                    project_crs_osr
                )
            elif output_source[0] == "single_dem":
                ndx_dem_to_export = output_source[1]
                export_topography_single_dem(
                    output_format,
                    ndx_dem_to_export,
                    output_filepath,
                    project_crs_osr
                )
            elif output_source[0] == "gpx_file":
                export_topography_gpx_data(
                    output_format,
                    output_filepath,
                    project_crs_osr
                )
            else:
                error(self,
                      self.plugin_name,
                      "Debug: output choice not correctly defined")
                return

        try:

            geoprofile = self.input_geoprofiles.geoprofile(0)
            geoprofile.topo_profiles.profile_s

        except:

            warn(self,
                 self.plugin_name,
                 "Profiles not yet calculated")
            return

        selected_dems_params = geoprofile.topo_profiles.dem_params
        dialog = TopographicProfileExportDialog(
            self.plugin_name,
            selected_dems_params
        )

        if dialog.exec_():

            output_source = get_source_type()
            if not output_source:
                warn(self,
                     self.plugin_name,
                     "Error in output source")
                return

            output_format = get_format_type()
            if output_format == "":
                warn(self,
                     self.plugin_name,
                     "Error in output format")
                return

            output_filepath = dialog.outpath_QLineEdit.text()
            if len(output_filepath) == 0:
                warn(self,
                     self.plugin_name,
                     "Error in output path")
                return
            add_to_project = dialog.load_output_checkBox.isChecked()
        else:
            warn(self,
                 self.plugin_name,
                 "No export defined")
            return

        # get project CRS information

        project_crs_osr = get_prjcrs_as_proj4str(self.canvas)

        export_topography()

        # add theme to QGis project

        if 'shapefile' in output_format and add_to_project:
            try:
                layer = QgsVectorLayer(output_filepath,
                                       QFileInfo(output_filepath).baseName(),
                                       "ogr")
                QgsProject.instance().addMapLayer(layer)
            except:
                QMessageBox.critical(self, "Result", "Unable to load layer in project")
                return

    def setup_export_section_tab(self):

        qwdtImportExport = QWidget()
        qlytImportExport = QVBoxLayout()

        # Export section        

        qgbxExport = QGroupBox(qwdtImportExport)
        qgbxExport.setTitle('Export')

        qlytExport = QGridLayout()

        self.qpbtExportImage = QPushButton("Figure")
        qlytExport.addWidget(self.qpbtExportImage, 1, 0, 1, 4)
        self.qpbtExportImage.clicked.connect(self.do_export_image)

        self.qpbtExportTopographicProfile = QPushButton("Topographic profile data")
        qlytExport.addWidget(self.qpbtExportTopographicProfile, 2, 0, 1, 4)
        self.qpbtExportTopographicProfile.clicked.connect(self.do_export_topo_profiles)

        self.qpbtExportProjectGeolAttitudes = QPushButton("Projected geological attitude data")
        qlytExport.addWidget(self.qpbtExportProjectGeolAttitudes, 3, 0, 1, 4)
        self.qpbtExportProjectGeolAttitudes.clicked.connect(self.do_export_project_geol_attitudes)

        self.qpbtExportProjectGeolLines = QPushButton("Projected geological line data")
        qlytExport.addWidget(self.qpbtExportProjectGeolLines, 4, 0, 1, 4)
        self.qpbtExportProjectGeolLines.clicked.connect(self.do_export_project_geol_traces)

        self.qpbtExportLineIntersections = QPushButton("Line intersection data")
        qlytExport.addWidget(self.qpbtExportLineIntersections, 5, 0, 1, 4)
        self.qpbtExportLineIntersections.clicked.connect(self.do_export_line_intersections)

        self.qpbtExportPolygonIntersections = QPushButton("Polygon intersection data")
        qlytExport.addWidget(self.qpbtExportPolygonIntersections, 6, 0, 1, 4)
        self.qpbtExportPolygonIntersections.clicked.connect(self.do_export_polygon_intersections)

        qgbxExport.setLayout(qlytExport)
        qlytImportExport.addWidget(qgbxExport)

        qwdtImportExport.setLayout(qlytImportExport)

        return qwdtImportExport

    def setup_about_tab(self):

        qwdtAbout = QWidget()
        qlytAbout = QVBoxLayout()

        # About section

        about_textBrwsr = QTextBrowser(qwdtAbout)
        url_path = "file:///{}/help/help.html".format(os.path.dirname(__file__))
        about_textBrwsr.setSource(QUrl(url_path))
        about_textBrwsr.setSearchPaths(['{}/help'.format(os.path.dirname(__file__))])
        qlytAbout.addWidget(about_textBrwsr)

        qwdtAbout.setLayout(qlytAbout)

        return qwdtAbout

    def stop_rubberband(self):

        try:
            self.canvas_end_profile_line()
        except:
            pass

        try:
            self.clear_rubberband()
        except:
            pass

    def create_topo_profiles(self):

        selected_dems = None
        selected_dem_parameters = None

        sample_distance = None
        source_profile_lines = None

        if self.dem_line_source_radiobutton.isChecked():
            topo_source_type = self.demline_source
        elif self.gpx_source_radiobutton.isChecked():
            topo_source_type = self.gpxfile_source
        else:
            warn(self,
                 self.plugin_name,
                 "Debug: source data type undefined")
            return

        self.input_geoprofiles = GeoProfilesSet()  # reset any previous created profiles

        if topo_source_type == self.demline_source:

            try:

                selected_dems = self.selected_dems
                selected_dem_parameters = self.selected_dem_parameters

            except Exception as e:

                warn(self,
                     self.plugin_name,
                     f"Input DEMs definition not correct: {e}")
                return

            try:

                sample_distance = float(self.profile_densify_distance_lineedit.text())
                assert sample_distance > 0.0

            except Exception as e:

                warn(self,
                     self.plugin_name,
                     f"Sample distance value not correct: {e}"
                     )
                return

            if self.digitized_line_source_radiobutton.isChecked():

                if self.digitized_profile_line2dt is None or \
                        self.digitized_profile_line2dt.num_pts < 2:

                    warn(self,
                         self.plugin_name,
                         "No digitized line available")
                    return

                source_profile_lines = [self.digitized_profile_line2dt]

            else:

                self.stop_rubberband()

                try:

                    source_profile_lines = self.profiles_lines

                except:

                    warn(self,
                         self.plugin_name,
                         "DEM-line profile source not correctly created [1]")
                    return

                if source_profile_lines is None:
                    warn(self,
                         self.plugin_name,
                         "DEM-line profile source not correctly created [2]")
                    return

        elif topo_source_type == self.gpxfile_source:

            self.stop_rubberband()

            try:
                source_gpx_path = str(self.gpx_file_lineedit.text())
                if source_gpx_path == '':
                    warn(self,
                         self.plugin_name,
                         "Source GPX file is not defined")
                    return
            except Exception as e:
                warn(self,
                     self.plugin_name,
                     f"Source GPX file not correctly defined: {e}"
                     )
                return

        else:
            warn(self,
                 self.plugin_name,
                 "Debug: uncorrect type source for topo sources def")
            return

        # calculates profiles

        invert_profile = self.invert_profile_checkbox.isChecked()

        if topo_source_type == self.demline_source:  # sources are DEM(s) and line

            # check total number of points in line(s) to create
            estimated_total_num_pts = 0
            for profile_line in source_profile_lines:
                profile_length = profile_line.length_2d
                profile_num_pts = profile_length / sample_distance
                estimated_total_num_pts += profile_num_pts

            estimated_total_num_pts = int(ceil(estimated_total_num_pts))

            if estimated_total_num_pts > pt_num_threshold:
                warn(
                    parent=self,
                    header=self.plugin_name,
                    msg="There are {} estimated points (limit is {}) in profile(s) to create.".format(
                        estimated_total_num_pts, pt_num_threshold) +
                        "\nPlease increase sample distance value"
                )
                return

            for profile_line in source_profile_lines:

                try:

                    topo_profiles = topoprofiles_from_dems(
                        self.canvas,
                        profile_line,
                        sample_distance,
                        selected_dems,
                        selected_dem_parameters,
                        invert_profile
                    )

                except Exception as e:

                    warn(self,
                         self.plugin_name,
                         "Error with data source read: {}".format(e))
                    return

                if topo_profiles is None:
                    warn(self,
                         self.plugin_name,
                         "Debug: profile not created")
                    return

                geoprofile = GeoProfile()
                geoprofile.source_data_type = topo_source_type
                geoprofile.original_line = profile_line
                geoprofile.sample_distance = sample_distance
                geoprofile.set_topo_profiles(topo_profiles)

                self.input_geoprofiles.append(geoprofile)

        elif topo_source_type == self.gpxfile_source:  # source is GPX file

            try:

                topo_profiles = topoprofiles_from_gpxfile(
                    source_gpx_path,
                    invert_profile,
                    self.gpxfile_source
                )

            except Exception as e:

                warn(self,
                     self.plugin_name,
                     "Error with profile calculation from GPX file: {}".format(e))
                return

            if topo_profiles is None:

                warn(self,
                     self.plugin_name,
                     "Debug: profile not created")
                return

            geoprofile = GeoProfile()
            geoprofile.source_data_type = topo_source_type
            geoprofile.original_line = source_profile_lines
            geoprofile.sample_distance = sample_distance
            geoprofile.set_topo_profiles(topo_profiles)

            self.input_geoprofiles.append(geoprofile)

        else:  # source type error

            error(self,
                  self.plugin_name,
                  "Debug: profile calculation not defined")
            return

        info(self,
             self.plugin_name,
             "Data profile read")

    def get_dem_resolution_in_prj_crs(self, dem, dem_params, on_the_fly_projection, prj_crs):

        cellsizeEW, cellsizeNS = dem_params.cellsizeEW, dem_params.cellsizeNS
        xMin, yMin = dem_params.xMin, dem_params.yMin

        if on_the_fly_projection and dem.crs() != prj_crs:
            cellsizeEW_prj_crs = distance_projected_pts(xMin, yMin, cellsizeEW, 0, dem.crs(), prj_crs)
            cellsizeNS_prj_crs = distance_projected_pts(xMin, yMin, 0, cellsizeNS, dem.crs(), prj_crs)
        else:
            cellsizeEW_prj_crs = cellsizeEW
            cellsizeNS_prj_crs = cellsizeNS

        return 0.5 * (cellsizeEW_prj_crs + cellsizeNS_prj_crs)

    def get_dem_parameters(self, dem):

        return QGisRasterParameters(*raster_qgis_params(dem))

    def get_selected_dems_params(self, dialog):

        selected_dems = []
        for dem_qgis_ndx in range(dialog.listDEMs_treeWidget.topLevelItemCount()):
            curr_DEM_item = dialog.listDEMs_treeWidget.topLevelItem(dem_qgis_ndx)
            if curr_DEM_item.checkState(0) == 2:
                selected_dems.append(dialog.singleband_raster_layers_in_project[dem_qgis_ndx])

        return selected_dems

    def define_source_DEMs(self):

        self.selected_dems = None
        self.selected_dem_parameters = []

        current_raster_layers = loaded_monoband_raster_layers()
        if len(current_raster_layers) == 0:
            warn(self,
                 self.plugin_name,
                 "No loaded DEM")
            return

        dialog = SourceDEMsDialog(self.plugin_name, current_raster_layers)

        if dialog.exec_():
            selected_dems = self.get_selected_dems_params(dialog)
        else:
            warn(self,
                 self.plugin_name,
                 "No chosen DEM")
            return

        if len(selected_dems) == 0:
            warn(self,
                 self.plugin_name,
                 "No selected DEM")
            return
        else:
            self.selected_dems = selected_dems

        # get geodata

        self.selected_dem_parameters = [self.get_dem_parameters(dem) for dem in selected_dems]

        # get DEMs resolutions in project CRS and choose the min value

        on_the_fly_projection, project_crs = get_on_the_fly_projection(self.canvas)

        dem_resolutions_prj_crs_list = []
        for dem, dem_params in zip(self.selected_dems, self.selected_dem_parameters):
            dem_resolutions_prj_crs_list.append(
                self.get_dem_resolution_in_prj_crs(
                    dem,
                    dem_params,
                    on_the_fly_projection,
                    project_crs))

        max_dem_resolution = max(dem_resolutions_prj_crs_list)
        if max_dem_resolution > 1:
            max_dem_proposed_resolution = round(max_dem_resolution)
        else:
            max_dem_proposed_resolution = max_dem_resolution
        self.profile_densify_distance_lineedit.setText(str(max_dem_proposed_resolution))

    def save_rubberband(self):

        def output_profile_line(output_format, output_filepath, pts2dt, proj_sr):

            points = [[n, pt2dt.x, pt2dt.y] for n, pt2dt in enumerate(pts2dt)]
            if output_format == "csv":
                success, msg = write_generic_csv(output_filepath,
                                                 ['id', 'x', 'y'],
                                                 points)
                if not success:
                    warn(self,
                         self.plugin_name,
                         msg)
            elif output_format == "shapefile - line":
                success, msg = write_rubberband_profile_lnshp(
                    output_filepath,
                    ['id'],
                    points,
                    proj_sr)
                if not success:
                    warn(self,
                         self.plugin_name,
                         msg)
            else:
                error(self,
                      self.plugin_name,
                      "Debug: error in export format")
                return

            if success:
                info(self,
                     self.plugin_name,
                     "Line saved")

        def get_format_type():

            if dialog.outtype_shapefile_line_QRadioButton.isChecked():
                return "shapefile - line"
            elif dialog.outtype_csv_QRadioButton.isChecked():
                return "csv"
            else:
                return ""

        if self.digitized_profile_line2dt is None:
            warn(self,
                 self.plugin_name,
                 "No available line to save [1]")
            return
        elif self.digitized_profile_line2dt.num_pts < 2:
            warn(self,
                 self.plugin_name,
                 "No available line to save [2]")
            return

        dialog = LineDataExportDialog(self.plugin_name)
        if dialog.exec_():
            output_format = get_format_type()
            if output_format == "":
                warn(self,
                     self.plugin_name,
                     "Error in output format")
                return
            output_filepath = dialog.outpath_QLineEdit.text()
            if len(output_filepath) == 0:
                warn(self,
                     self.plugin_name,
                     "Error in output path")
                return
            add_to_project = dialog.load_output_checkBox.isChecked()
        else:
            warn(self,
                 self.plugin_name,
                 "No export defined")
            return

        # get project CRS information
        project_crs_osr = get_prjcrs_as_proj4str(self.canvas)

        output_profile_line(
            output_format,
            output_filepath,
            self.digitized_profile_line2dt.pts,
            project_crs_osr)

        # add theme to QGis project
        if output_format == "shapefile - line" and add_to_project:
            try:
                digitized_line_layer = QgsVectorLayer(output_filepath,
                                                      QFileInfo(output_filepath).baseName(),
                                                      "ogr")
                QgsProject.instance().addMapLayer(digitized_line_layer)
            except:
                QMessageBox.critical(self, "Result", "Unable to load layer in project")
                return

    def calculate_profile_statistics(self):

        correct, err_msg = self.check_pre_statistics()
        if not correct:
            warn(self, self.plugin_name, err_msg)
            return

        for ndx in range(self.input_geoprofiles.geoprofiles_num):
            self.input_geoprofiles.geoprofile(ndx).topo_profiles.statistics_elev = [get_statistics(p) for p in
                                                                                    self.input_geoprofiles.geoprofile(
                                                                                        ndx).topo_profiles.profile_zs]
            self.input_geoprofiles.geoprofile(ndx).topo_profiles.statistics_dirslopes = [get_statistics(p) for p in
                                                                                         self.input_geoprofiles.geoprofile(
                                                                                             ndx).topo_profiles.profile_dirslopes]
            self.input_geoprofiles.geoprofile(ndx).topo_profiles.statistics_slopes = [get_statistics(p) for p in
                                                                                      np.absolute(
                                                                                          self.input_geoprofiles.geoprofile(
                                                                                              ndx).topo_profiles.profile_dirslopes)]

            self.input_geoprofiles.geoprofile(ndx).topo_profiles.profile_length = \
            self.input_geoprofiles.geoprofile(ndx).topo_profiles.profile_s[-1] - \
            self.input_geoprofiles.geoprofile(ndx).topo_profiles.profile_s[0]
            statistics_elev = self.input_geoprofiles.geoprofile(ndx).topo_profiles.statistics_elev
            self.input_geoprofiles.geoprofile(ndx).topo_profiles.natural_elev_range = (
                np.nanmin(np.array([ds_stats["min"] for ds_stats in statistics_elev])),
                np.nanmax(np.array([ds_stats["max"] for ds_stats in statistics_elev])))

            self.input_geoprofiles.geoprofile(ndx).topo_profiles.statistics_calculated = True

        dialog = StatisticsDialog(
            self.plugin_name,
            self.input_geoprofiles
        )

        dialog.exec_()

    def load_line2d_layer(self):

        self.init_line2d_topo_labels()

        current_line_layers = loaded_line_layers()

        if len(current_line_layers) == 0:
            warn(self,
                 self.plugin_name,
                 "No available line layers")
            return

        dialog = SourceLine2DLayerDialog(self.plugin_name,
                                         current_line_layers)

        if dialog.exec_():
            line_layer, multiple_profiles, label_field_ndx, order_field_ndx = line2d_layer_params(dialog)
        else:
            warn(self,
                 self.plugin_name,
                 "No defined line source")
            return

        line_label_fld_ndx = int(label_field_ndx) - 1 if label_field_ndx else None
        line_order_fld_ndx = int(order_field_ndx) - 1 if order_field_ndx else None

        areLinesToReorder = False if line_order_fld_ndx is None else True

        # get profile path from input line layer

        success, result = line_traces_with_order_and_labels(
            line_layer,
            line_label_fld_ndx,
            line_order_fld_ndx
        )

        if not success:
            raise VectorIOException(result)

        profile_orig_lines, label_values, order_values = result

        processed_lines = []
        if multiple_profiles:

            if areLinesToReorder:

                sorted_profiles = sort_by_external_key(
                    profile_orig_lines,
                    order_values
                )

                sorted_labels = list(sort_by_external_key(
                    label_values,
                    order_values
                ))

                sorted_orders = sorted(order_values)

            else:

                sorted_profiles = profile_orig_lines
                sorted_labels = label_values
                sorted_orders = order_values

            for orig_line in sorted_profiles:
                processed_lines.append(merge_line(orig_line))

        else:

            sorted_labels = label_values
            sorted_orders = order_values
            processed_lines.append(merge_lines_with_order(profile_orig_lines, order_values))

        # process input line layer

        on_the_fly_projection, project_crs = get_on_the_fly_projection(self.canvas)
        projected_lines = []
        for processed_line in processed_lines:
            projected_lines.append(
                create_line_in_project_crs(
                    processed_line,
                    line_layer.crs(),
                    on_the_fly_projection,
                    project_crs
                )
            )

        self.profiles_lines = [line.remove_coincident_points() for line in projected_lines]
        self.profiles_labels = sorted_labels
        self.profiles_order = sorted_orders

    def load_points2d_list(self):

        def get_point_list(dialog):

            raw_point_string = dialog.point_list_qtextedit.toPlainText()
            raw_point_list = raw_point_string.split("\n")
            raw_point_list = [clean_string(str(unicode_txt)) for unicode_txt in raw_point_list]
            data_list = [rp for rp in raw_point_list if rp != ""]

            point_list = [to_float(xy_pair.split(",")) for xy_pair in data_list]
            line2d = xytuple_list_to_Line(point_list)

            return line2d

        self.init_line2d_topo_labels()

        dialog = LoadPointListDialog(self.plugin_name)

        if dialog.exec_():
            line2d = get_point_list(dialog)
        else:
            warn(self,
                 self.plugin_name,
                 "No defined line source")
            return
        try:
            npts = line2d.num_pts
            if npts < 2:
                warn(self,
                     self.plugin_name,
                     "Defined line source with less than two points")
                return
        except:
            warn(self,
                 self.plugin_name,
                 "No defined line source")
            return

        self.profiles_lines = [line2d]

    def digitize_line(self):

        def connect_digitize_maptool():
            self.digitize_maptool.moved.connect(self.canvas_refresh_profile_line)
            self.digitize_maptool.leftClicked.connect(self.profile_add_point)
            self.digitize_maptool.rightClicked.connect(self.canvas_end_profile_line)

        self.init_line2d_topo_labels()

        QProfQWidget.map_digitations += 1

        self.clear_rubberband()
        self.profile_canvas_points = []

        if QProfQWidget.map_digitations == 1:
            info(self,
                 self.plugin_name,
                 "Now you can digitize a line on the map.\nLeft click: add point\nRight click: end adding point")

        self.previous_maptool = self.canvas.mapTool()  # Save the standard map tool for restoring it at the end
        self.digitize_maptool = MapDigitizeTool(self.canvas)  # mouse listener
        self.canvas.setMapTool(self.digitize_maptool)
        connect_digitize_maptool()

        self.rubberband = QgsRubberBand(self.canvas)
        self.rubberband.setWidth(2)
        self.rubberband.setColor(QColor(Qt.red))

    def select_input_gpx_file(self):

        gpx_last_used_dir = self.settings.value(self.settings_gpxdir_key,
                                                "")
        file_name, __ = QFileDialog.getOpenFileName(self,
                                                    self.tr("Open GPX file"),
                                                    gpx_last_used_dir,
                                                    "GPX (*.gpx *.GPX)")
        if not file_name:
            return
        else:
            update_directory_key(self.settings,
                                 self.settings_gpxdir_key,
                                 file_name)
            self.gpx_file_lineedit.setText(file_name)

    def get_profile_plot_params(self, dialog):

        profile_params = {}

        # get profile plot parameters

        try:
            profile_params['plot_min_elevation_user'] = float(dialog.qledtPlotMinValue.text())
        except:
            profile_params['plot_min_elevation_user'] = None

        try:
            profile_params['plot_max_elevation_user'] = float(dialog.qledtPlotMaxValue.text())
        except:
            profile_params['plot_max_elevation_user'] = None

        profile_params['set_vertical_exaggeration'] = dialog.qcbxSetVerticalExaggeration.isChecked()
        try:
            profile_params['vertical_exaggeration'] = float(dialog.qledtDemExagerationRatio.text())
            assert profile_params['vertical_exaggeration'] > 0
        except:
            profile_params['vertical_exaggeration'] = 1

        profile_params['filled_height'] = dialog.qcbxPlotFilledHeight.isChecked()
        profile_params['filled_slope'] = dialog.qcbxPlotFilledSlope.isChecked()
        profile_params['plot_height_choice'] = dialog.qcbxPlotProfileHeight.isChecked()
        profile_params['plot_slope_choice'] = dialog.qcbxPlotProfileSlope.isChecked()
        profile_params['plot_slope_absolute'] = dialog.qrbtPlotAbsoluteSlope.isChecked()
        profile_params['plot_slope_directional'] = dialog.qrbtPlotDirectionalSlope.isChecked()
        profile_params['invert_xaxis'] = dialog.qcbxInvertXAxisProfile.isChecked()

        surface_names = self.input_geoprofiles.geoprofile(0).topo_profiles.surface_names

        if hasattr(dialog, 'visible_elevation_layers') and dialog.visible_elevation_layers is not None:
            profile_params['visible_elev_lyrs'] = dialog.visible_elevation_layers
        else:
            profile_params['visible_elev_lyrs'] = surface_names

        if hasattr(dialog, 'elevation_layer_colors') and dialog.elevation_layer_colors is not None:
            profile_params['elev_lyr_colors'] = dialog.elevation_layer_colors
        else:
            profile_params['elev_lyr_colors'] = [QColor('red')] * len(surface_names)

        return profile_params

    def plot_topo_profiles(self):

        if not self.check_pre_profile():
            return

        natural_elev_min_set = []
        natural_elev_max_set = []
        profile_length_set = []
        for geoprofile in self.input_geoprofiles.geoprofiles:
            natural_elev_min, natural_elev_max = geoprofile.topo_profiles.natural_elev_range
            natural_elev_min_set.append(natural_elev_min)
            natural_elev_max_set.append(natural_elev_max)
            profile_length_set.append(geoprofile.topo_profiles.profile_length)

        surface_names = geoprofile.topo_profiles.surface_names
        if self.input_geoprofiles.plot_params is None:
            surface_colors = None
        else:
            surface_colors = self.input_geoprofiles.plot_params.get('elev_lyr_colors')

        dialog = PlotTopoProfileDialog(self.plugin_name,
                                       profile_length_set,
                                       natural_elev_min_set,
                                       natural_elev_max_set,
                                       surface_names,
                                       surface_colors)

        if dialog.exec_():
            self.input_geoprofiles.plot_params = self.get_profile_plot_params(dialog)
        else:
            return

        self.input_geoprofiles.profiles_created = True

        # plot profiles

        plot_addit_params = dict()
        #plot_addit_params["label_projected_lines"] = self.project_line_add_labels.isChecked()
        #plot_addit_params["projected_lines_class_colors"] = self.projected_lines_classification_colors
        plot_addit_params["add_trendplunge_label"] = self.plot_prj_add_trendplunge_label.isChecked()
        plot_addit_params["add_ptid_label"] = self.plot_prj_add_pt_id_label.isChecked()
        plot_addit_params["polygon_class_colors"] = self.intersected_polygon_classification_colors
        plot_addit_params["plane_attitudes_styles"] = self.plane_attitudes_styles

        profile_window = plot_geoprofiles(
            self.input_geoprofiles,
            plot_addit_params
        )
        self.profile_windows.append(profile_window)

    def clear_rubberband(self):

        self.profile_canvas_points = []
        self.digitized_profile_line2dt = None
        try:
            self.rubberband.reset()
        except:
            pass

    def refresh_rubberband(self, xy_list):

        self.rubberband.reset(QgsWkbTypes.LineGeometry)
        for x, y in xy_list:
            self.rubberband.addPoint(QgsPointXY(x, y))

    def canvas_refresh_profile_line(self, position):

        if len(self.profile_canvas_points) == 0:
            return

        x, y = xy_from_canvas(self.canvas, position)
        self.refresh_rubberband(self.profile_canvas_points + [[x, y]])

    def profile_add_point(self, position):

        x, y = xy_from_canvas(self.canvas, position)
        self.profile_canvas_points.append([x, y])

    def canvas_end_profile_line(self):

        def restore_previous_map_tool():

            self.canvas.unsetMapTool(self.digitize_maptool)
            self.canvas.setMapTool(self.previous_maptool)

        self.refresh_rubberband(self.profile_canvas_points)

        self.digitized_profile_line2dt = None
        if len(self.profile_canvas_points) > 1:
            raw_line = Line(
                [Point(x, y) for x, y in self.profile_canvas_points]).remove_coincident_points()
            if raw_line.num_pts > 1:
                self.digitized_profile_line2dt = raw_line

        self.profile_canvas_points = []

        restore_previous_map_tool()

    def check_pre_statistics(self):

        if self.input_geoprofiles is None:
            return False, "Source profile not yet defined"

        if self.input_geoprofiles.geoprofiles_num == 0:
            return False, "No defined profile"

        return True, ""

    def check_pre_profile(self) -> Tuple[bool, str]:

        correct, err_msg = self.check_pre_statistics()
        if not correct:
            return False, err_msg

        for geoprofile in self.input_geoprofiles.geoprofiles:
            if not geoprofile.topo_profiles.statistics_calculated:
                return False, "Profile statistics not yet calculated"

        return True, ""

    def reset_lineaments_intersections(self):

        geoprofile = self.input_geoprofiles.geoprofile(0)
        if geoprofile is not None:
            geoprofile.intersected_lineaments = []

    def reset_polygon_intersections(self):

        try:
            geoprofile = self.input_geoprofiles.geoprofile(0)
            if geoprofile is not None:
                geoprofile.intersected_outcrops = []
        except:
            pass

    def check_intersection_polygon_inputs(self) -> Tuple[bool, str]:

        correct, err_msg = self.check_for_struc_process()
        if not correct:
            return False, err_msg

        # polygon layer with parameter fields
        intersection_polygon_qgis_ndx = self.inters_input_polygon_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box
        if intersection_polygon_qgis_ndx < 0:
            return False, "No defined polygon layer"

        return True, ""

    def check_intersection_line_inputs(self) -> Tuple[bool, str]:

        correct, err_msg = self.check_for_struc_process()
        if not correct:
            return False, err_msg

        # line structural layer with parameter fields
        intersection_line_qgis_ndx = self.inters_input_line_comboBox.currentIndex() - 1  # minus 1 in order to account for initial text in combo box
        if intersection_line_qgis_ndx < 0:
            return False, "No defined geological line layer"

        return True, ""

    def do_polygon_intersection(self):

        # check input values

        correct, err_msg = self.check_intersection_polygon_inputs()
        if not correct:
            warn(
                self,
                self.plugin_name,
                err_msg
            )
            return

        # get dem parameters
        geoprofile = self.input_geoprofiles.geoprofile(0)
        demLayer = geoprofile.topo_profiles.dem_params[0].layer
        demParams = geoprofile.topo_profiles.dem_params[0].params

        # profile line2d, in project CRS and densified
        profile_line2d_prjcrs_densif = geoprofile.original_line.densify_2d_line(geoprofile.sample_distance)

        # polygon layer
        intersection_polygon_qgis_ndx = self.inters_input_polygon_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box
        inters_polygon_classifaction_field_ndx = self.inters_polygon_classifaction_field_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box
        polygon_layer = self.current_polygon_layers[intersection_polygon_qgis_ndx]
        polygon_layer_crs = polygon_layer.crs()

        on_the_fly_projection, project_crs = get_on_the_fly_projection(self.canvas)

        if on_the_fly_projection and polygon_layer_crs != project_crs:
            profile_line2d_polycrs_densif = profile_line2d_prjcrs_densif.crs_project(project_crs,
                                                                                     polygon_layer_crs)
        else:
            profile_line2d_polycrs_densif = profile_line2d_prjcrs_densif

        profile_qgsgeometry = QgsGeometry.fromPolyline(
            [QgsPoint(pt2d.x, pt2d.y) for pt2d in profile_line2d_polycrs_densif.pts])

        success, return_data = profile_polygon_intersection(profile_qgsgeometry,
                                                            polygon_layer,
                                                            inters_polygon_classifaction_field_ndx)

        if not success:
            error(self,
                  self.plugin_name,
                  return_data)
            return

        lIntersectPolylinePolygonCrs = return_data

        if len(lIntersectPolylinePolygonCrs) == 0:
            warn(self,
                 self.plugin_name,
                 "No intersection found")
            return

        # transform polyline intersections into prj crs line2d & classification list
        lIntersLine2dPrjCrs = []
        for intersection_polyline_polygon_crs in lIntersectPolylinePolygonCrs:
            rec_classification, xy_tuple_list = intersection_polyline_polygon_crs
            intersection_polygon_crs_line2d = xytuple_list_to_Line(xy_tuple_list)
            if on_the_fly_projection and polygon_layer_crs != project_crs:
                intersection_prj_crs_line2d = intersection_polygon_crs_line2d.crs_project(polygon_layer_crs,
                                                                                          project_crs)
            else:
                intersection_prj_crs_line2d = intersection_polygon_crs_line2d
            lIntersLine2dPrjCrs.append([rec_classification, intersection_prj_crs_line2d])

        # create Point lists from intersection with source DEM

        sect_pt_1, sect_pt_2 = geoprofile.original_line.pts
        formation_list = []
        intersection_line3d_list = []
        intersection_polygon_s_list2 = []
        for polygon_classification, line2d in lIntersLine2dPrjCrs:

            lptIntersPts3d = intersect_with_dem(demLayer, demParams, on_the_fly_projection, project_crs, line2d.pts)
            lineIntersectionLine3d = Line(lptIntersPts3d)

            s0_list = lineIntersectionLine3d.incremental_length_2d()
            s_start = sect_pt_1.dist_2d(lineIntersectionLine3d.pts[0])
            s_list = [s + s_start for s in s0_list]

            formation_list.append(polygon_classification)
            intersection_line3d_list.append(lineIntersectionLine3d)
            intersection_polygon_s_list2.append(s_list)

        if len(intersection_polygon_s_list2) == 0:
            warn(self,
                 self.plugin_name,
                 "No reprojected intersection")
            return

        geoprofile.add_intersections_lines(formation_list, intersection_line3d_list, intersection_polygon_s_list2)

        # plot profiles
        plot_addit_params = dict()
        #plot_addit_params["label_projected_lines"] = self.project_line_add_labels.isChecked()
        #plot_addit_params["projected_lines_class_colors"] = self.projected_lines_classification_colors
        plot_addit_params["add_trendplunge_label"] = self.plot_prj_add_trendplunge_label.isChecked()
        plot_addit_params["add_ptid_label"] = self.plot_prj_add_pt_id_label.isChecked()
        plot_addit_params["polygon_class_colors"] = self.intersected_polygon_classification_colors
        plot_addit_params["plane_attitudes_styles"] = self.plane_attitudes_styles

        profile_window = plot_geoprofiles(
            self.input_geoprofiles,
            plot_addit_params
        )
        self.profile_windows.append(profile_window)

    def classification_colors(self, dialog):

        polygon_classification_colors_dict = dict()
        for classification_ndx in range(dialog.classifications_treeWidget.topLevelItemCount()):
            class_itemwidget = dialog.classifications_treeWidget.topLevelItem(classification_ndx)
            classification = str(class_itemwidget.text(0))
            # get color
            color = qcolor2rgbmpl(dialog.classifications_treeWidget.itemWidget(class_itemwidget, 1).color())
            polygon_classification_colors_dict[classification] = color

        return polygon_classification_colors_dict

    def do_line_intersection(self):

        # check input values

        correct, err_msg = self.check_intersection_line_inputs()
        if not correct:
            warn(
                self,
                self.plugin_name,
                err_msg
            )
            return

        # get color for projected points
        color = qcolor2rgbmpl(self.inters_line_point_color_QgsColorButton.color())

        # get dem parameters
        geoprofile = self.input_geoprofiles.geoprofile(0)
        demLayer = geoprofile.topo_profiles.dem_params[0].layer
        demParams = geoprofile.topo_profiles.dem_params[0].params

        # get line structural layer
        intersection_line_qgis_ndx = self.inters_input_line_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box

        # get id field
        intersection_line_id_field_ndx = self.inters_input_id_fld_line_comboBox.currentIndex() - 1  # minus 1 in order to account for initial text in combo box

        # define structural layer
        structural_line_layer = self.current_line_layers[intersection_line_qgis_ndx]

        on_the_fly_projection, project_crs = get_on_the_fly_projection(self.canvas)

        # read structural line values
        if intersection_line_id_field_ndx == -1:
            id_list = None
        else:
            id_list = field_values(structural_line_layer, intersection_line_id_field_ndx)

        line_proj_crs_MultiLine2D_list = extract_multiline2d_list(structural_line_layer, on_the_fly_projection,
                                                                       project_crs)

        # calculated Point intersection list
        intersection_point_id_list = calculate_profile_lines_intersection(line_proj_crs_MultiLine2D_list,
                                                                          id_list,
                                                                          geoprofile.original_line)

        # sort intersection points by spat_distance from profile start point
        lstDistancesFromProfileStart = intersection_distances_by_profile_start_list(geoprofile.original_line,
                                                                                         intersection_point_id_list)

        # create CartesianPoint from intersection with source DEM
        lstIntersectionPoints = [pt2d for pt2d, _ in intersection_point_id_list]
        lstIntersectionIds = [pt_id for _, pt_id in intersection_point_id_list]
        lstIntersectionPoints3d = intersect_with_dem(demLayer, demParams, on_the_fly_projection, project_crs,
                                                            lstIntersectionPoints)
        lstIntersectionColors = [color] * len(lstIntersectionPoints)

        geoprofile.add_intersections_pts(
            list(zip(lstDistancesFromProfileStart, lstIntersectionPoints3d, lstIntersectionIds, lstIntersectionColors)))

        # plot profiles

        plot_addit_params = dict()
        plot_addit_params["add_trendplunge_label"] = self.plot_prj_add_trendplunge_label.isChecked()
        plot_addit_params["add_ptid_label"] = self.plot_prj_add_pt_id_label.isChecked()
        plot_addit_params["polygon_class_colors"] = self.intersected_polygon_classification_colors
        plot_addit_params["plane_attitudes_styles"] = self.plane_attitudes_styles

        profile_window = plot_geoprofiles(
            self.input_geoprofiles,
            plot_addit_params
        )
        self.profile_windows.append(profile_window)

    def save_projected_line_styles(self):

        try:

            file_pth = new_file_path(
                self,
                "Save graphical parameters as file",
                "*.pkl",
                "pickle (*.pkl *.PKL)"
            )

            if not file_pth:
                return

            with open(file_pth, 'wb') as handle:
                pickle.dump(
                    self.projected_lines_classification_colors,
                    handle,
                    protocol=pickle.HIGHEST_PROTOCOL
                )

            info(
                self,
                self.plugin_name,
                f"Graphical parameters saved in {file_pth}"
            )

        except Exception as e:

            warn(
                self,
                self.plugin_name,
                f"Error: {e}"
            )

    def load_projected_line_styles(self):

        try:

            file_pth = old_file_path(
                self,
                "Load graphical parameters from file",
                "*.pkl",
                "pickle (*.pkl *.PKL)"
            )

            if not file_pth:
                return

            with open(file_pth, 'rb') as handle:
                self.projected_lines_classification_colors = pickle.load(handle)

            info(
                self,
                self.plugin_name,
                f"Graphical parameters loaded from {file_pth}"
            )

        except Exception as e:

            warn(
                self,
                self.plugin_name,
                f"Error: {e}"
            )

    def struct_point_refresh_lyr_combobox(self):

        self.pointLayers = loaded_point_layers()

        update_ComboBox(self.prj_struct_point_comboBox,
                        self.choose_message,
                        [layer.name() for layer in self.pointLayers])

    def struct_polygon_refresh_lyr_combobox(self):

        self.current_polygon_layers = loaded_polygon_layers()
        update_ComboBox(self.inters_input_polygon_comboBox,
                        self.choose_message,
                        [layer.name() for layer in self.current_polygon_layers])

    def struct_line_refresh_lyr_combobox(self):

        self.current_line_layers = loaded_line_layers()
        update_ComboBox(self.prj_input_line_comboBox,
                        self.choose_message,
                        [layer.name() for layer in self.current_line_layers])
        update_ComboBox(self.inters_input_line_comboBox,
                        self.choose_message,
                        [layer.name() for layer in self.current_line_layers])

    def update_point_layers_boxes(self):

        if len(self.pointLayers) == 0:
            return

        shape_qgis_ndx = self.prj_struct_point_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box
        if shape_qgis_ndx < 0:
            return

        layer = self.pointLayers[shape_qgis_ndx]
        fields = layer.dataProvider().fields()
        field_names = [field.name() for field in fields.toList()]
        #assert print(f"Layer: {layer}, Fields: {fields}, Field Names: {field_names}")
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
            shape_qgis_ndx = self.prj_input_line_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box
            field_combobox_list = self.flds_prj_line_comboBoxes
            layer_list = self.current_line_layers
        elif self.sender() is self.inters_input_line_comboBox:
            shape_qgis_ndx = self.inters_input_line_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box
            field_combobox_list = self.flds_inters_line_comboBoxes
            layer_list = self.current_line_layers
        elif self.sender() is self.inters_input_polygon_comboBox:
            shape_qgis_ndx = self.inters_input_polygon_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box
            field_combobox_list = self.flds_inters_polygon_comboBoxes
            layer_list = self.current_polygon_layers

        update_field_combo_boxes()

    def get_current_combobox_values(self, combobox_list):

        return [combobox.currentText() for combobox in combobox_list]

    def calculate_section_data_dictionary(self) -> dict:

        geoprofile = self.input_geoprofiles.geoprofile(0)
        sect_pt_1, sect_pt_2 = geoprofile.original_line.pts

        section_init_pt = Point(sect_pt_1.x, sect_pt_1.y, 0.0)
        section_final_pt = Point(sect_pt_2.x, sect_pt_2.y, 0.0)

        section_final_pt_up = Point(section_final_pt.x, section_final_pt.y,
                                       1000.0)  # arbitrary point on the same vertical as sect_pt_2
        section_cartes_plane = Plane.from_points(section_init_pt, section_final_pt, section_final_pt_up)
        section_vector = Segment(section_init_pt, section_final_pt).vector()

        return {
            'init_pt': section_init_pt,
            'cartes_plane': section_cartes_plane,
            'vector': section_vector
        }

    def struct_prjct_get_mapping_method(self):

        if self.nearest_point_proj_choice.isChecked():
            return {'method': 'nearest'}

        if self.axis_common_point_proj_choice.isChecked():
            return {'method': 'common axis',
                    'trend': float(self.common_axis_point_trend_SpinBox.value()),
                    'plunge': float(self.common_axis_point_plunge_SpinBox.value())}

        if self.axis_individual_point_proj_choice.isChecked():
            return {'method': 'individual axes',
                    'trend field': str(self.proj_point_indivax_trend_fld_comboBox.currentText()),
                    'plunge field': str(self.proj_point_indivax_plunge_fld_comboBox.currentText())}

    def check_post_profile(self) -> Tuple[bool, str]:

        correct, err_msg = self.check_pre_profile()
        if not correct:
            return False, err_msg

        if not self.input_geoprofiles.profiles_created:
            return False, "Topographic profile not yet created"

        return True, ""

    def check_for_struc_process(self,
                                single_segment_constrain=True
                                ) -> Tuple[bool, str]:

        correct, err_msg = self.check_post_profile()
        if not correct:
            return False, err_msg

        # check that just one profile is set

        if self.input_geoprofiles.geoprofiles_num != 1:
            return False, "Profile lines must be one and just one"

        geoprofile = self.input_geoprofiles.geoprofile(0)

        # check that section is made up of only two points

        if single_segment_constrain:
            if geoprofile.original_line.num_pts != 2:
                return False, "For projection, profile must be made up by just two points"

        # check that source dem is just one

        if len(geoprofile.topo_profiles.profile_s3ds) != 1:
            return False, "One (and only) topographic surface has to be used in the profile section"

        return True, ""

    def check_struct_point_proj_parameters(self) -> Tuple[bool, str]:

        correct, err_msg = self.check_for_struc_process()
        if not correct:
            return False, err_msg

        # get point structural layer with parameter fields
        prj_struct_point_qgis_ndx = self.prj_struct_point_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box
        if prj_struct_point_qgis_ndx < 0:
            return False, "No defined point layer for structural data"

        return True, ""


    #structural_layer = structural_layer.selectedFeatures()
    def project_attitudes(self):

        correct, err_msg = self.check_struct_point_proj_parameters()
        if not correct:
            warn(
                self,
                self.plugin_name,
                err_msg
            )
            return

        # get graphic style for projected attitudes

        marker_symbol = marker_mapping[self.proj_point_marker_symbol_QComboBox.currentText()]
        marker_size = self.proj_point_marker_size_QSpinBox.value()
        color = qcolor2rgbmpl(self.proj_point_color_QgsColorButton.color())
        line_width = self.proj_point_line_width_QSpinBox.value()
        transparency = self.proj_point_opacity_QSpinBox.value() / 100.0

        # define structural layer 
        prj_struct_point_qgis_ndx = self.prj_struct_point_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box
        structural_layer = self.pointLayers[prj_struct_point_qgis_ndx]


        structural_layer_crs = structural_layer.crs()
        structural_field_list = self.get_current_combobox_values(self.flds_prj_point_comboBoxes)
        isRHRStrike = self.qrbtPlotPrjUseRhrStrike.isChecked()

        # retrieve selected structural points with their attributes
        # original version
        # THIS ONE CHECKS IF SELECTED ATTRIBUTES >0
        structural_pts_attrs = pt_geoms_attrs(structural_layer, structural_field_list)



        # list of structural points with original crs
        struct_pts_in_orig_crs = [Point(float(rec[0]), float(rec[1])) for rec in structural_pts_attrs]

        # IDs of structural points
        struct_pts_ids = [rec[2] for rec in structural_pts_attrs]

        # - geological planes (3D), as geological planes
        try:
            structural_planes = [GPlane(float(rec[3]), float(rec[4]), isRHRStrike) for rec in structural_pts_attrs]
        except Exception as e:
            warn(self,
                 self.plugin_name,
                 f"Check defined fields for possible errors exception: {e}")
            return

        geoprofile = self.input_geoprofiles.geoprofile(0)
        struct_pts_3d = calculate_projected_3d_pts(self.canvas,
                                                   struct_pts_in_orig_crs,
                                                   structural_layer_crs,
                                                   geoprofile.topo_profiles.dem_params[0])

        # - zip together the point value data sets                     
        assert len(struct_pts_3d) == len(structural_planes)
        structural_data = list(zip(struct_pts_3d, structural_planes, struct_pts_ids))

        ### map points onto section ###

        # calculation of Cartesian plane expressing section plane        
        self.section_data = self.calculate_section_data_dictionary()

        # calculation of projected structural points

        # get chosen mapping method
        mapping_method = self.struct_prjct_get_mapping_method()
        if mapping_method['method'] == 'individual axes':
            trend_field_name, plunge_field_name = mapping_method['trend field'], mapping_method['plunge field']
            # retrieve structural points mapping axes        
            mapping_method['individual_axes_values'] = vect_attrs(structural_layer,
                                                                  [trend_field_name, plunge_field_name])

        geoprofile.add_plane_attitudes(map_struct_pts_on_section(structural_data, self.section_data, mapping_method))
        self.plane_attitudes_styles.append((marker_symbol, marker_size, color, line_width, transparency))

        # plot profiles

        plot_addit_params = dict()
        #plot_addit_params["label_projected_lines"] = self.project_line_add_labels.isChecked()
        #plot_addit_params["projected_lines_class_colors"] = self.projected_lines_classification_colors
        plot_addit_params["add_trendplunge_label"] = self.plot_prj_add_trendplunge_label.isChecked()
        plot_addit_params["add_ptid_label"] = self.plot_prj_add_pt_id_label.isChecked()
        plot_addit_params["polygon_class_colors"] = self.intersected_polygon_classification_colors
        plot_addit_params["plane_attitudes_styles"] = self.plane_attitudes_styles

        profile_window = plot_geoprofiles(
            self.input_geoprofiles,
            plot_addit_params
        )
        self.profile_windows.append(profile_window)

    def reset_struct_point_projection(self):

        try:
            geoprofile = self.input_geoprofiles.geoprofile(0)
            geoprofile.projected_attitudes = []
            self.plane_attitudes_styles = []
        except:
            pass

    def check_inputs_for_structural_lines_projection(self
                                                     ) -> Tuple[bool, str]:

        correct, err_msg = self.check_for_struc_process()
        if not correct:
            return False, err_msg

        # line layer with parameter fields

        if self.prj_input_line_comboBox.currentIndex() < 1:
            return False, "No defined structural line layer"

        if self.id_fld_line_prj_comboBox.currentIndex() < 1:
            return False, "No defined structural line id field"

        if self.project_line_2d_choice.isChecked():
            try:
                densify_distance = float(self.project_line_densify_distance_lineedit.text())
            except:
                return False, "No valid numeric value for densify line distance"
            else:
                if densify_distance <= 0.0:
                    return False, "Densify line distance must be larger than zero"

        return True, ""

    def define_line_projection_style(self):

        try:

            if self.unique_color_choice_radiobutton.isChecked():

                features_ids = set(["unique color"])

            else:

                # get structural layer and id field indices

                prj_struct_line_qgis_ndx = self.prj_input_line_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box
                prj_struct_line_id_field_ndx = self.id_fld_line_prj_comboBox.currentIndex() - 1  # minus 1 to account for initial text in combo box

                # define structural layer

                structural_line_layer = self.current_line_layers[prj_struct_line_qgis_ndx]

                values = extract_values_from_layer(
                    layer=structural_line_layer,
                    field_ndx=prj_struct_line_id_field_ndx,

                )

                if not isinstance(values, List):

                    if isinstance(values, str):
                        err_msg = "Error in style definition. Is input defined?"
                    else:
                        err_msg = "Error while getting layer id values"

                    warn(
                        self,
                        self.plugin_name,
                        err_msg
                    )
                    return

                features_ids = set(values)

            # define classification colors

            dialog = ClassificationColorsDialog(
                self.plugin_name,
                features_ids,
                self.projected_lines_classification_colors,
            )

            if dialog.exec_():
                features_classification_colors_dict = self.classification_colors(dialog)
            else:
                warn(self,
                     self.plugin_name,
                     "No color chosen")
                return

            if len(features_classification_colors_dict) == 0:

                warn(self,
                     self.plugin_name,
                     "No defined colors")
                return

            else:

                self.projected_lines_classification_colors = features_classification_colors_dict

        except Exception as e:

            return f"Error with line style definition: {e}"

    def plot_projected_lines(self):

        # check input values

        correct, err_msg = self.check_inputs_for_structural_lines_projection()

        if not correct:
            warn(
                self,
                self.plugin_name,
                err_msg
            )
            return

        if not hasattr(self, 'projected_lines_classification_colors'):
            warn(
                self,
                self.plugin_name,
                "Line color styles have to be defined first"
            )

        # get geoprofile

        geoprofile = self.input_geoprofiles.geoprofile(0)

        # get structural layer and id field indices
        # note: minus 1 for both indices are to account for initial text in combo box
        prj_struct_line_qgis_ndx = self.prj_input_line_comboBox.currentIndex() - 1
        prj_struct_line_id_field_ndx = self.id_fld_line_prj_comboBox.currentIndex() - 1

        # define structural layer

        structural_line_layer = self.current_line_layers[prj_struct_line_qgis_ndx]

        on_the_fly_projection, project_crs = get_on_the_fly_projection(self.canvas)

        # read structural line values

        if self.project_line_2d_choice.isChecked():  # 2D

            ids = field_values(
                structural_line_layer,
                prj_struct_line_id_field_ndx
            )

            densify_proj_crs_distance = float(self.project_line_densify_distance_lineedit.text())

            dem_layer = geoprofile.topo_profiles.dem_params[0].layer
            dem_parameters = geoprofile.topo_profiles.dem_params[0].params

            multiline_3d_proj_crs_list = extract_2d_lines_laying_on_dem(
                structural_line_layer,
                densify_proj_crs_distance,
                on_the_fly_projection,
                project_crs,
                dem_layer,
                dem_parameters,
            )

        else:   # 3D

            multilines_3d = extract_from_line3d(
                structural_line_layer,
                [prj_struct_line_id_field_ndx]
            )

            if isinstance(multilines_3d, str):
                error(
                    self,
                    self.plugin_name,
                    multilines_3d
                )
                return

            # multilines_3d is List[Tuple[List[Any], List[Union[MultiLine, Line]]]]

            # now parse the result to decompose it into a record id list and a MultiLine/Line list

            ids = []
            geometries = []

            for (rec_id, ), geometry in multilines_3d:

                ids.append(rec_id)
                geometries.append(geometry)

            # force the geometries to be all multiline, for parallelism with the already fully implemented
            # (even if sub-optimal) 2D case

            if structural_line_layer.crs() != project_crs:

                multiline_3d_proj_crs_list = [mline.crs_project(structural_line_layer.crs(), project_crs) for
                                                  mline in geometries]

            else:

                multiline_3d_proj_crs_list = geometries

        # Projection parameters part

        # create projection vector

        trend = float(self.common_axis_line_trend_SpinBox.value())
        plunge = float(self.common_axis_line_plunge_SpinBox.value())
        axis_versor = GAxis(trend, plunge).as_gvect().versor()
        l, m, n = axis_versor.x, axis_versor.y, axis_versor.z

        # calculation of Cartesian plane expressing section plane

        self.section_data = self.calculate_section_data_dictionary()

        # project the multiline points onto the section

        points3d_projected_onto_section = [] # note: result may contain None instances

        for multiline_3d in multiline_3d_proj_crs_list:
            for line_3d in multiline_3d.lines:
                for pt_3d in line_3d.pts:
                    srcPt = pt_3d
                    param_line = ParamLine3D(srcPt, l, m, n)
                    points3d_projected_onto_section.append(
                        param_line.intersect_cartes_plane(
                            self.section_data['cartes_plane']
                        )
                    )

        # create again the multiline 3D list structure of points onto the section
        # using the 3D points with the project CRS

        ndx = -1
        multiline_3d_proj_crs_section_list = []
        for multiline_3d in multiline_3d_proj_crs_list:
            multiline_3d_list = []
            for line_3d in multiline_3d.lines:
                line_3d_pts_list = []
                for _ in line_3d.pts:
                    ndx += 1
                    line_3d_pts_list.append(points3d_projected_onto_section[ndx])
                multiline_3d_list.append(Line(line_3d_pts_list))
            multiline_3d_proj_crs_section_list.append(MultiLine(multiline_3d_list))

        # parse the multiline 3D list into a structure that can be used for profile plotting

        section_start_point, section_vector = self.section_data['init_pt'], self.section_data['vector']

        multilines2d = []
        for multiline_3d in multiline_3d_proj_crs_section_list:
            multiline_2d_list = []
            for line_3d in multiline_3d.lines:
                line_2d_pts_list = []
                for pt_3d in line_3d.pts:
                    s = calculate_distance_with_sign(pt_3d, section_start_point, section_vector)
                    z = pt_3d.z
                    line_2d_pts_list.append(Point(s, z))
                multiline_2d_list.append(Line(line_2d_pts_list))
            multilines2d.append(MultiLine(multiline_2d_list))

        geoprofile.add_curves(
            multilines2d,
            ids,
            self.classified_colors_choice_radiobutton.isChecked(),
            self.projected_lines_classification_colors,
            self.project_line_add_labels.isChecked()
        )

        # plot profiles

        plot_addit_params = dict()
        #plot_addit_params["label_projected_lines"] = self.project_line_add_labels.isChecked()
        #plot_addit_params["categorize_projected_lines"] = self.classified_colors_choice_radiobutton.isChecked()
        plot_addit_params["add_trendplunge_label"] = self.plot_prj_add_trendplunge_label.isChecked()
        plot_addit_params["add_ptid_label"] = self.plot_prj_add_pt_id_label.isChecked()
        plot_addit_params["polygon_class_colors"] = self.intersected_polygon_classification_colors
        plot_addit_params["plane_attitudes_styles"] = self.plane_attitudes_styles

        profile_window = plot_geoprofiles(
            self.input_geoprofiles,
            plot_addit_params
        )
        self.profile_windows.append(profile_window)

    def reset_structural_lines_projection(self):

        try:
            geoprofile = self.input_geoprofiles.geoprofile(0)
            geoprofile.projected_lines = []
        except:
            pass

    def do_export_project_geol_attitudes(self):

        def get_format_type():

            if dialog.outtype_shapefile_point_QRadioButton.isChecked():
                return "shapefile - point"
            elif dialog.outtype_csv_QRadioButton.isChecked():
                return "csv"
            else:
                return ""

        try:
            geoprofile = self.input_geoprofiles.geoprofile(0)
            num_plane_attitudes_sets = len(geoprofile.projected_attitudes)
        except:
            warn(self,
                 self.plugin_name,
                 "No available geological attitudes")
            return
        else:
            if num_plane_attitudes_sets == 0:
                warn(self,
                     self.plugin_name,
                     "No available geological attitudes")
                return

        dialog = PointDataExportDialog(self.plugin_name)

        if dialog.exec_():

            output_format = get_format_type()
            if output_format == "":
                warn(self,
                     self.plugin_name,
                     "Error in output format")
                return
            output_filepath = dialog.outpath_QLineEdit.text()
            if len(output_filepath) == 0:
                warn(self,
                     self.plugin_name,
                     "Error in output path")
                return
            add_to_project = dialog.load_output_checkBox.isChecked()
        else:
            warn(self,
                 self.plugin_name,
                 "No export defined")
            return

        # get project CRS information
        project_crs_osr = get_prjcrs_as_proj4str(self.canvas)

        self.output_geological_attitudes(output_format, output_filepath, project_crs_osr)

        # add theme to QGis project
        if 'shapefile' in output_format and add_to_project:
            try:
                layer = QgsVectorLayer(output_filepath,
                                       QFileInfo(output_filepath).baseName(),
                                       "ogr")
                QgsProject.instance().addMapLayer(layer)
            except:
                QMessageBox.critical(self, "Result", "Unable to load layer in project")
                return

    def export_parse_geologicalattitudes_results(self, plane_attitudes_datasets):

        result_data = []

        for dataset in plane_attitudes_datasets:

            for plane_attitude_rec in dataset:
                pt_id = plane_attitude_rec.id
                or_pt_x = plane_attitude_rec.src_pt_3d.x
                or_pt_y = plane_attitude_rec.src_pt_3d.y
                or_pt_z = plane_attitude_rec.src_pt_3d.z
                pr_pt_x = plane_attitude_rec.pt_3d.x
                pr_pt_y = plane_attitude_rec.pt_3d.y
                pr_pt_z = plane_attitude_rec.pt_3d.z
                s = plane_attitude_rec.sign_hor_dist
                or_dipdir = plane_attitude_rec.src_geol_plane.dd
                or_dipangle = plane_attitude_rec.src_geol_plane.da
                tr_dipangle = degrees(plane_attitude_rec.slope_rad)
                tr_dipdir = plane_attitude_rec.dwnwrd_sense

                record = [pt_id, or_pt_x, or_pt_y, or_pt_z, pr_pt_x, pr_pt_y, pr_pt_z, s, or_dipdir, or_dipangle,
                          tr_dipangle, tr_dipdir]

                result_data.append(record)

        return result_data

    def output_geological_attitudes(self, output_format, output_filepath, project_crs_osr):

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

        geoprofile = self.input_geoprofiles.geoprofile(0)
        parsed_geologicalattitudes_results = self.export_parse_geologicalattitudes_results(
            geoprofile.projected_attitudes)

        # output for csv file
        if output_format == "csv":
            success, msg = write_generic_csv(output_filepath, header_list, parsed_geologicalattitudes_results)
            if not success:
                warn(self,
                     self.plugin_name,
                     msg)
        elif output_format == "shapefile - point":
            success, msg = write_geological_attitudes_ptshp(output_filepath, parsed_geologicalattitudes_results, project_crs_osr)
            if not success:
                warn(self,
                     self.plugin_name,
                     msg)
        else:
            error(self,
                  self.plugin_name,
                  "Debug: error in export format")
            return

        if success:
            info(self,
                 self.plugin_name,
                 "Projected attitudes saved")

    def do_export_project_geol_traces(self):

        try:
            geoprofile = self.input_geoprofiles.geoprofile(0)
            num_proj_lines_sets = len(geoprofile.projected_lines)
        except:
            warn(self,
                 self.plugin_name,
                 "No available geological traces")
            return
        else:
            if num_proj_lines_sets == 0:
                warn(self,
                     self.plugin_name,
                     "No available geological traces to save")
                return

        fileName, __ = QFileDialog.getSaveFileName(self,
                                               self.tr("Save results"),
                                               "*.csv",
                                               self.tr("csv (*.csv)"))

        if fileName is None or fileName == '':
            warn(self,
                 self.plugin_name,
                 "No output file has been defined")
            return

        parsed_curves_for_export = self.export_parse_projected_geological_traces()
        header_list = ['id', 's', 'z']

        write_generic_csv(fileName, header_list, parsed_curves_for_export)

        info(self,
             self.plugin_name,
             "Projected lines saved")

    def do_export_line_intersections(self):

        def get_format_type():

            if dialog.outtype_shapefile_point_QRadioButton.isChecked():
                return "shapefile - point"
            elif dialog.outtype_csv_QRadioButton.isChecked():
                return "csv"
            else:
                return ""

        try:
            geoprofile = self.input_geoprofiles.geoprofile(0)
            num_intersection_pts = len(geoprofile.intersected_lineaments)
        except:
            warn(self,
                 self.plugin_name,
                 "No available profile-line intersections")
            return
        else:
            if num_intersection_pts == 0:
                warn(self,
                     self.plugin_name,
                     "No available profile-line intersections")
                return

        dialog = PointDataExportDialog(self.plugin_name)

        if dialog.exec_():
            output_format = get_format_type()
            if output_format == "":
                warn(self,
                     self.plugin_name,
                     "Error in output format")
                return
            output_filepath = dialog.outpath_QLineEdit.text()
            if len(output_filepath) == 0:
                warn(self,
                     self.plugin_name,
                     "Error in output path")
                return
            add_to_project = dialog.load_output_checkBox.isChecked()
        else:
            warn(self,
                     self.plugin_name,
                     "No export defined")
            return

        # get project CRS information
        project_crs_osr = get_prjcrs_as_proj4str(self.canvas)

        self.output_profile_lines_intersections(output_format, output_filepath, project_crs_osr)

        # add theme to QGis project
        if 'shapefile' in output_format and add_to_project:
            try:
                layer = QgsVectorLayer(output_filepath,
                                       QFileInfo(output_filepath).baseName(),
                                       "ogr")
                QgsProject.instance().addMapLayer(layer)
            except:
                QMessageBox.critical(self, "Result", "Unable to load layer in project")
                return

    def output_profile_lines_intersections(self, output_format, output_filepath, project_crs_osr):

        # definition of field names
        header_list = ['id',
                       's',
                       'x',
                       'y',
                       'z']

        geoprofile = self.input_geoprofiles.geoprofile(0)
        parsed_profilelineintersections = self.export_parse_lineintersections(geoprofile.intersected_lineaments)

        # output for csv file
        if output_format == "csv":
            success, msg = write_generic_csv(output_filepath, header_list, parsed_profilelineintersections)
            if not success:
                warn(self,
                     self.plugin_name,
                     msg)
        elif output_format == "shapefile - point":
            success, msg = write_intersection_line_ptshp(output_filepath, header_list, parsed_profilelineintersections, project_crs_osr)
            if not success:
                warn(self,
                     self.plugin_name,
                     msg)
        else:
            error(self,
                  self.plugin_name,
                  "Debug: error in export format")
            return

        if success:
            info(self,
                 self.plugin_name,
                 "Line intersections saved")

    def export_parse_projected_geological_traces(self):

        data_list = []
        geoprofile = self.input_geoprofiles.geoprofile(0)
        for projected_lines in geoprofile.projected_lines:
            for curve, rec_id in zip(projected_lines.multilines2d, projected_lines.ids):
                for line in curve.projected_lines:
                    for pt in line.pts:
                        data_list.append([rec_id, pt.x, pt.y])
        return data_list

    def export_parse_lineintersections(self, profile_intersection_pts):

        result_data = []

        for distances_from_profile_start, intersection_point3d, intersection_id, _ in profile_intersection_pts:
            result_data.append(
                [intersection_id, distances_from_profile_start, intersection_point3d.x, intersection_point3d.y,
                 intersection_point3d.z])

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
            geoprofile = self.input_geoprofiles.geoprofile(0)
            num_intersection_lines = len(geoprofile.intersected_outcrops)
        except:
            warn(self,
                     self.plugin_name,
                     "No available profile-polygon intersections")
            return
        else:
            if num_intersection_lines == 0:
                warn(self,
                     self.plugin_name,
                     "No available profile-polygon intersections")
                return

        dialog = LineDataExportDialog(self.plugin_name)
        if dialog.exec_():
            output_format = get_format_type()
            if output_format == "":
                warn(self,
                     self.plugin_name,
                     "Error in output format")
                return
            output_filepath = dialog.outpath_QLineEdit.text()
            if len(output_filepath) == 0:
                warn(self,
                     self.plugin_name,
                     "Error in output path")
                return
            add_to_project = dialog.load_output_checkBox.isChecked()
        else:
            warn(self,
                     self.plugin_name,
                     "No export defined")
            return

        # get project CRS information
        project_crs_osr = get_prjcrs_as_proj4str(self.canvas)

        self.output_profile_polygons_intersections(output_format, output_filepath, project_crs_osr)

        # add theme to QGis project
        if 'shapefile' in output_format and add_to_project:
            try:
                layer = QgsVectorLayer(output_filepath,
                                       QFileInfo(output_filepath).baseName(),
                                       "ogr")
                QgsProject.instance().addMapLayer(layer)
            except:
                QMessageBox.critical(self, "Result", "Unable to load layer in project")
                return

    def output_profile_polygons_intersections(self, output_format, output_filepath, sr):

        # definition of field names
        header_list = ['class_fld',
                       's',
                       'x',
                       'y',
                       'z']

        geoprofile = self.input_geoprofiles.geoprofile(0)
        intersection_lines = geoprofile.intersected_outcrops

        # output for csv file
        if output_format == "csv":
            success, msg = write_intersection_line_csv(
                output_filepath,
                header_list,
                intersection_lines)
            if not success:
                warn(self,
                     self.plugin_name,
                     msg)
        elif output_format == "shapefile - line":
            success, msg = write_intersection_polygon_lnshp(
                output_filepath,
                header_list,
                intersection_lines,
                sr)
            if not success:
                warn(self,
                     self.plugin_name,
                     msg)
        else:
            error(
                parent=self,
                header=self.plugin_name,
                msg="Debug: error in export format")
            return

        if success:
            info(self,
                 self.plugin_name,
                 "Polygon intersections saved")

    def reset_rubber_band(self):

        try:
            self.rubberband.reset(QgsWkbTypes.LineGeometry)
        except:
            pass

    def disconnect_digitize_maptool(self):

        self.digitize_maptool.moved.disconnect(self.canvas_refresh_profile_line)
        self.digitize_maptool.leftClicked.disconnect(self.profile_add_point)
        self.digitize_maptool.rightClicked.disconnect(self.canvas_end_profile_line)

    def stop_profile_digitize_tool(self):

        try:
            self.disconnect_digitize_maptool()
        except:
            pass

        try:
            self.canvas.setMapTool(self.previous_maptool)
        except:
            pass

    def reset_profile_defs(self):

        self.dem_source_profile_line2dt = None
        self.reset_rubber_band()
        self.stop_profile_digitize_tool()

    def closeEvent(self, event):

        try:
            reset_profile_defs(self)
        except:
            pass

        try:
            self.clear_rubberband()
        except:
            pass

        try:
            QgsProject.instance().layerWasAdded.disconnect(self.struct_polygon_refresh_lyr_combobox)
        except:
            pass

        try:
            QgsProject.instance().layerWasAdded.disconnect(self.struct_line_refresh_lyr_combobox)
        except:
            pass

        try:
            QgsProject.instance().layerWasAdded.disconnect(self.struct_point_refresh_lyr_combobox)
        except:
            pass

        try:
            QgsProject.instance().layerRemoved.disconnect(self.struct_polygon_refresh_lyr_combobox)
        except:
            pass

        try:
            QgsProject.instance().layerRemoved.disconnect(self.struct_line_refresh_lyr_combobox)
        except:
            pass

        try:
            QgsProject.instance().layerRemoved.disconnect(self.struct_point_refresh_lyr_combobox)
        except:
            pass


class SourceDEMsDialog(QDialog):

    def __init__(self, plugin_name, raster_layers, parent=None):

        super(SourceDEMsDialog, self).__init__(parent)

        self.plugin_name = plugin_name

        self.singleband_raster_layers_in_project = raster_layers

        self.listDEMs_treeWidget = QTreeWidget()
        self.listDEMs_treeWidget.setColumnCount(2)
        self.listDEMs_treeWidget.headerItem().setText(0, "Select")
        self.listDEMs_treeWidget.headerItem().setText(1, "Name")
        self.listDEMs_treeWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.listDEMs_treeWidget.setDragEnabled(False)
        self.listDEMs_treeWidget.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.listDEMs_treeWidget.setAlternatingRowColors(True)
        self.listDEMs_treeWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.listDEMs_treeWidget.setTextElideMode(Qt.ElideLeft)

        self.populate_raster_layer_treewidget()

        self.listDEMs_treeWidget.resizeColumnToContents(0)
        self.listDEMs_treeWidget.resizeColumnToContents(1)

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

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

        self.setWindowTitle("Define source DEMs")

    def populate_raster_layer_treewidget(self):

        self.listDEMs_treeWidget.clear()

        for raster_layer in self.singleband_raster_layers_in_project:
            tree_item = QTreeWidgetItem(self.listDEMs_treeWidget)
            tree_item.setText(1, raster_layer.name())
            tree_item.setFlags(tree_item.flags() | Qt.ItemIsUserCheckable)
            tree_item.setCheckState(0, 0)


class SourceLine2DLayerDialog(QDialog):

    def __init__(self,
        plugin_name,
        current_line_layers,
        parent=None
    ):

        super(SourceLine2DLayerDialog, self).__init__(parent)

        self.plugin_name = plugin_name
        self.current_line_layers = current_line_layers

        layout = QGridLayout()

        layout.addWidget(QLabel(self.tr("Input line layer:")), 0, 0, 1, 1)
        self.LineLayers_comboBox = QComboBox()
        layout.addWidget(self.LineLayers_comboBox, 0, 1, 1, 3)
        self.refresh_input_profile_layer_combobox()

        self.qrbtLineIsMultiProfile = QCheckBox(self.tr("Layer with multiple profiles:"))
        layout.addWidget(self.qrbtLineIsMultiProfile, 1, 0, 1, 2)

        layout.addWidget(QLabel(self.tr("label field:")), 1, 2, 1, 1)
        self.Trace2D_label_field_comboBox = QComboBox()
        layout.addWidget(self.Trace2D_label_field_comboBox, 1, 3, 1, 1)

        self.refresh_label_field_combobox()
        self.LineLayers_comboBox.currentIndexChanged.connect(self.refresh_label_field_combobox)

        layout.addWidget(QLabel(self.tr("Line order field:")), 2, 0, 1, 1)

        self.Trace2D_order_field_comboBox = QComboBox()
        layout.addWidget(self.Trace2D_order_field_comboBox, 2, 1, 1, 3)

        self.refresh_order_field_combobox()

        self.LineLayers_comboBox.currentIndexChanged.connect(self.refresh_order_field_combobox)

        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)

        layout.addLayout(buttonLayout, 3, 0, 1, 3)

        self.setLayout(layout)

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

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

    def refresh_label_field_combobox(self):

        self.Trace2D_label_field_comboBox.clear()
        self.Trace2D_label_field_comboBox.addItem('--optional--')

        shape_qgis_ndx = self.LineLayers_comboBox.currentIndex()
        self.line_shape = self.current_line_layers[shape_qgis_ndx]

        line_layer_field_list = self.line_shape.dataProvider().fields().toList()
        for field in line_layer_field_list:
            self.Trace2D_label_field_comboBox.addItem(field.name())


class LoadPointListDialog(QDialog):

    def __init__(self, plugin_name, parent=None):

        super(LoadPointListDialog, self).__init__(parent)

        self.plugin_name = plugin_name
        layout = QGridLayout()

        layout.addWidget(QLabel(self.tr("Point list, with at least two points.")), 0, 0, 1, 1)
        layout.addWidget(
            QLabel(self.tr("Each point is defined by a comma-separated, x-y coordinate pair, one for each row")), 1, 0,
            1, 1)
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

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

        self.setWindowTitle("Point list")


class ElevationLineStyleDialog(QDialog):

    def __init__(self, plugin_name, layer_names, layer_colors, parent=None):

        super(ElevationLineStyleDialog, self).__init__(parent)

        self.plugin_name = plugin_name

        #self.elevation_layers = layer_names

        self.qtwdElevationLayers = QTreeWidget()
        self.qtwdElevationLayers.setColumnCount(3)
        self.qtwdElevationLayers.headerItem().setText(0, "View")
        self.qtwdElevationLayers.headerItem().setText(1, "Name")
        self.qtwdElevationLayers.headerItem().setText(2, "Color")
        self.qtwdElevationLayers.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.qtwdElevationLayers.setDragEnabled(False)
        self.qtwdElevationLayers.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.qtwdElevationLayers.setAlternatingRowColors(True)
        self.qtwdElevationLayers.setSelectionMode(QAbstractItemView.SingleSelection)
        self.qtwdElevationLayers.setTextElideMode(Qt.ElideLeft)

        self.populate_elevation_layer_treewidget(layer_names, layer_colors)

        self.qtwdElevationLayers.resizeColumnToContents(0)
        self.qtwdElevationLayers.resizeColumnToContents(1)
        self.qtwdElevationLayers.resizeColumnToContents(2)

        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)

        layout = QGridLayout()

        layout.addWidget(self.qtwdElevationLayers, 0, 0, 1, 3)
        layout.addLayout(buttonLayout, 1, 0, 1, 3)

        self.setLayout(layout)

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

        self.setWindowTitle("Define elevation line style")

    def populate_elevation_layer_treewidget(self, layer_names, layer_colors):

        self.qtwdElevationLayers.clear()

        if layer_colors is None:
            num_available_colors = 0
        else:
            num_available_colors = len(layer_colors)

        for ndx, layer_name in enumerate(layer_names):
            tree_item = QTreeWidgetItem(self.qtwdElevationLayers)
            tree_item.setText(1, layer_name)
            color_button = QgsColorButton()
            if ndx < num_available_colors:
                color_button.setColor(layer_colors[ndx])
            else:
                color_button.setColor(QColor('red'))
            self.qtwdElevationLayers.setItemWidget(tree_item, 2, color_button)
            tree_item.setFlags(tree_item.flags() | Qt.ItemIsUserCheckable)
            tree_item.setCheckState(0, 2)


class ClassificationColorsDialog(QDialog):

    colors = ["darkseagreen", "darkgoldenrod", "darkviolet", "hotpink", "powderblue", "yellowgreen", "palevioletred",
              "seagreen", "darkturquoise", "beige", "darkkhaki", "red", "yellow", "magenta", "blue", "cyan",
              "chartreuse"]

    def __init__(
            self,
            plugin_name,
            classification_set,
            current_graphical_params: dict,
            parent=None
    ):

        super(ClassificationColorsDialog, self).__init__(parent)

        self.plugin_name = plugin_name
        self.current_graphical_params = current_graphical_params
        self.classifications = list(classification_set)

        self.classifications_treeWidget = QTreeWidget()
        self.classifications_treeWidget.setColumnCount(2)
        self.classifications_treeWidget.headerItem().setText(0, "Name")
        self.classifications_treeWidget.headerItem().setText(1, "Color")
        self.classifications_treeWidget.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.classifications_treeWidget.setDragEnabled(False)
        self.classifications_treeWidget.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.classifications_treeWidget.setAlternatingRowColors(True)
        self.classifications_treeWidget.setTextElideMode(Qt.ElideLeft)

        self.update_classification_colors_treewidget()

        self.classifications_treeWidget.resizeColumnToContents(0)
        self.classifications_treeWidget.resizeColumnToContents(1)

        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)

        layout = QGridLayout()

        layout.addWidget(self.classifications_treeWidget, 0, 0, 1, 3)
        layout.addLayout(buttonLayout, 1, 0, 1, 3)

        self.setLayout(layout)

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

        self.setWindowTitle("Classification colors")

    def update_classification_colors_treewidget(self):

        if len(ClassificationColorsDialog.colors) < len(self.classifications):
            dupl_factor = 1 + int(len(self.classifications) / len(ClassificationColorsDialog.colors))
            curr_colors = dupl_factor * ClassificationColorsDialog.colors
        else:
            curr_colors = ClassificationColorsDialog.colors

        self.classifications_treeWidget.clear()

        for classification_id, color in zip(self.classifications, curr_colors):
            tree_item = QTreeWidgetItem(self.classifications_treeWidget)
            tree_item.setText(0, str(classification_id))

            color_QgsColorButton = QgsColorButton()
            if classification_id in self.current_graphical_params:
                color = QColor.fromRgbF(*self.current_graphical_params[classification_id])
            color_QgsColorButton.setColor(QColor(color))
            self.classifications_treeWidget.setItemWidget(tree_item, 1, color_QgsColorButton)


class PlotTopoProfileDialog(QDialog):

    def __init__(self,
                 plugin_name,
                 profile_length_set,
                 natural_elev_min_set,
                 natural_elev_max_set,
                 elevation_layer_names,
                 elevation_layer_colors,
                 parent=None
                 ):

        super(PlotTopoProfileDialog, self).__init__(parent)

        self.plugin_name = plugin_name
        self.elevation_layer_names = elevation_layer_names
        self.elevation_layer_colors = elevation_layer_colors

        # pre-process input data to account for multi.profiles

        profile_length = nanmax(profile_length_set)
        natural_elev_min = nanmin(natural_elev_min_set)
        natural_elev_max = nanmax(natural_elev_max_set)

        # pre-process elevation values

        # suggested plot elevation range

        z_padding = 0.5
        delta_z = natural_elev_max - natural_elev_min
        if delta_z < 0.0:
            warn(self,
                 self.plugin_name,
                 "Error: min elevation larger then max elevation")
            return
        elif delta_z == 0.0:
            plot_z_min = floor(natural_elev_min) - 10
            plot_z_max = ceil(natural_elev_max) + 10
        else:
            plot_z_min = floor(natural_elev_min - delta_z * z_padding)
            plot_z_max = ceil(natural_elev_max + delta_z * z_padding)
        delta_plot_z = plot_z_max - plot_z_min

        # suggested exaggeration value

        w_to_h_rat = float(profile_length) / float(delta_plot_z)
        sugg_ve = 0.2*w_to_h_rat

        layout = QVBoxLayout()

        # Axes

        qlytProfilePlot = QVBoxLayout()

        qgbxPlotSettings = QGroupBox("Axes")

        qlytAxisSettings = QGridLayout()

        self.qcbxSetVerticalExaggeration = QCheckBox("Set vertical exaggeration")
        self.qcbxSetVerticalExaggeration.setChecked(True)
        qlytAxisSettings.addWidget(self.qcbxSetVerticalExaggeration)
        self.qledtDemExagerationRatio = QLineEdit()
        self.qledtDemExagerationRatio.setText("%f" % sugg_ve)
        qlytAxisSettings.addWidget(self.qledtDemExagerationRatio, 0, 1, 1, 1)

        qlytAxisSettings.addWidget(QLabel(self.tr("Plot z max value")), 0, 2, 1, 1)
        self.qledtPlotMaxValue = QLineEdit()
        self.qledtPlotMaxValue.setText("%f" % plot_z_max)
        qlytAxisSettings.addWidget(self.qledtPlotMaxValue, 0, 3, 1, 1)

        self.qcbxInvertXAxisProfile = QCheckBox(self.tr("Flip x-axis direction"))
        qlytAxisSettings.addWidget(self.qcbxInvertXAxisProfile, 1, 0, 1, 2)

        qlytAxisSettings.addWidget(QLabel(self.tr("Plot z min value")), 1, 2, 1, 1)
        self.qledtPlotMinValue = QLineEdit()
        self.qledtPlotMinValue.setText("%f" % plot_z_min)
        qlytAxisSettings.addWidget(self.qledtPlotMinValue, 1, 3, 1, 1)

        qgbxPlotSettings.setLayout(qlytAxisSettings)

        qlytProfilePlot.addWidget(qgbxPlotSettings)

        # Y variables

        qgbxYVariables = QGroupBox("Y variables")

        qlytYVariables = QGridLayout()

        self.qcbxPlotProfileHeight = QCheckBox(self.tr("Height"))
        self.qcbxPlotProfileHeight.setChecked(True)
        qlytYVariables.addWidget(self.qcbxPlotProfileHeight, 0, 0, 1, 1)

        self.qcbxPlotProfileSlope = QCheckBox(self.tr("Slope (degrees)"))
        qlytYVariables.addWidget(self.qcbxPlotProfileSlope, 1, 0, 1, 1)

        self.qrbtPlotAbsoluteSlope = QRadioButton(self.tr("absolute"))
        self.qrbtPlotAbsoluteSlope.setChecked(True);
        qlytYVariables.addWidget(self.qrbtPlotAbsoluteSlope, 1, 1, 1, 1)

        self.qrbtPlotDirectionalSlope = QRadioButton(self.tr("directional"))
        qlytYVariables.addWidget(self.qrbtPlotDirectionalSlope, 1, 2, 1, 1)

        qlytYVariables.addWidget(QLabel("Note: to  calculate correctly the slope, the project must have a CRS set or the DEM(s) must not be in lon-lat"), 2, 0, 1, 3)

        qgbxYVariables.setLayout(qlytYVariables)

        qlytProfilePlot.addWidget(qgbxYVariables)

        # Style parameters

        qgbxStyleParameters = QGroupBox("Plot style")

        qlyStyleParameters = QGridLayout()

        self.qcbxPlotFilledHeight = QCheckBox(self.tr("Filled height"))
        qlyStyleParameters.addWidget(self.qcbxPlotFilledHeight, 0, 0, 1, 1)

        self.qcbxPlotFilledSlope = QCheckBox(self.tr("Filled slope"))
        qlyStyleParameters.addWidget(self.qcbxPlotFilledSlope, 0, 1, 1, 1)

        self.qpbtDefineTopoColors = QPushButton(self.tr("Elevation line visibility and colors"))
        self.qpbtDefineTopoColors.clicked.connect(self.define_profile_colors)
        qlyStyleParameters.addWidget(self.qpbtDefineTopoColors, 1, 0, 1, 3)

        qgbxStyleParameters.setLayout(qlyStyleParameters)

        qlytProfilePlot.addWidget(qgbxStyleParameters)

        layout.addLayout(qlytProfilePlot)

        # ok/cancel section

        okButton = QPushButton("&OK")
        cancelButton = QPushButton("Cancel")

        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()
        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)

        layout.addLayout(buttonLayout)

        self.setLayout(layout)

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

        self.setWindowTitle("Topographic plot parameters")

    def define_profile_colors(self):

        def layer_styles(dialog):

            layer_visibilities = []
            layer_colors = []

            for layer_ndx in range(len(self.elevation_layer_names)):
                curr_item = dialog.qtwdElevationLayers.topLevelItem(layer_ndx)
                if curr_item.checkState(0) == 2:
                    layer_visibilities.append(True)
                else:
                    layer_visibilities.append(False)
                layer_colors.append(dialog.qtwdElevationLayers.itemWidget(curr_item, 2).color())

            return layer_visibilities, layer_colors

        if len(self.elevation_layer_names) == 0:
            warn(self,
                 self.plugin_name,
                 "No loaded elevation layer")
            return

        dialog = ElevationLineStyleDialog(
            self.plugin_name,
            self.elevation_layer_names,
            self.elevation_layer_colors)

        if dialog.exec_():
            visible_elevation_layers, layer_colors = layer_styles(dialog)
        else:
            return

        if len(visible_elevation_layers) == 0:
            warn(self,
                 self.plugin_name,
                 "No visible layer")
            return
        else:
            self.visible_elevation_layers = visible_elevation_layers
            self.elevation_layer_colors = layer_colors


class FigureExportDialog(QDialog):

    def __init__(self, plugin_name, parent=None):

        super(FigureExportDialog, self).__init__(parent)

        self.plugin_name = plugin_name

        layout = QVBoxLayout()

        # main parameters gropbox

        main_params_groupBox = QGroupBox("Main graphic parameters")

        main_params_layout = QGridLayout()

        main_params_layout.addWidget(QLabel(self.tr("Figure width (inches)")), 0, 0, 1, 1)
        self.figure_width_inches_QLineEdit = QLineEdit("40")
        main_params_layout.addWidget(self.figure_width_inches_QLineEdit, 0, 1, 1, 1)

        main_params_layout.addWidget(QLabel(self.tr("Resolution (dpi)")), 0, 2, 1, 1)
        self.figure_resolution_dpi_QLineEdit = QLineEdit("600")
        main_params_layout.addWidget(self.figure_resolution_dpi_QLineEdit, 0, 3, 1, 1)

        main_params_layout.addWidget(QLabel(self.tr("Font size (pts)")), 0, 4, 1, 1)
        self.figure_fontsize_pts_QLineEdit = QLineEdit("36")
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
        self.left_space_value_QDoubleSpinBox.setValue(0.01)
        add_params_layout.addWidget(self.left_space_value_QDoubleSpinBox, 1, 1, 1, 1)

        add_params_layout.addWidget(QLabel("Right space"), 1, 4, 1, 1)
        self.right_space_value_QDoubleSpinBox = QDoubleSpinBox()
        self.right_space_value_QDoubleSpinBox.setRange(0.0, 1.0)
        self.right_space_value_QDoubleSpinBox.setDecimals(2)
        self.right_space_value_QDoubleSpinBox.setSingleStep(0.01)
        self.right_space_value_QDoubleSpinBox.setValue(0.99)
        add_params_layout.addWidget(self.right_space_value_QDoubleSpinBox, 1, 5, 1, 1)

        add_params_layout.addWidget(QLabel("Bottom space"), 2, 2, 1, 1)
        self.bottom_space_value_QDoubleSpinBox = QDoubleSpinBox()
        self.bottom_space_value_QDoubleSpinBox.setRange(0.0, 1.0)
        self.bottom_space_value_QDoubleSpinBox.setDecimals(2)
        self.bottom_space_value_QDoubleSpinBox.setSingleStep(0.01)
        self.bottom_space_value_QDoubleSpinBox.setValue(0.01)
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

        add_params_layout.setRowMinimumHeight(3, 50)

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

        output_file_groupBox = QGroupBox(self.tr("Output file - available formats: tif, pdf, svg"))

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

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

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

        info(self,
             self.plugin_name,
             "Graphic parameters saved")

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
            warn(self,
                 self.plugin_name,
                 "Error in configuration file")
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

        outfile_path = new_file_path(self, "Create", "", "Images (*.svg *.pdf *.tif)")

        if not outfile_path:
            return

        self.figure_outpath_QLineEdit.setText(outfile_path)


class TopographicProfileExportDialog(QDialog):

    def __init__(self, plugin_name, selected_dem_params, parent=None):

        super(TopographicProfileExportDialog, self).__init__(parent)

        self.plugin_name = plugin_name

        layout = QVBoxLayout()

        ##
        # Profile source

        source_groupBox = QGroupBox(self.tr("Profile sources"))

        source_layout = QGridLayout()

        self.src_allselecteddems_QRadioButton = QRadioButton(self.tr("All selected DEMs"))
        source_layout.addWidget(self.src_allselecteddems_QRadioButton, 1, 0, 1, 2)
        self.src_allselecteddems_QRadioButton.setChecked(True)

        self.src_singledem_QRadioButton = QRadioButton(self.tr("Single DEM"))
        source_layout.addWidget(self.src_singledem_QRadioButton, 2, 0, 1, 1)

        self.src_singledemlist_QComboBox = QComboBox()
        selected_dem_layers = [dem_param.layer for dem_param in selected_dem_params]
        for qgsRasterLayer in selected_dem_layers:
            self.src_singledemlist_QComboBox.addItem(qgsRasterLayer.name())
        source_layout.addWidget(self.src_singledemlist_QComboBox, 2, 1, 1, 1)

        self.src_singlegpx_QRadioButton = QRadioButton(self.tr("GPX file"))
        source_layout.addWidget(self.src_singlegpx_QRadioButton, 3, 0, 1, 1)

        source_groupBox.setLayout(source_layout)

        layout.addWidget(source_groupBox)

        ##
        # Output type

        output_type_groupBox = QGroupBox(self.tr("Output format"))

        output_type_layout = QGridLayout()

        self.outtype_shapefile_point_QRadioButton = QRadioButton(self.tr("shapefile - point"))
        output_type_layout.addWidget(self.outtype_shapefile_point_QRadioButton, 0, 0, 1, 1)
        self.outtype_shapefile_point_QRadioButton.setChecked(True)

        self.outtype_shapefile_line_QRadioButton = QRadioButton(self.tr("shapefile - line"))
        output_type_layout.addWidget(self.outtype_shapefile_line_QRadioButton, 1, 0, 1, 1)

        self.outtype_csv_QRadioButton = QRadioButton(self.tr("csv"))
        output_type_layout.addWidget(self.outtype_csv_QRadioButton, 2, 0, 1, 1)

        output_type_groupBox.setLayout(output_type_layout)

        layout.addWidget(output_type_groupBox)

        ##
        # Output name/path

        output_path_groupBox = QGroupBox(self.tr("Output file"))

        output_path_layout = QGridLayout()

        self.outpath_QLineEdit = QLineEdit()
        output_path_layout.addWidget(self.outpath_QLineEdit, 0, 0, 1, 1)

        self.outpath_QPushButton = QPushButton("....")
        self.outpath_QPushButton.clicked.connect(self.define_outpath)
        output_path_layout.addWidget(self.outpath_QPushButton, 0, 1, 1, 1)

        self.load_output_checkBox = QCheckBox("load output shapefile in project")
        self.load_output_checkBox.setChecked(True)
        output_path_layout.addWidget(self.load_output_checkBox, 1, 0, 1, 2)

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

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

        self.setWindowTitle("Export topographic profile")

    def define_outpath(self):

        if self.outtype_shapefile_line_QRadioButton.isChecked() or self.outtype_shapefile_point_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Save file", "", "Shapefiles (*.shp)")
        elif self.outtype_csv_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Save file", "", "Csv (*.csv)")
        else:
            warn(self,
                 self.plugin_name,
                 self.tr("Output type definiton error"))
            return

        self.outpath_QLineEdit.setText(outfile_path)


class PointDataExportDialog(QDialog):

    def __init__(self, plugin_name, parent=None):

        super(PointDataExportDialog, self).__init__(parent)

        self.plugin_name = plugin_name

        layout = QVBoxLayout()

        ##
        # Output type

        output_type_groupBox = QGroupBox(self.tr("Output format"))

        output_type_layout = QGridLayout()

        self.outtype_shapefile_point_QRadioButton = QRadioButton(self.tr("shapefile - point"))
        output_type_layout.addWidget(self.outtype_shapefile_point_QRadioButton, 0, 0, 1, 1)
        self.outtype_shapefile_point_QRadioButton.setChecked(True)

        self.outtype_csv_QRadioButton = QRadioButton(self.tr("csv"))
        output_type_layout.addWidget(self.outtype_csv_QRadioButton, 1, 0, 1, 1)

        output_type_groupBox.setLayout(output_type_layout)

        layout.addWidget(output_type_groupBox)

        ##
        # Output name/path

        output_path_groupBox = QGroupBox(self.tr("Output path"))

        output_path_layout = QGridLayout()

        self.outpath_QLineEdit = QLineEdit()
        output_path_layout.addWidget(self.outpath_QLineEdit, 0, 0, 1, 1)

        self.outpath_QPushButton = QPushButton(self.tr("Choose"))
        self.outpath_QPushButton.clicked.connect(self.define_outpath)
        output_path_layout.addWidget(self.outpath_QPushButton, 0, 1, 1, 1)

        self.load_output_checkBox = QCheckBox("load output shapefile in project")
        self.load_output_checkBox.setChecked(True)
        output_path_layout.addWidget(self.load_output_checkBox, 1, 0, 1, 2)

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

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

        self.setWindowTitle("Export geological attitudes")

    def define_outpath(self):

        if self.outtype_shapefile_point_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Path", "*.shp", "Shapefile")
        elif self.outtype_csv_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Path", "*.csv", "Csv")
        else:
            warn(self,
                 self.plugin_name,
                 self.tr("Output type definiton error"))
            return

        self.outpath_QLineEdit.setText(outfile_path)


class LineDataExportDialog(QDialog):

    def __init__(self, plugin_name, parent=None):

        super(LineDataExportDialog, self).__init__(parent)

        self.plugin_name = plugin_name

        layout = QVBoxLayout()

        ##
        # Output type

        output_type_groupBox = QGroupBox(self.tr("Output format"))

        output_type_layout = QGridLayout()

        self.outtype_shapefile_line_QRadioButton = QRadioButton(self.tr("shapefile - line"))
        output_type_layout.addWidget(self.outtype_shapefile_line_QRadioButton, 0, 0, 1, 1)
        self.outtype_shapefile_line_QRadioButton.setChecked(True)

        self.outtype_csv_QRadioButton = QRadioButton(self.tr("csv"))
        output_type_layout.addWidget(self.outtype_csv_QRadioButton, 0, 1, 1, 1)

        output_type_groupBox.setLayout(output_type_layout)

        layout.addWidget(output_type_groupBox)

        ##
        # Output name/path

        output_path_groupBox = QGroupBox(self.tr("Output file"))

        output_path_layout = QGridLayout()

        self.outpath_QLineEdit = QLineEdit()
        output_path_layout.addWidget(self.outpath_QLineEdit, 0, 0, 1, 1)

        self.outpath_QPushButton = QPushButton("....")
        self.outpath_QPushButton.clicked.connect(self.define_outpath)
        output_path_layout.addWidget(self.outpath_QPushButton, 0, 1, 1, 1)

        self.load_output_checkBox = QCheckBox("load output in project")
        self.load_output_checkBox.setChecked(True)
        output_path_layout.addWidget(self.load_output_checkBox, 1, 0, 1, 2)

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

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

        self.setWindowTitle("Export")

    def define_outpath(self):

        if self.outtype_shapefile_line_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Save file", "", "Shapefiles (*.shp)")
        elif self.outtype_csv_QRadioButton.isChecked():
            outfile_path = new_file_path(self, "Save file", "", "Csv (*.csv)")
        else:
            warn(self,
                 self.plugin_name,
                 self.tr("Output type definiton error"))
            return

        self.outpath_QLineEdit.setText(outfile_path)


class StatisticsDialog(QDialog):

    def __init__(
            self,
            plugin_name,
            geoprofile_set,
            parent=None
    ):

        super(StatisticsDialog, self).__init__(parent)

        self.plugin_name = plugin_name

        layout = QVBoxLayout()

        self.text_widget = QTextEdit()
        self.text_widget.setReadOnly(True)

        num_profiles = geoprofile_set.geoprofiles_num
        stat_report = "\nGeneral statistics for {} profiles\n".format(num_profiles)

        for ndx in range(num_profiles):

            profile_elevations = geoprofile_set.geoprofile(ndx).topo_profiles

            profiles_stats = list(
                zip(
                    profile_elevations.surface_names,
                    list(
                        zip(
                            profile_elevations.statistics_elev,
                            profile_elevations.statistics_dirslopes,
                            profile_elevations.statistics_slopes
                        )
                    )
                )
            )

            stat_report += "\nStatistics for profile # {}".format(ndx+1)
            stat_report += "\n\tLength: {}".format(profile_elevations.profile_length)
            stat_report += "\n\tTopographic elevations"
            stat_report += "\n\t - min: {}".format(profile_elevations.natural_elev_range[0])
            stat_report += "\n\t - max: {}".format(profile_elevations.natural_elev_range[1])
            stat_report += "\n" + self.report_stats(profiles_stats)

        for ndx in range(num_profiles):

            topo_profiles = geoprofile_set.geoprofile(ndx).topo_profiles
            resampled_line_xs = topo_profiles.planar_xs
            resampled_line_ys = topo_profiles.planar_ys

            if resampled_line_xs is not None:

                stat_report += "\nSampling points ({}) for profile # {}".format(len(resampled_line_xs), ndx + 1)

                for ln_ndx, (x, y) in enumerate(zip(resampled_line_xs, resampled_line_ys)):
                   stat_report += "\n{}, {}, {}".format(ln_ndx+1, x, y)

        self.text_widget.insertPlainText(stat_report)

        layout.addWidget(self.text_widget)

        self.setLayout(layout)

        self.setWindowTitle("Statistics")

    def report_stats(self, profiles_stats):

        def type_report(values):

            type_report = 'min: %s\n' % (values['min'])
            type_report += 'max: %s\n' % (values['max'])
            type_report += 'mean: %s\n' % (values['mean'])
            type_report += 'variance: %s\n' % (values['var'])
            type_report += 'standard deviation: %s\n\n' % (values['std'])

            return type_report

        report = 'Dataset statistics\n'
        types = [
            'elevations',
            'directional slopes',
            'absolute slopes'
        ]

        for name, stats in profiles_stats:
            report += '\ndataset name\n%s\n\n' % name
            for prof_type, stat_val in zip(types, stats):
                report += '%s\n\n' % prof_type
                report += type_report(stat_val)

        return report
