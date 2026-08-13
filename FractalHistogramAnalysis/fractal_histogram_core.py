"""
Shared, pure-numpy analysis logic for fractal dimension (3D box-counting)
and intensity histogram statistics.

This is the SAME logic used by the standalone CLI tool
(https://github.com/niyaziacer/brain-fractal-histogram-analysis,
fractal_analysis.py / histogram_analysis.py), refactored to operate on
in-memory numpy arrays instead of reading .nii files from disk - so it can
be called directly from the Slicer scripted module on arrays obtained via
slicer.util.arrayFromSegmentBinaryLabelmap() / slicer.util.arrayFromVolume(),
with no manual "export to file, then run a separate script" step.

No Slicer imports here - this module has zero dependency on `slicer` and
can be unit-tested with plain numpy/SimpleITK outside Slicer.
"""

import math
import re

import numpy as np


def parse_roi_info(name, label_scheme=None):
    """Derive a human-readable ROI name and hemisphere from a segment/file name.

    Examples:
        caudate_L                    -> ("Caudate", "Left")
        right_amygdala                -> ("Amygdala", "Right")
        thalamus_R                    -> ("Thalamus", "Right")
        Segment_47, label_scheme="volbrain"   -> ("Hippocampus", "Right")
        Segment_75, label_scheme="openmapt1"  -> ("Hippo", "Left")

    label_scheme selects which multi-label atlas table (if any) to use for
    resolving Slicer's auto-generated "Segment_<N>" names (N = the raw
    integer label value): None (skip straight to the generic filename
    parsing below), "volbrain" (volBrain's native_structures table), or
    "openmapt1" (OpenMAP-T1's Type1 Level5 table).

    This MUST be chosen explicitly rather than auto-detected: volBrain and
    OpenMAP-T1 both produce segments named "Segment_<N>" when imported
    without a color table, but the same N means a different region in each
    scheme (e.g. N=47 is "Right Hippocampus" in volBrain but the left
    entorhinal area ("ENT_L") in OpenMAP-T1) - guessing wrong would silently
    mislabel every region.
    """
    if label_scheme == "volbrain":
        try:
            from volbrain_labels import lookup_structure_label
            match = lookup_structure_label(name)
            if match is not None:
                return match
        except ImportError:
            pass
    elif label_scheme == "openmapt1":
        try:
            from openmap_labels import lookup_structure_label
            match = lookup_structure_label(name)
            if match is not None:
                return match
        except ImportError:
            pass

    name = re.sub(r"\.nii(\.gz)?$", "", name, flags=re.IGNORECASE)
    lname = name.lower()

    if re.search(r"(^|_)r(ight)?(_|$)", lname):
        hemi = "Right"
    elif re.search(r"(^|_)l(eft)?(_|$)", lname):
        hemi = "Left"
    else:
        hemi = "Unknown"

    roi_name = re.sub(r"(^|_)(left|right|l|r)(_|$)", "_", lname, flags=re.IGNORECASE)
    roi_name = roi_name.strip("_").replace("_", " ").strip()
    roi_name = roi_name.title() if roi_name else name

    return roi_name, hemi


def crop_to_bounding_box(mask_bin, pad=1):
    """Crop a boolean 3D array to the tight bounding box of True voxels (+pad)."""
    coords = np.argwhere(mask_bin)
    if coords.size == 0:
        return mask_bin
    mins = coords.min(axis=0)
    maxs = coords.max(axis=0) + 1
    mins = np.maximum(mins - pad, 0)
    maxs = np.minimum(maxs + pad, mask_bin.shape)
    return mask_bin[mins[0]:maxs[0], mins[1]:maxs[1], mins[2]:maxs[2]]


def box_counts(mask_bin, size, mode):
    """Count occupied boxes of a given size.

    mode="volume":   count boxes containing >=1 foreground voxel.
    mode="boundary": count boxes containing BOTH foreground and background
                      voxels (i.e. the object's surface only).
    """
    count = 0
    sx, sy, sz = mask_bin.shape
    for x in range(0, sx, size):
        for y in range(0, sy, size):
            for z in range(0, sz, size):
                cube = mask_bin[x:x + size, y:y + size, z:z + size]
                has_fg = np.any(cube)
                if mode == "volume":
                    if has_fg:
                        count += 1
                else:  # boundary
                    if has_fg and np.any(~cube):
                        count += 1
    return count


def get_sizes(shape, min_points=2):
    """Powers of two (starting at 2) up to just under the smallest axis,
    guaranteeing at least `min_points` sizes so the log-log fit is defined."""
    p = int(math.log2(max(min(shape), 4)))
    p = max(p, min_points + 1)
    return 2 ** np.arange(1, p)


def fractal_dimension_3d(mask_bin, sizes, mode):
    counts = np.array([box_counts(mask_bin, int(size), mode) for size in sizes], dtype=float)
    valid = counts > 0
    if valid.sum() < 2:
        return float("nan"), sizes, counts
    coeffs = np.polyfit(np.log(1.0 / sizes[valid]), np.log(counts[valid]), 1)
    return coeffs[0], sizes, counts


def compute_fractal_dimensions(mask_bin, include_full=True):
    """Compute FD variants for a boolean 3D mask array.

    Returns a dict with FD_full_boundary, FD_full_volume, FD_bbox_boundary,
    FD_bbox_volume, and a "_plot" entry per variant with (sizes, counts) for
    plotting a log-log comparison figure. See the CLI tool's README for the
    rationale behind computing all four instead of picking one.

    include_full=False skips the full-image-sized variants (FD_full_*), which
    are set to NaN instead. This is a real performance optimization, not just
    a display toggle: box_counts() scans boxes across the FULL image shape for
    every structure regardless of how small it is, so for batch runs over many
    small segments (e.g. a multi-label "structures" segmentation with 100+
    regions) skipping it avoids doing that full-image scan once per region.
    Only the bbox variants (each scanning just that region's own bounding box)
    are computed, which is what batch mode uses.
    """
    results = {"voxel_count": int(mask_bin.sum())}

    if include_full:
        sizes_full = get_sizes(mask_bin.shape)
        for mode in ("boundary", "volume"):
            fd, sizes, counts = fractal_dimension_3d(mask_bin, sizes_full, mode)
            results[f"FD_full_{mode}"] = fd
            results[f"_plot_full_{mode}"] = (sizes, counts)
    else:
        results["FD_full_boundary"] = float("nan")
        results["FD_full_volume"] = float("nan")

    mask_cropped = crop_to_bounding_box(mask_bin, pad=1)
    sizes_bbox = get_sizes(mask_cropped.shape)
    for mode in ("boundary", "volume"):
        fd, sizes, counts = fractal_dimension_3d(mask_cropped, sizes_bbox, mode)
        results[f"FD_bbox_{mode}"] = fd
        results[f"_plot_bbox_{mode}"] = (sizes, counts)

    return results


def compute_histogram_stats(intensity_values):
    """Compute mean/std/min/max/skewness/kurtosis for a 1D array of intensities.

    Implemented without scipy (Slicer's bundled Python may not have it) using
    plain numpy moment formulas, matching scipy.stats.skew/kurtosis (Fisher,
    bias-corrected=False - i.e. the simple/"population" definitions).
    """
    values = np.asarray(intensity_values, dtype=float)
    n = values.size
    if n == 0:
        return None
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0 or n < 2:
        skewness = 0.0
        kurtosis = 0.0
    else:
        centered = values - mean
        m2 = np.mean(centered ** 2)
        m3 = np.mean(centered ** 3)
        m4 = np.mean(centered ** 4)
        skewness = float(m3 / (m2 ** 1.5)) if m2 > 0 else 0.0
        kurtosis = float(m4 / (m2 ** 2) - 3.0) if m2 > 0 else 0.0  # excess kurtosis
    return {
        "voxel_count": int(n),
        "mean": mean,
        "std": std,
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "skewness": skewness,
        "kurtosis": kurtosis,
    }


def save_comparison_plot(results, out_path, title):
    """Save the 4-variant log-log comparison plot. Imports matplotlib lazily
    so this module can be imported even before matplotlib is installed."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(7, 6))
    styles = {
        "full_boundary": ("o-", "full image / boundary (original method)"),
        "full_volume":   ("s-", "full image / volume"),
        "bbox_boundary": ("^-", "bounding box / boundary"),
        "bbox_volume":   ("d-", "bounding box / volume (recommended)"),
    }
    for key, (style, label) in styles.items():
        plot_data = results.get(f"_plot_{key}")
        if plot_data is None:
            continue  # skipped (e.g. full-image variant in batch/bbox-only mode)
        sizes, counts = plot_data
        counts = np.asarray(counts, dtype=float)
        valid = counts > 0
        if valid.sum() < 2:
            continue
        fd = results[f"FD_{key}"]
        plt.plot(np.log(1.0 / np.asarray(sizes)[valid]), np.log(counts[valid]), style,
                  label=f"{label} (FD={fd:.3f})")
    plt.xlabel("log(1 / box size)")
    plt.ylabel("log(box count)")
    plt.title(title)
    plt.legend(fontsize=8)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def save_histogram_plot(values, out_path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.figure(figsize=(8, 5))
    plt.hist(values, bins=200, color="gray", alpha=0.7)
    plt.xlabel("Intensity (gray level)")
    plt.ylabel("Voxel count")
    plt.title(title)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()
