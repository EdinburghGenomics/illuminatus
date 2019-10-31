# Illuminatus!

The all-knowing, all-seeing, enlightened pipeline for Illumina run processing.

Runs bcl2fastq, various QC steps, unassigned barcode analysis and MultiQC reporting.
Error conditions are handled robustly and reported to RT.

The manual is maintained as a Google Doc. We do not (yet) have a manual that
is ready for public consumption but are very happy to talk about the system and
share documentation if you think you would like to use the pipeline. Porting
something like this to work in another organisation is never going to be trivial,
but the code is fairly modular once you get a handle on it.
[Ask Tim!](mailto:tim.booth@ed.ac.uk)

Design info is here (internal page):
https://www.wiki.ed.ac.uk/display/GenePool/QC+Workflow+Project

Changelog and features are here (also an internal page):
https://www.wiki.ed.ac.uk/display/GenePool/Illuminatus+feature+requests

See the doc/ directory for miscellaneous notes on various aspects of the system.
