"""
Label -> anatomical name lookup for volBrain / vol2Brain's
{native,mni}_structures_<JOB_ID>.nii.gz multi-label output.

Transcribed directly from the vol2Brain README.pdf "Label correspondence"
table (version 1.0, release 2021-04-20). Do NOT "clean up" or replace this
with an inferred odd=Right/even=Left rule: labels 75/76 (Basal Forebrain)
are a real exception in volBrain's own numbering (75=Left, 76=Right - the
reverse of every other paired structure below), so a hand-guessed rule
would silently mislabel that one pair.

Why this file exists: when a volBrain native_structures*.nii.gz multi-label
volume is imported into 3D Slicer as a Segmentation node WITHOUT a color
table, Slicer names each segment "Segment_<N>" where N is the original
integer label value (not a re-numbered index) - so we can recover the real
structure name/hemisphere straight from that name.
"""

STRUCTURE_LABELS = {
    # Label 1 is NOT listed in the vol2Brain README's structures table, but
    # it IS present in real native_structures*.nii.gz output. Identified by
    # cross-checking: voxel count for label 1 converts to ~183 cm3 (using the
    # image's own voxel spacing), which matches the "External CSF volume cm3"
    # field (~185 cm3) in that same job's report_<JOB_ID>.csv to within ~1%.
    # So this is extra-axial/sulcal CSF, not one of the specifically labeled
    # ventricles (4, 11, 49-52). Not an official README entry - flagged here
    # so it's traceable if a future volBrain version changes this.
    1: "External CSF",
    4: "3rd Ventricle",
    11: "4th Ventricle",
    23: "Right Accumbens",
    30: "Left Accumbens",
    31: "Right Amygdala",
    32: "Left Amygdala",
    35: "Brainstem",
    36: "Right Caudate",
    37: "Left Caudate",
    38: "Right Cerebellum Exterior",
    39: "Left Cerebellum Exterior",
    40: "Right Cerebellum White Matter",
    41: "Left Cerebellum White Matter",
    44: "Right Cerebral White Matter",
    45: "Left Cerebral White Matter",
    47: "Right Hippocampus",
    48: "Left Hippocampus",
    49: "Right Inf Lat Vent",
    50: "Left Inf Lat Vent",
    51: "Right Lateral Ventricle",
    52: "Left Lateral Ventricle",
    55: "Right Pallidum",
    56: "Left Pallidum",
    57: "Right Putamen",
    58: "Left Putamen",
    59: "Right Thalamus",
    60: "Left Thalamus",
    61: "Right Ventral DC",
    62: "Left Ventral DC",
    71: "Lobules I-V",
    72: "Lobules VI-VII",
    73: "Lobules VIII-X",
    75: "Left Basal Forebrain",
    76: "Right Basal Forebrain",
    100: "Right anterior cingulate gyrus",
    101: "Left anterior cingulate gyrus",
    102: "Right anterior insula",
    103: "Left anterior insula",
    104: "Right anterior orbital gyrus",
    105: "Left anterior orbital gyrus",
    106: "Right angular gyrus",
    107: "Left angular gyrus",
    108: "Right calcarine cortex",
    109: "Left calcarine cortex",
    112: "Right central operculum",
    113: "Left central operculum",
    114: "Right cuneus",
    115: "Left cuneus",
    116: "Right entorhinal area",
    117: "Left entorhinal area",
    118: "Right frontal operculum",
    119: "Left frontal operculum",
    120: "Right frontal pole",
    121: "Left frontal pole",
    122: "Right fusiform gyrus",
    123: "Left fusiform gyrus",
    124: "Right gyrus rectus",
    125: "Left gyrus rectus",
    128: "Right inf. occipital gyrus",
    129: "Left inf. occipital gyrus",
    132: "Right inf. temporal gyrus",
    133: "Left inf. temporal gyrus",
    134: "Right lingual gyrus",
    135: "Left lingual gyrus",
    136: "Right lateral orbital gyrus",
    137: "Left lateral orbital gyrus",
    138: "Right middle cingulate gyrus",
    139: "Left middle cingulate gyrus",
    140: "Right medial frontal cortex",
    141: "Left medial frontal cortex",
    142: "Right middle frontal gyrus",
    143: "Left middle frontal gyrus",
    144: "Right middle occipital gyrus",
    145: "Left middle occipital gyrus",
    146: "Right medial orbital gyrus",
    147: "Left medial orbital gyrus",
    148: "Right postcentral gyrus medial segment",
    149: "Left postcentral gyrus medial segment",
    150: "Right precentral gyrus medial segment",
    151: "Left precentral gyrus medial segment",
    152: "Right sup. frontal gyrus medial segment",
    153: "Left sup. frontal gyrus medial segment",
    154: "Right middle temporal gyrus",
    155: "Left middle temporal gyrus",
    156: "Right occipital pole",
    157: "Left occipital pole",
    160: "Right occipital fusiform gyrus",
    161: "Left occipital fusiform gyrus",
    162: "Right opercular inf. frontal gyrus",
    163: "Left opercular inf. frontal gyrus",
    164: "Right orbital inf. frontal gyrus",
    165: "Left orbital inf. frontal gyrus",
    166: "Right posterior cingulate gyrus",
    167: "Left posterior cingulate gyrus",
    168: "Right precuneus",
    169: "Left precuneus",
    170: "Right parahippocampal gyrus",
    171: "Left parahippocampal gyrus",
    172: "Right posterior insula",
    173: "Left posterior insula",
    174: "Right parietal operculum",
    175: "Left parietal operculum",
    176: "Right postcentral gyrus",
    177: "Left postcentral gyrus",
    178: "Right posterior orbital gyrus",
    179: "Left posterior orbital gyrus",
    180: "Right planum polare",
    181: "Left planum polare",
    182: "Right precentral gyrus",
    183: "Left precentral gyrus",
    184: "Right planum temporale",
    185: "Left planum temporale",
    186: "Right subcallosal area",
    187: "Left subcallosal area",
    190: "Right sup. frontal gyrus",
    191: "Left sup. frontal gyrus",
    192: "Right supplementary motor cortex",
    193: "Left supplementary motor cortex",
    194: "Right supramarginal gyrus",
    195: "Left supramarginal gyrus",
    196: "Right sup. occipital gyrus",
    197: "Left sup. occipital gyrus",
    198: "Right sup. parietal lobule",
    199: "Left sup. parietal lobule",
    200: "Right sup. temporal gyrus",
    201: "Left sup. temporal gyrus",
    202: "Right temporal pole",
    203: "Left temporal pole",
    204: "Right triangular inf. frontal gyrus",
    205: "Left triangular inf. frontal gyrus",
    206: "Right transverse temporal gyrus",
    207: "Left transverse temporal gyrus",
}


def lookup_structure_label(segment_name):
    """If segment_name matches Slicer's default labelmap-import naming
    ("Segment_<N>", N = the original integer label value), return
    (roi_name, hemisphere) using the volBrain structures table above.

    Returns None if segment_name doesn't look like a Slicer auto-generated
    "Segment_<N>" name at all (e.g. the user renamed it, or it's from the
    old manual single-file workflow like "right_amygdala") - the caller
    should fall back to its own generic filename-based parsing in that case.

    If it DOES look like "Segment_<N>" but N isn't in the table (e.g. N=1,
    which is not a native_structures label - it may be an intracranial mask
    or a different volBrain output file), returns a clearly-flagged
    "Unmapped structure (label N)" instead of guessing, so this doesn't get
    silently confused with a real resolved name.
    """
    import re
    match = re.fullmatch(r"[Ss]egment_?(\d+)", segment_name.strip())
    if not match:
        return None
    label = int(match.group(1))
    full_name = STRUCTURE_LABELS.get(label)
    if full_name is None:
        return f"Unmapped structure (label {label})", "Unknown"
    if full_name.startswith("Right "):
        return full_name[len("Right "):], "Right"
    if full_name.startswith("Left "):
        return full_name[len("Left "):], "Left"
    return full_name, "N/A"
