cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(FractalHistogramAnalysis)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/niyaziacer/SlicerFractalHistogramAnalysis")
set(EXTENSION_CATEGORY "Quantification")
set(EXTENSION_CONTRIBUTORS "Niyazi Acer (Erciyes University, Retired)")
set(EXTENSION_DESCRIPTION "Computes the 3D box-counting fractal dimension (4 comparison variants) and intensity histogram statistics (mean, std, skewness, kurtosis) of a selected segment directly from a Segmentation node in the scene - no manual export-to-file step needed.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/niyaziacer/SlicerFractalHistogramAnalysis/main/FractalHistogramAnalysis/Resources/Icons/FractalHistogramAnalysis.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/niyaziacer/SlicerFractalHistogramAnalysis/main/Screenshots/interface.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(FractalHistogramAnalysis)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
