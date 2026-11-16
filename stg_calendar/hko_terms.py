"""Fallback solar terms published by the Hong Kong Observatory."""

from .pmo_terms import parse_terms

# https://www.hko.gov.hk/en/gts/astronomy/data/files/24SolarTerms_2027.xml
HKO_TERMS = parse_terms({
    2027: (
        "05 22:10 20 15:30", "04 09:46 19 05:33", "06 03:40 21 04:25",
        "05 08:17 20 15:18", "06 01:25 21 14:18", "06 05:26 21 22:11",
        "07 15:37 23 09:05", "08 01:27 23 16:14", "08 04:28 23 14:02",
        "08 20:17 23 23:33", "07 23:39 22 21:16", "07 16:38 22 10:42",
    ),
})
