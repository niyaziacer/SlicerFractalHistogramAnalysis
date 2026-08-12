import csv
import importlib
import logging
import os
from datetime import datetime

import vtk
import qt
import ctk
import slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

# Slicer's "Reload" button only re-executes THIS file - sibling modules like
# fractal_histogram_core.py and volbrain_labels.py stay cached in sys.modules
# from the first import and would otherwise silently keep running stale code
# after edits, even though this file looks freshly reloaded. Force-reload
# them explicitly every time this file itself is (re)loaded, so "Reload"
# actually picks up changes made to those files too, not just this one.
import fractal_histogram_core as core
importlib.reload(core)
try:
    import volbrain_labels
    importlib.reload(volbrain_labels)
except ImportError:
    pass


#
# FractalHistogramAnalysis
#

class FractalHistogramAnalysis(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Fractal & Histogram Analysis"
        self.parent.categories = ["Quantification"]
        self.parent.dependencies = []
        self.parent.contributors = ["Niyazi Acer (Erciyes University, Retired)"]
        self.parent.helpText = """
Computes the 3D box-counting fractal dimension (4 variants) and intensity
histogram statistics (mean/std/skewness/kurtosis) of a selected segment,
directly from a Segmentation node loaded in the scene - no manual
export-to-file step needed.
See the <a href="https://github.com/niyaziacer/brain-fractal-histogram-analysis">project README</a>
for the methodology and the standalone CLI version of this tool.
"""
        self.parent.acknowledgementText = """
Developed by Prof. Dr. Niyazi Acer (Retired, Erciyes University).
"""


#
# FractalHistogramAnalysisWidget
#

class FractalHistogramAnalysisWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        self.logic = None
        self._segmentationNode = None
        self._segmentRawNames = {}  # segmentId -> Slicer's actual segment name (e.g. "Segment_47"),
        # kept separate from the friendly display text shown in the UI, so parse_roi_info()
        # always gets the real name it knows how to resolve (see onSegmentationNodeChanged).

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        # --- Inputs ---
        inputsCollapsibleButton = ctk.ctkCollapsibleButton()
        inputsCollapsibleButton.text = "Inputs"
        self.layout.addWidget(inputsCollapsibleButton)
        inputsFormLayout = qt.QFormLayout(inputsCollapsibleButton)

        self.segmentationSelector = slicer.qMRMLNodeComboBox()
        self.segmentationSelector.nodeTypes = ["vtkMRMLSegmentationNode"]
        self.segmentationSelector.selectNodeUponCreation = False
        self.segmentationSelector.addEnabled = False
        self.segmentationSelector.removeEnabled = False
        self.segmentationSelector.noneEnabled = True
        self.segmentationSelector.showHidden = False
        self.segmentationSelector.setMRMLScene(slicer.mrmlScene)
        self.segmentationSelector.setToolTip("Segmentation node containing the region(s) to analyze.")
        inputsFormLayout.addRow("Segmentation: ", self.segmentationSelector)

        self.segmentSelector = qt.QComboBox()
        self.segmentSelector.setToolTip("Segment (region) to analyze. Only one segment is processed per click of Calculate.")
        inputsFormLayout.addRow("Segment: ", self.segmentSelector)

        self.t1Selector = slicer.qMRMLNodeComboBox()
        self.t1Selector.nodeTypes = ["vtkMRMLScalarVolumeNode"]
        self.t1Selector.selectNodeUponCreation = False
        self.t1Selector.addEnabled = False
        self.t1Selector.removeEnabled = False
        self.t1Selector.noneEnabled = True
        self.t1Selector.setMRMLScene(slicer.mrmlScene)
        self.t1Selector.setToolTip(
            "Optional. T1 (or other) intensity volume to compute histogram statistics from. "
            "If left as 'None', only the fractal dimension is computed.")
        inputsFormLayout.addRow("T1 volume (optional, for histogram): ", self.t1Selector)

        self.outputDirSelector = ctk.ctkPathLineEdit()
        self.outputDirSelector.filters = ctk.ctkPathLineEdit.Dirs
        self.outputDirSelector.setToolTip(
            "Optional. If set, results are appended to fractal_results_comparison.csv / "
            "roi_histogram_stats.csv in this folder (same format as the CLI tool), and "
            "comparison/histogram plots are saved here as PNG.")
        inputsFormLayout.addRow("Save results to folder (optional): ", self.outputDirSelector)

        # --- Calculate button (single segment, all 4 FD variants) ---
        self.calculateButton = qt.QPushButton("Calculate")
        self.calculateButton.toolTip = "Run full analysis (all 4 fractal dimension variants, and histogram if a T1 volume is selected) on the selected segment."
        self.calculateButton.enabled = False
        self.layout.addWidget(self.calculateButton)

        self.statusLabel = qt.QLabel("")
        self.statusLabel.setWordWrap(True)
        self.layout.addWidget(self.statusLabel)

        # --- Batch analysis (multiple segments, bbox variants only - fast) ---
        batchCollapsibleButton = ctk.ctkCollapsibleButton()
        batchCollapsibleButton.text = "Batch Analysis (multiple segments)"
        batchCollapsibleButton.collapsed = True
        self.layout.addWidget(batchCollapsibleButton)
        batchLayout = qt.QVBoxLayout(batchCollapsibleButton)

        batchInfoLabel = qt.QLabel(
            "For segmentations with many regions (e.g. VolBrain's native_structures, "
            "100+ labels). Check the segments to process, then click below. To keep "
            "this fast, batch mode computes only the bbox-based FD variants "
            "(FD_bbox_boundary, FD_bbox_volume) - not the full-image variants, which "
            "would rescan the whole volume for every single region.")
        batchInfoLabel.setWordWrap(True)
        batchLayout.addWidget(batchInfoLabel)

        self.segmentListWidget = qt.QListWidget()
        self.segmentListWidget.setSelectionMode(qt.QAbstractItemView.NoSelection)
        self.segmentListWidget.setMaximumHeight(220)
        batchLayout.addWidget(self.segmentListWidget)

        selectButtonsLayout = qt.QHBoxLayout()
        self.selectAllButton = qt.QPushButton("Select All")
        self.clearSelectionButton = qt.QPushButton("Clear Selection")
        selectButtonsLayout.addWidget(self.selectAllButton)
        selectButtonsLayout.addWidget(self.clearSelectionButton)
        batchLayout.addLayout(selectButtonsLayout)

        self.batchCalculateButton = qt.QPushButton("Calculate Selected")
        self.batchCalculateButton.toolTip = "Run bbox-only analysis on every checked segment, one at a time."
        self.batchCalculateButton.enabled = False
        batchLayout.addWidget(self.batchCalculateButton)

        self.batchProgressBar = qt.QProgressBar()
        self.batchProgressBar.visible = False
        batchLayout.addWidget(self.batchProgressBar)

        # --- Results table ---
        resultsCollapsibleButton = ctk.ctkCollapsibleButton()
        resultsCollapsibleButton.text = "Results"
        self.layout.addWidget(resultsCollapsibleButton)
        resultsLayout = qt.QVBoxLayout(resultsCollapsibleButton)

        self.resultsTable = qt.QTableWidget()
        self.resultsTable.setColumnCount(10)
        self.resultsTable.setHorizontalHeaderLabels([
            "Region", "Hemisphere", "Voxels",
            "FD full/bnd", "FD full/vol", "FD bbox/bnd", "FD bbox/vol (rec.)",
            "Mean", "Std", "Skew/Kurt",
        ])
        self.resultsTable.horizontalHeader().setStretchLastSection(True)
        self.resultsTable.setEditTriggers(qt.QAbstractItemView.NoEditTriggers)
        resultsLayout.addWidget(self.resultsTable)

        resultsButtonsLayout = qt.QHBoxLayout()
        self.clearResultsButton = qt.QPushButton("Clear Results")
        self.clearResultsButton.toolTip = "Empty the results table. Results are always appended (never overwritten automatically), so re-running Calculate on the same segment adds another row - use this to start fresh."
        self.exportExcelButton = qt.QPushButton("Export to Excel")
        self.exportExcelButton.toolTip = "Save the current Results table as an .xls file (HTML-table format, opens directly in Excel/LibreOffice - same approach as the SlicerVolBrain extension, no extra Python packages needed)."
        resultsButtonsLayout.addWidget(self.clearResultsButton)
        resultsButtonsLayout.addWidget(self.exportExcelButton)
        resultsLayout.addLayout(resultsButtonsLayout)

        self.plotLabel = qt.QLabel()
        self.plotLabel.setAlignment(qt.Qt.AlignCenter)
        resultsLayout.addWidget(self.plotLabel)

        self.layout.addStretch(1)

        # --- Connections ---
        self.segmentationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSegmentationNodeChanged)
        self.calculateButton.connect("clicked(bool)", self.onCalculateButton)
        self.selectAllButton.connect("clicked(bool)", self.onSelectAll)
        self.clearSelectionButton.connect("clicked(bool)", self.onClearSelection)
        self.batchCalculateButton.connect("clicked(bool)", self.onBatchCalculateButton)
        self.clearResultsButton.connect("clicked(bool)", self.onClearResults)
        self.exportExcelButton.connect("clicked(bool)", self.onExportExcel)

        self.logic = FractalHistogramAnalysisLogic()
        self.onSegmentationNodeChanged()

    def onSegmentationNodeChanged(self, node=None):
        self._segmentationNode = self.segmentationSelector.currentNode()
        self.segmentSelector.clear()
        self.segmentListWidget.clear()
        self._segmentRawNames = {}

        if self._segmentationNode is None:
            self.calculateButton.enabled = False
            self.batchCalculateButton.enabled = False
            return

        segmentation = self._segmentationNode.GetSegmentation()
        segmentIDs = vtk.vtkStringArray()
        segmentation.GetSegmentIDs(segmentIDs)
        for i in range(segmentIDs.GetNumberOfValues()):
            segmentId = segmentIDs.GetValue(i)
            segment = segmentation.GetSegment(segmentId)
            segmentName = segment.GetName()
            self._segmentRawNames[segmentId] = segmentName

            displayName = self._friendlyDisplayName(segmentName)
            self.segmentSelector.addItem(displayName, segmentId)

            item = qt.QListWidgetItem(displayName)
            item.setData(qt.Qt.UserRole, segmentId)
            item.setFlags(item.flags() | qt.Qt.ItemIsUserCheckable)
            item.setCheckState(qt.Qt.Unchecked)
            self.segmentListWidget.addItem(item)

        self.calculateButton.enabled = self.segmentSelector.count > 0
        self.batchCalculateButton.enabled = self.segmentListWidget.count > 0

    @staticmethod
    def _friendlyDisplayName(rawSegmentName):
        """Build a UI display string like 'Hippocampus (Right)  [Segment_47]' from
        the raw Slicer segment name, using the same resolution logic (volBrain
        table, or generic filename parsing) used for the actual results. The
        raw name in brackets is kept visible so it's traceable/debuggable, and
        because it is the string that actually gets passed to parse_roi_info()
        again downstream - the display text itself is never used for that."""
        roi, hemi = core.parse_roi_info(rawSegmentName)
        return f"{roi} ({hemi})  [{rawSegmentName}]"

    def onCalculateButton(self):
        if self._segmentationNode is None or self.segmentSelector.count == 0:
            return
        segmentId = self.segmentSelector.itemData(self.segmentSelector.currentIndex)
        segmentName = self._segmentRawNames.get(segmentId, self.segmentSelector.currentText)
        t1Node = self.t1Selector.currentNode()
        outputDir = self.outputDirSelector.currentPath.strip() or None

        self.statusLabel.text = f"Calculating for '{segmentName}'..."
        slicer.app.processEvents()
        try:
            result = self.logic.run(self._segmentationNode, segmentId, segmentName, t1Node, outputDir)
        except Exception as e:
            logging.error(f"FractalHistogramAnalysis calculation failed: {e}")
            self.statusLabel.text = f"Error: {e}"
            slicer.util.errorDisplay(f"Calculation failed:\n{e}")
            return

        self._addResultRow(result)
        self.statusLabel.text = f"Done: '{segmentName}' ({result['voxel_count']} voxels)."

        if result.get("plot_path") and os.path.isfile(result["plot_path"]):
            pixmap = qt.QPixmap(result["plot_path"])
            if not pixmap.isNull():
                self.plotLabel.setPixmap(pixmap.scaledToWidth(380, qt.Qt.SmoothTransformation))

    def onClearResults(self):
        self.resultsTable.setRowCount(0)

    def onExportExcel(self):
        if self.resultsTable.rowCount == 0:
            slicer.util.infoDisplay("Results table is empty - nothing to export.")
            return

        defaultName = f"fractal_histogram_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xls"
        filePath = qt.QFileDialog.getSaveFileName(self.parent, "Export Results to Excel", defaultName, "Excel Files (*.xls)")
        if not filePath:
            return
        if not filePath.lower().endswith(".xls"):
            filePath += ".xls"

        headers = [self.resultsTable.horizontalHeaderItem(c).text() for c in range(self.resultsTable.columnCount)]
        htmlParts = [
            "<html><head><meta charset='utf-8'></head><body>",
            "<table border='1' cellspacing='0' cellpadding='4'>",
            "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>",
        ]
        for row in range(self.resultsTable.rowCount):
            cells = []
            for col in range(self.resultsTable.columnCount):
                item = self.resultsTable.item(row, col)
                cells.append(item.text() if item else "")
            htmlParts.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
        htmlParts.append("</table></body></html>")

        try:
            with open(filePath, "w", encoding="utf-8") as f:
                f.write("\n".join(htmlParts))
        except Exception as e:
            slicer.util.errorDisplay(f"Could not save file:\n{e}")
            return

        slicer.util.infoDisplay(f"Exported {self.resultsTable.rowCount} row(s) to:\n{filePath}")

    def onSelectAll(self):
        for i in range(self.segmentListWidget.count):
            self.segmentListWidget.item(i).setCheckState(qt.Qt.Checked)

    def onClearSelection(self):
        for i in range(self.segmentListWidget.count):
            self.segmentListWidget.item(i).setCheckState(qt.Qt.Unchecked)

    def onBatchCalculateButton(self):
        if self._segmentationNode is None:
            return

        checked = []
        for i in range(self.segmentListWidget.count):
            item = self.segmentListWidget.item(i)
            if item.checkState() == qt.Qt.Checked:
                segmentId = item.data(qt.Qt.UserRole)
                segmentName = self._segmentRawNames.get(segmentId, item.text())
                checked.append((segmentId, segmentName))

        if not checked:
            slicer.util.infoDisplay("No segments are checked. Check at least one segment in the list first.")
            return

        t1Node = self.t1Selector.currentNode()
        outputDir = self.outputDirSelector.currentPath.strip() or None

        self.batchProgressBar.visible = True
        self.batchProgressBar.minimum = 0
        self.batchProgressBar.maximum = len(checked)
        self.batchProgressBar.value = 0

        errors = []
        for index, (segmentId, segmentName) in enumerate(checked):
            self.statusLabel.text = f"Batch: {index + 1}/{len(checked)} - '{segmentName}'..."
            slicer.app.processEvents()
            try:
                result = self.logic.run(self._segmentationNode, segmentId, segmentName, t1Node, outputDir,
                                         computeFull=False)
                self._addResultRow(result)
            except Exception as e:
                logging.error(f"Batch calculation failed for '{segmentName}': {e}")
                errors.append(f"{segmentName}: {e}")
            self.batchProgressBar.value = index + 1
            slicer.app.processEvents()

        self.batchProgressBar.visible = False
        if errors:
            self.statusLabel.text = f"Batch finished with {len(errors)} error(s). See details below."
            slicer.util.warningDisplay("Some segments failed:\n\n" + "\n".join(errors))
        else:
            self.statusLabel.text = f"Batch finished: {len(checked)} segment(s) processed."

    def _addResultRow(self, result):
        row = self.resultsTable.rowCount
        self.resultsTable.insertRow(row)

        def setCell(col, text):
            item = qt.QTableWidgetItem(str(text))
            self.resultsTable.setItem(row, col, item)

        def fmt(value):
            try:
                if value != value:  # NaN check without importing math here
                    return "-"
            except TypeError:
                pass
            return f"{value:.4f}"

        setCell(0, result["roi_name"])
        setCell(1, result["hemisphere"])
        setCell(2, result["voxel_count"])
        setCell(3, fmt(result['FD_full_boundary']))
        setCell(4, fmt(result['FD_full_volume']))
        setCell(5, fmt(result['FD_bbox_boundary']))
        setCell(6, fmt(result['FD_bbox_volume']))
        if result.get("hist") is not None:
            h = result["hist"]
            setCell(7, f"{h['mean']:.3f}")
            setCell(8, f"{h['std']:.3f}")
            setCell(9, f"{h['skewness']:.3f} / {h['kurtosis']:.3f}")
        else:
            setCell(7, "-")
            setCell(8, "-")
            setCell(9, "-")


#
# FractalHistogramAnalysisLogic
#

class FractalHistogramAnalysisLogic(ScriptedLoadableModuleLogic):

    def _ensureMatplotlib(self):
        try:
            import matplotlib  # noqa: F401
            return True
        except ImportError:
            if slicer.util.confirmOkCancelDisplay(
                    "Saving plots requires the 'matplotlib' Python package, which is not "
                    "installed in Slicer's Python environment yet. Install it now?"):
                slicer.util.pip_install("matplotlib")
                return True
            return False

    def run(self, segmentationNode, segmentId, segmentName, t1Node, outputDir, computeFull=True):
        """Compute fractal dimension (+ histogram if t1Node is given) for one segment.
        Returns a result dict; if outputDir is given, also appends to CSV files and
        saves PNG plots there, matching the CLI tool's output format.

        computeFull=False skips the full-image FD variants (used by batch mode for
        speed - see the note on core.compute_fractal_dimensions). The single-segment
        Calculate button always uses the default computeFull=True."""

        roi_name, hemisphere = core.parse_roi_info(segmentName)

        if t1Node is not None:
            maskArray = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId, t1Node)
        else:
            maskArray = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId)
        maskBin = maskArray > 0
        if maskBin.sum() == 0:
            raise ValueError(f"Segment '{segmentName}' has no voxels in the selected reference geometry.")

        fdResults = core.compute_fractal_dimensions(maskBin, include_full=computeFull)

        result = {
            "roi_name": roi_name,
            "hemisphere": hemisphere,
            "voxel_count": fdResults["voxel_count"],
            "FD_full_boundary": fdResults["FD_full_boundary"],
            "FD_full_volume": fdResults["FD_full_volume"],
            "FD_bbox_boundary": fdResults["FD_bbox_boundary"],
            "FD_bbox_volume": fdResults["FD_bbox_volume"],
            "hist": None,
            "plot_path": None,
        }

        histStats = None
        if t1Node is not None:
            t1Array = slicer.util.arrayFromVolume(t1Node)
            if t1Array.shape != maskBin.shape:
                raise ValueError(
                    f"Mask shape {maskBin.shape} does not match T1 shape {t1Array.shape} "
                    "even after requesting the segment in the T1's geometry - this should not "
                    "normally happen.")
            voxelValues = t1Array[maskBin]
            histStats = core.compute_histogram_stats(voxelValues)
            result["hist"] = histStats

        safeName = "".join(c if c.isalnum() or c in "._-" else "_" for c in segmentName)

        if outputDir:
            os.makedirs(outputDir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            def roundOrBlank(value):
                return "" if value != value else round(value, 4)  # NaN != NaN

            fractalCsv = os.path.join(outputDir, "fractal_results_comparison.csv")
            self._appendCsv(fractalCsv,
                             ["timestamp", "file_name", "roi_name", "hemisphere", "voxel_count",
                              "FD_full_boundary", "FD_full_volume", "FD_bbox_boundary", "FD_bbox_volume"],
                             [timestamp, segmentName, roi_name, hemisphere, fdResults["voxel_count"],
                              roundOrBlank(fdResults["FD_full_boundary"]), roundOrBlank(fdResults["FD_full_volume"]),
                              roundOrBlank(fdResults["FD_bbox_boundary"]), roundOrBlank(fdResults["FD_bbox_volume"])])

            if self._ensureMatplotlib():
                plotPath = os.path.join(outputDir, f"{safeName}_fractal_compare.png")
                core.save_comparison_plot(fdResults, plotPath, f"{roi_name} ({hemisphere}) - {segmentName}")
                result["plot_path"] = plotPath

            if histStats is not None:
                histCsv = os.path.join(outputDir, "roi_histogram_stats.csv")
                self._appendCsv(histCsv,
                                 ["timestamp", "file_name", "roi_name", "hemisphere", "voxel_count",
                                  "mean", "std", "min", "max", "skewness", "kurtosis"],
                                 [timestamp, segmentName, roi_name, hemisphere, histStats["voxel_count"],
                                  round(histStats["mean"], 2), round(histStats["std"], 2),
                                  round(histStats["min"], 2), round(histStats["max"], 2),
                                  round(histStats["skewness"], 3), round(histStats["kurtosis"], 3)])
                if self._ensureMatplotlib():
                    histPlotPath = os.path.join(outputDir, f"{safeName}_hist.png")
                    core.save_histogram_plot(voxelValues, histPlotPath, f"{roi_name} ({hemisphere}) histogram")
                    if result["plot_path"] is None:
                        result["plot_path"] = histPlotPath

        return result

    @staticmethod
    def _appendCsv(path, header, row):
        fileExists = os.path.isfile(path)
        with open(path, "a", newline="") as f:
            writer = csv.writer(f)
            if not fileExists:
                writer.writerow(header)
            writer.writerow(row)


#
# FractalHistogramAnalysisTest
#

class FractalHistogramAnalysisTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear()

    def runTest(self):
        self.setUp()
        self.test_FractalHistogramAnalysisCore()

    def test_FractalHistogramAnalysisCore(self):
        """Sanity-checks the pure-numpy core logic (no Slicer scene needed)
        with a synthetic spherical mask, mirroring the CLI tool's own tests."""
        self.delayDisplay("Starting core logic test")
        import numpy as np

        shape = (80, 120, 100)
        zz, yy, xx = np.ogrid[:shape[0], :shape[1], :shape[2]]
        sphere = (zz - 40) ** 2 + (yy - 60) ** 2 + (xx - 50) ** 2 <= 8 * 8

        result = core.compute_fractal_dimensions(sphere)
        self.assertGreater(result["voxel_count"], 0)
        self.assertTrue(1.0 < result["FD_bbox_volume"] < 3.0)

        name, hemi = core.parse_roi_info("right_amygdala.nii")
        self.assertEqual(name, "Amygdala")
        self.assertEqual(hemi, "Right")

        self.delayDisplay("Test passed")
