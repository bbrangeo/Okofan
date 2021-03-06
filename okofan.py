#!/usr/bin/env python
"""Gui application to analyze Ökofen log files."""

import sys
import csv
import glob
from datetime import datetime
import copy

import numpy as np
import PyQt5.QtCore
from PyQt5.QtWidgets import (QApplication, QFileDialog, QTableWidgetItem,
                             QAbstractItemView, QMainWindow, QWidget,
                             QHBoxLayout, QTabWidget, QStatusBar, QAction,
                             QTableWidget, QVBoxLayout, QCalendarWidget,
                             QMessageBox, QProgressDialog, QSizePolicy)
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates


class MplCanvas(FigureCanvasQTAgg):

    """This is the canvas (QWidget) for the log graphs."""

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        fig.autofmt_xdate()

        FigureCanvasQTAgg.__init__(self, fig)
        self.setParent(parent)

        FigureCanvasQTAgg.setSizePolicy(self,
                                        QSizePolicy.Expanding,
                                        QSizePolicy.Expanding)
        FigureCanvasQTAgg.updateGeometry(self)

    def set_data(self, x, y, status=None):
        """Takes data and plots it on the canvas

        :param x: Numpy array of X axis data to be plotted.
        :param y: Tuple of Numpy arrays of Y axis data to be plotted.
        :param status: Status with which to set the background shading.
        :return:

        """
        for axis in y:
            self.axes.plot(x, axis)

        self.axes.fill_between(x, 0, self.axes.get_ylim()[1],
                               where=status == 'Zuendung',
                               facecolor='green', alpha=0.2)
        self.axes.fill_between(x, 0, self.axes.get_ylim()[1],
                               where=status == 'Softstrt',
                               facecolor='yellow', alpha=0.2)
        self.axes.fill_between(x, 0, self.axes.get_ylim()[1],
                               where=status == 'Burning',
                               facecolor='red', alpha=0.2)
        self.axes.fill_between(x, 0, self.axes.get_ylim()[1],
                               where=status == 'Nachlauf',
                               facecolor='blue', alpha=0.2)

        self.axes.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.axes.grid(True)
        self.axes.xaxis.axis_date()


class MainWindow(QMainWindow):

    """This class defines the main application Window."""

    # dictionary of log file paths with date as key (YYYY-MM-DD)
    logfiles = {}

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # setting up the ui design
        self.resize(680, 500)
        self.setMinimumSize(PyQt5.QtCore.QSize(680, 500))
        self.setWindowTitle('Ökofan')

        # construct the main widget
        self.centralwidget = QWidget(self)
        self.centralwidgetlayout = QHBoxLayout(self.centralwidget)
        self.setCentralWidget(self.centralwidget)

        # construct the menu bar items
        self.actionOpen = QAction('Open Directory', self)
        self.actionOpen.setShortcut('Ctrl+O')
        self.actionOpen.setStatusTip('Open a log file directory')
        self.actionOpen.triggered.connect(self.open_action)
        self.actionExit = QAction('Exit', self)
        self.actionExit.setShortcut('Ctrl+Q')
        self.actionExit.setStatusTip('Exit the application')
        self.actionExit.triggered.connect(self.exit_action)
        self.actionAbout = QAction('About', self)
        self.actionAbout.setShortcut('Ctrl+A')
        self.actionAbout.setStatusTip('Open the About dialog')
        self.actionAbout.triggered.connect(self.about_action)

        # add menu bar items to menu bar
        self.menuFile = self.menuBar().addMenu('&File')
        self.menuFile.addAction(self.actionOpen)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)
        self.menuHelp = self.menuBar().addMenu('&Help')
        self.menuHelp.addAction(self.actionAbout)

        # construct the status bar
        self.statusbar = QStatusBar(self)
        self.setStatusBar(self.statusbar)

        # construct the main window tab
        self.maintabwidget = QTabWidget(self.centralwidget)

        # construct the overview tab
        self.taboverview = QWidget()
        self.taboverviewlayout = QHBoxLayout(self.taboverview)

        # layout to hold the calendar widget
        self.overviewcalendarlayout = QVBoxLayout(self.taboverview)

        # construct the calendar widget
        self.overviewcalendar = QCalendarWidget(self.taboverview)
        self.overviewcalendar.setMaximumSize(PyQt5.QtCore.QSize(260, 183))
        self.overviewcalendar.setVerticalHeaderFormat(QCalendarWidget
                                                      .NoVerticalHeader)
        self.overviewcalendar.setGridVisible(True)
        self.overviewcalendar.setNavigationBarVisible(True)
        self.overviewcalendar.clicked.connect(self.overview_cal_clicked)
        self.overviewcalendar.activated.connect(self.item_activated)
        self.overviewcalendarlayout.addWidget(self.overviewcalendar)
        self.overviewcalendarlayout.addStretch()
        self.taboverviewlayout.addLayout(self.overviewcalendarlayout)

        # construct the log list table
        self.loglist = QTableWidget(self.taboverview)
        self.loglist.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.loglist.setSelectionMode(QAbstractItemView.SingleSelection)
        self.loglist.itemSelectionChanged.connect(self.selection_changed)
        self.loglist.itemActivated.connect(self.item_activated)
        self.taboverviewlayout.addWidget(self.loglist)

        # construct the detail tab
        self.tabdetaillist = QWidget()
        self.logdetaillistlayout = QVBoxLayout(self.tabdetaillist)

        # construct the log detail table
        self.logdetaillist = QTableWidget(self.tabdetaillist)
        self.logdetaillist.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.logdetaillistlayout.addWidget(self.logdetaillist)

        # construct the detail graph tab
        self.tabdetailgraph = QWidget()
        self.logdetailgraphlayout = QVBoxLayout(self.tabdetailgraph)

        # add the tabs to the main tab widget
        self.maintabwidget.addTab(self.taboverview, 'Overview')
        self.maintabwidget.addTab(self.tabdetaillist, 'Detail log')
        self.maintabwidget.addTab(self.tabdetailgraph, 'Detail graph')
        self.centralwidgetlayout.addWidget(self.maintabwidget)

    def open_action(self):
        """Open a file dialog to get the logfile location.

        :return: empty

        """
        # opens directory chooser dialog
        directory = QFileDialog.getExistingDirectory(self,
                                                     'Open Directory', '',
                                                     QFileDialog.ShowDirsOnly)

        # checks if the user canceled the dialog
        if not directory:
            return

        # logfile name pattern: CM130513.CSV
        filelist = glob.glob(''.join((directory, '/CM', '[0-9]' * 6, '.csv')))

        # check if there were suitably named files and load them
        if filelist:
            self.load_log_list(filelist)

    def load_log_list(self, files):
        """Display a list of log files in the overview tab

        :param files: List of log file paths.
        :return: empty

        """
        # construct the progressbar dialog in case opening takes a while
        progress = QProgressDialog('Opening files...', 'Cancel', 0,
                                   len(files), self)
        progress.setWindowModality(PyQt5.QtCore.Qt.WindowModal)

        logfilescopy = copy.deepcopy(self.logfiles)

        logdata = []
        for i, file in enumerate(files, start=1):
            # get date from the log file and convert it to YYYY-MM-DD
            date = self.getlogdate(file)

            # save path and date for later use
            self.logfiles[date] = file

            logdata.append(date)

            # increment the progress bar
            progress.setValue(i)
            if progress.wasCanceled():
                self.logfiles = logfilescopy
                return

        # construct the overview log list
        self.loglist.setRowCount(len(logdata))
        self.loglist.setColumnCount(1)
        self.loglist.setHorizontalHeaderLabels(['Date'])
        self.loglist.horizontalHeader().setStretchLastSection(True)

        for rowcount, rowdata in enumerate(logdata):
            cellitem = QTableWidgetItem()
            cellitem.setFlags(PyQt5.QtCore.Qt.ItemIsSelectable |
                              PyQt5.QtCore.Qt.ItemIsEnabled)
            cellitem.setText(str(rowdata))
            self.loglist.setItem(rowcount, 0, cellitem)

    @staticmethod
    def exit_action():
        """Quit the application.

        :return: empty

        """
        QApplication.quit()

    @staticmethod
    def about_action(self):
        """Open the about dialog.

        :return: empty

        """
        # TODO Implement about_action: Opening about dialog.
        pass

    def overview_cal_clicked(self, date):
        """Select the selected day in the log table.

        :param date: Selected date.

        """
        items = self.loglist.findItems(date.toString('yyyy-MM-dd'),
                                       PyQt5.QtCore.Qt.MatchExactly)

        if items:
            for item in items:
                results = int(item.row())
                self.loglist.selectRow(results)

    def selection_changed(self):
        """Select the day in the calendar widget."""
        selected = self.loglist.selectedItems()[0].text()
        date = datetime.strptime(selected, '%Y-%m-%d')
        self.overviewcalendar.setSelectedDate(date)

    def item_activated(self, param):
        """Load the selected log in the detail table.

        :param param: QTableWidgetItem or QDate that was activated.

        """

        # Check if you got a WidgetItem from the table
        # or a QDate from the calendar.
        if isinstance(param, QTableWidgetItem):
            date = param.text()
        elif isinstance(param, PyQt5.QtCore.QDate):
            date = param.toString('yyyy-MM-dd')
        else:
            return

        # check if there is a log for the selected date
        if date not in self.logfiles:
            QMessageBox.warning(self, 'Error', ''.join(('No log for day \'',
                                                        date, '\' found.')),
                                QMessageBox.Ok)
            return

        # read csv file and save the data to a list
        logdata = np.genfromtxt(self.logfiles[date], delimiter=';',
                                usecols=range(1, 13), names=True,
                                autostrip=True, unpack=True,
                                filling_values='Burning',
                                dtype=(object, int, int, int, int, int,
                                       int, int, int, int, int, object),
                                converters={1: lambda s: convert_time(s, date),
                                            12: lambda s: s.decode()})
        logdata.dtype.names = ('Time', 'KF', 'RGF', 'SP_FRT', 'FRT', 'ES', 'PA', 'LL', 'SZ', 'SP_uP', 'uP', 'SM')

        # setup the log detail table
        self.logdetaillist.setRowCount(len(logdata))
        self.logdetaillist.setColumnCount(len(logdata[0]))
        self.logdetaillist.setHorizontalHeaderLabels(logdata.dtype.names)
        self.logdetaillist.horizontalHeader().setStretchLastSection(True)

        # insert data in to the table
        for rowcount, rowdata in enumerate(logdata):
            for colcount, coldata in enumerate(rowdata):
                cellitem = QTableWidgetItem()
                cellitem.setFlags(PyQt5.QtCore.Qt.ItemIsSelectable |
                                  PyQt5.QtCore.Qt.ItemIsEnabled)
                if isinstance(coldata, datetime):
                    cellitem.setText(coldata.time().isoformat())
                else:
                    cellitem.setText(str(coldata))
                self.logdetaillist.setItem(rowcount, colcount, cellitem)

        self.logdetaillist.resizeColumnsToContents()

        # plot the data on the canvas
        graph = MplCanvas(self.tabdetailgraph, width=10, height=4, dpi=100)
        graph.set_data(matplotlib.dates.date2num(logdata['Time']),
                       [logdata['FRT']], logdata['SM'])
        self.logdetailgraphlayout.addWidget(graph)

        # switch to the details tab
        self.maintabwidget.setCurrentIndex(1)

    @staticmethod
    def getlogdate(filepath):
        """Open a log file and get the log files date.

        :param filepath: Path to the log file.
        :return: Date the log File was written in YYYY-MM-DD.

        """
        with open(filepath, newline='') as logfile:
            logfile = (x.replace('\0', '') for x in logfile)
            reader = csv.reader(strip_lines(logfile), delimiter=';')

            # skip the header
            next(reader)

            date = datetime.strptime(next(reader)[0], '%d.%m.%Y')

            return date.date().isoformat()


def strip_lines(iterable):
    """Strip empty lines from the iterator.

    :param iterable: Iterator to strip lines from
    :return: Yields next iterator line

    """
    for line in iterable:
        if line.strip():
            yield line


def convert_time(timestring, date='1990-01-01'):
    """Convert time string to have leading zeros.

    :param timestring: Byte array in '%H:%M:%S' without leading zeros.
    :param date: Date of the timestamp (defaults to 1990-01-01)
    :return: time object

    """
    return datetime.strptime(' '.join((date, timestring.decode())),
                             '%Y-%m-%d %H:%M:%S')


app = QApplication(sys.argv)
widget = MainWindow()
widget.show()
sys.exit(app.exec_())
