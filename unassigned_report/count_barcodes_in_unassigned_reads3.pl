#!/usr/bin/perl

# =========================================================================================================
# Script to count the barcodes found in the unassigned reads file, and try to classify them into known
# barcodes.
# See count_barcodes_notes.txt for notes on latest updates and LIMS fixes.

# Usage:  count_barcodes_in_unassigned_reads.pl ...

# Last updated: March 2017

# The Illumina Casava 1.8+ fastq format is:
#
#  @9L6V3M1:265:C06M9ACXX:5:1101:1387:1954 2:N:0:TAAGCGTT
#  GTGCAAACGAGCTTTGTTTTCCGCGTGCTCCGGAATCCTGCCTCCTTCAGCTCAGTCTCCGTTCCTCTGTTCAGGTCGATTCTCGCACCTAACTCCACCAT
#  +
#  @@@FDFDDHHFDFIHIFHGIJJ?HHF?DFDHBDHIIIC9FHDCGGGGEHIEEHHHHHFE?D?CCEA;@C>C>A:@:@@BBDDDDDDDD@ACDDDCCD<??:
#  @9L6V3M1:265:C06M9ACXX:5:1101:1351:1959 2:N:0:TAAGCGTT
#  GGAAAACTCTGGAGCTCTTGTCAAAAATTTTGGCCCTCCTATGATAATCACTAGCCTCTTTCCCTTCATCTTCCCCCATGATTGCTTCTCTTTCCAAACAC
#  +
#  ...etc

# But the older version of casava (used by Oxford) outputs header format:  @WTCHG_35989_0:7:1101:1743:2218#TAGCAAGA/1
# We no longer need to be compatible with this.

# =========================================================================================================

use strict;
use warnings;
use Getopt::Long;
use Data::Dumper;
use FindBin qw($RealBin);

my ($infile,$outfile)=('-','-'); # To default to StdIn, and StdOut
# my $indexLength=8; # Defaults to 8 bases, ie. Sanger indexes.
my $default_cutoff=1000;
my $cutoff;
my $collusion;
my $num_to_output;  # To only output the first $num_to_output barcodes.
my $sortBy='Count'; # Alternatively by 'Count'
my $show_help;
my $numReadsInLane; # To add the percent of num reads in lane - this is run separately.
my $extractBarcode;
my $findsamplesheetbarcodenames;
my ($completedfile,$reportfile);
my $noprogress;
my $hiSeqRunX;
my $showbarcodes;
my $hiSeqRun4000;
my $loadbcfrom;
my $savebcto;
my ($knownonly,$wiki,$xmlwiki,$flagtablestart); # To output wiki table markup. or flag start of table.
my $commify_qc_results=1;
# List of barcodes embedded in the code is problematic but use of LIMS should kill it off!
my $barcodes_config_file = "$RealBin/Barcodes.config";

# Save the whole command line we need it later.
my $cmdline = "$0 " . join(' ', @ARGV);

#my $infile="/scratch/111128_SN182_0265_AC06M9ACXX/Unaligned_SampleSheet_111128_all_lanes_lanes12345678_readlen101_index8/myDummyTestFile_head100000lines.fastq";
#my $infile="/scratch/111128_SN182_0265_AC06M9ACXX/Unaligned_SampleSheet_111128_all_lanes_lanes12345678_readlen101_index8/111128_0265_AC06M9ACXX_1_unassigned_2.sanfastq.gz"

sub show_syntax
{
  warn "
  Script to count numbers of each barcode in the unassigned reads fastq file.

  Usage:  [ -in reads.fastq ] [ -cutoff 10 ] [ -sortBy Count|Name ]  [ -out results.txt ]

  Where:
     -in  Reads.fastq      : If no input file is specified, or '-' is given for the input file, then reads from stdIn.
  or -in  Reads.fastq.gz   : If input file is compressed archive, this script will itself open a pipe from 'gunzip -c' (or you can use: 'gzip -cd file.fastq.gz | count_barcodes_in_unassigned_reads2.pl')

     -addnumlanepercent TotalNumReadsInlane : To later add percentages of num reads in lane after all fastq files in lane have been processed. Needs infile which is the previously output barcode count, (NOT the fastq file). Will write new file to STDERR.

     -fromtabs             : Used when the input file to the above '-addnumlanepercent' is in tab-deliminated format.

     -cutoff  Num          : Don't report counts less than this value (Default: $default_cutoff)

     -collusions BarcodeName or BarcodeSequence : To find barcode collusions with known 6 or 8 bases barcodes, allowing upto two bases mismatach (ie. one mutation in input sequence and one mutation on known sequence).

     -extract  BarcodeName : To extract read that match this barcode to file specified by '-out Filename' parameter (if specify 'ALL' then will output all barcodes in separate files). You can use eiter a known barcode name, eg: 'SA-PE-020' or the barcode sequence, eg: 'ATCGTGTAG'.

     -findsamplesheetbarcodenames SampleSheet.csv : To find barcode names for the barcodes for Roslin sample sheets that are missing barcode names.

     -numtooutput Num      : Number of barcodes to output in each table.

     -out  Results.txt     : Output file for the reads extracted. (Defaults to format: BarcodeName_from_Readsfilename.fastq)
  or -out Results.fastq.gz : to output to compressed gzip file(s).

     -sortBy Count or Name : To sort the output by Barcode name, or by Count. (Default: '$sortBy')

     -knownonly            : To output only the known barcodes.

     -wiki                 : To output table as wiki markup.

     -flagtablestart       : To output a flag indicating the start of the wiki table, with '#TABLE_START'

     -noprogress           : To NOT output progress while reading through input fastq file.

     -nocommas             : To NOT put commas after thousands position in the output counts.

     -reportfile FILENAME  : File to write the barcode summary report to, otherwise writes it to stderr.

     -showbarcodes        : To print the barcodes known by the script on screen - for transferring to database for future instead of having barcode sequences in this script.


   To count the numbers of barcodes (the default cutoff is $default_cutoff)

      count_barcodes_in_unassigned_reads3.pl -in  121009_0002_000000000-A1WWT_1_unassigned_1.sanfastq.gz  -reportfile 121009_0002_000000000-A1WWT_1_unassigned_1.barcode_report.txt

   To extract one reads with one specific barcode (this can be used to extract 6 base barcodes by ignoring the final 2 bases of 8 base barcodes):

      count_barcodes_in_unassigned_reads3.pl -in  121009_0002_000000000-A1WWT_1_unassigned_1.sanfastq.gz -out SA-PE-001_barcode.fastq.gz  -extract SA-PE-001


   To extract ALL barcodes that have more than '-cutoff' reads, to several files, which will have the suffix specified by '-out', use, eg:

      count_barcodes_in_unassigned_reads3.pl  -in UnassignedReadsLane1Read1.sanfastq.gz  -cutoff 1000  -extract ALL

 which would produce files:
      SA-PE-008_from_UnassignedReadsLane1Read1.fastq.gz
      SA-PE-010_from_UnassignedReadsLane1Read1.fastq.gz
      SA-PE-012_from_UnassignedReadsLane1Read1.fastq.gz
      etc....
";
# [ -length 6 ]
#    -length Num      : Index length. Is either 6 for Illumina or 8 for Sanger indexes. (Default: $indexLength)
}

sub reverseComplement {
  # Is partly based on: http://www.perlmonks.org/?node_id=197793
  # Note that for codes BDHV which reverse to become ACGT, then reversing again will give TGCA, not BDHV.
  # IUPAC codes: tr /RYSWKMBDHV/YRWSMKACGT/
  # R (=A/G); reverse = Y
  # Y (=C/T); reverse = R
  # S (=G/C); reverse = W
  # W (=A/T); reverse = S
  # K (=G/T); reverse = M
  # M (=A/C); reverse = K
  # B (=C/G/T); reverse = A
  # D (=A/G/T); reverse = C
  # H (=A/C/T); reverse = G
  # V (=A/C/G); reverse = T
  # Also added U/u -> A/a for RNA sequences.

  my ($seq)=@_;
  # Note that needed to escape the '-' inside the [] as otherwise is a range:
  if ($seq=~/([^ACGTUacgtuRYSWKMBDHVNn.\-]+)/) {&dieLog("Error: Input sequence must only contain 'ACGTUacgtuRYSWKMBDHVNn.-', but found '$1'\n");}
  my $revComp = reverse $seq;
  # The Perl translate/transliterate command is just what we need:
  $revComp =~ tr/ACGTUacgtuRYSWKMBDHV/TGCAAtgcaaYRWSMKACGT/;
  return $revComp;
}

my $nocommas_flag;

GetOptions
(
  "addnumlanepercent=i" => \$numReadsInLane, # To later add the percentage of number of reads in the whole lane.
  "completed=s" => \$completedfile,  # To flag to the calling program (eg. 'illuminapipe.pl') that this script has finished, as this is called inside 'tee' which completes before this script finishes
  "cutoff=i"     => \$cutoff,  # Don't report counts less than this value.
  "collusions=s"  => \$collusion, # Barcode collusion.
  "extractbarcode=s" => \$extractBarcode,
  "findsamplesheetbarcodenames=s" => \$findsamplesheetbarcodenames,
  "flagtablestart" => \$flagtablestart,
  "numtooutput=i"=> \$num_to_output, # Number of barcodes to output in each table summary.
  "knownonly"    =>\$knownonly, # To output only the known barcodes,
#  "lanetotal=i"  =>\$lane_total, # To compute the extra column if the total reads for the lane is known - no do this separately at the end.
  "help"         => \$show_help,
  "in=s"         => \$infile,  # Input fastq file. If not given then assumes stdin. If compressed archive, then pipe from 'gzip -cd file.fastq.gz | .... '
  "out=s"        => \$outfile,
  "nocommas"     => \$nocommas_flag,
  "hiSeqRunX"     => \$hiSeqRunX,
  "hiSeqRun4000"     => \$hiSeqRun4000,
  "noprogress"   => \$noprogress,
  "reportfile=s" => \$reportfile, # File to write the barcode report to, otherwise writes it to stderr.
  "showbarcodes" => \$showbarcodes,
  "sortby=s"     => \$sortBy, # To sort the output by Barcode name, or by Count. (Default is by Barcode Name)
  "wiki"         => \$wiki,   # To output a table as wiki markup
  "xmlwiki"      => \$xmlwiki, # To output table in XML format for the new Confluence 5 wiki
  "loadbc=s"     => \$loadbcfrom, # To load the barocde list from a file (Perl format as made by -savebc)
  "savebc=s"     => \$savebcto    # To save the list of barcodes to a file (- for stdout) (Perl format with Data::Dumper)
);
#  "length=i"     => \$indexLength, # Index length. Is either 6 for Illumina or 8 for Sanger indexes.

if ($#ARGV>=0) {die "\nUnknown options given: @ARGV\n\n";}
if (defined $show_help) {&show_syntax(); die "\n";}
if ($sortBy!~/^(Count|Name)$/i) {die "Invalid -sortBy '$sortBy'. Use Name or Count\n";}
if (defined $nocommas_flag) {$commify_qc_results=0;}

if ((defined $extractBarcode) and ($extractBarcode eq 'ALL')) {if (!defined $cutoff) {die "\nFor extract 'ALL' please define a cutoff, eg: -cutoff 10000\n\n";}}
elsif (!defined $cutoff) {$cutoff=$default_cutoff;}
my $minimun_unknown_barcode_count=$cutoff;  # Could set this to a different value if preferred, eg. adding an -unknown_cutoff parameter.

my ($Lh,$Mh,$Rh, $L,$M,$R, $B,$Bend, $H5,$H5end, $table,$tableend)=("","\t","", "","\t","", "","", "h5.","", "",""); # No longer using including the new-line in the $Rh and $R

my ($Lhin,$Mhin,$Rhin, $Lin,$Min,$Rin, $Bin,$Bendin, $H5in,$H5endin, $tablein,$tableendin) = ("","\t","", "","\t","", "","", "h5.","", "","");

if (defined $wiki and defined $xmlwiki) {die "count_barcodes_in_unassigned_reads3.pl(): Both '-wiki' and '-xmlwiki' options were specified on the command-line, but you should choose only one.";}

if    (defined $wiki)    {
    ($Lh,$Mh,$Rh, $L,$M,$R, $B,$Bend, $H5,$H5end, $table,$tableend)=(
    "|| "," || "," ||", "| "," | "," |", "*","*","h5.","","","");
} # For wiki table markup.
elsif (defined $xmlwiki) {
    ($Lh,$Mh,$Rh, $L,$M,$R, $B,$Bend, $H5,$H5end, $table,$tableend)=(
    "<thead><tr><th> "," </th><th> "," </th></tr></thead>\n", "<tr><td> "," </td><td> ",
    " </td></tr>", "<b>","</b>", "<h5>","</h5>\n",
    "<div class='container'><table class='display' cellspacing='0' width='100%'>\n", "</tbody></table></div>\n");}

# Using variables for text, so that can add the percentages of total number of reads later.
my $totalNumberOfUnassignedReadsText="Total number of unassigned reads=";
# above was: my $totalNumberOfUnassignedReadsText="${B}Total number of unassigned reads=";

# regexp='/\s**Total number of unassigned reads=([0-9,]+)\s*$/' line=''
# Nested quantifiers in regex; marked by <-- HERE in m/\s** <-- HERE Total number of unassigned reads=([0-9,]+)\s*$/ at /ifs/software/linux_x86_64/Illumina_pipeline_scripts/software_dependencies/Illumina_pipeline_scripts/count_barcodes_in_unassigned_reads3.pl line 542, <$IN> line 1.
# WAS: my $totalNumberOfUnassignedReadsTextRegExp="\\s*$totalNumberOfUnassignedReadsText([0-9,]+)\\s*\$"; 
# BUT the ${B} can be a '*' when in wiki format giving the double '**', so just not starting with \\s* now:
my $totalNumberOfUnassignedReadsTextRegExp="$totalNumberOfUnassignedReadsText([0-9,]+)"; # RegExp to extract this unassigned read count, which includes commas.

# As added: " of Unassigned reads" then initially need a reg-exp when adding extra columns:
#my $knownTableHeadeRegExp="${Lh}Barcode${Mh}Sequence${Mh}Count${Mh}Percentage( of Unassigned reads)?${Rh}"; # This was originally just Percentage${Rh}
#my $unknownBarcodesTableHeaderRegExp ="${Lh}Sequence${Mh}Count${Mh}Percentage( of Unassigned reads)?${Rh}";  # Is same header for 6-base and for 8-bases

my $knownTableHeader="${table}${Lh}Barcode${Mh}Sequence${Mh}Count${Mh}Percentage of Unassigned reads"; # This was originally just Percentage${Rh}
my $unknownBarcodesTableHeader ="${table}${Lh}Sequence${Mh}Count${Mh}Percentage of Unassigned reads";  # Is same header for 6-base and for 8-bases
# if (defined $numReadsInLane) {$knownTableHeader.=$Mh; $unknownBarcodesTableHeader.=$Mh;} # So can append the $additionalColumn column.
# else {$knownTableHeader.=$Rh; $unknownBarcodesTableHeader.=$Rh;}
my $dualIndexsAdditionalColumns="Dual Index 1${Mh}Dual index 2";
my $additionalColumn="Percentage of Total reads in the Lane";

if (defined $numReadsInLane) # As this doesn't need to do any barcode counting so is quick.
{
  my $result=&add_percentage_of_reads_in_lane($infile,$numReadsInLane,$reportfile);
  if (!defined $noprogress) {print STDERR "\nFinished\n";}
  exit $result;
}


# Original comment...
# This list if barcodes is from Tim's script: /ifs/software/linux_x86_64/Illumina_pipeline_scripts/software_dependencies/pipeline_tools_python/pipeline_tools_python_trunk/sbin/get_sample_sheet_from_wiki.py
# Added TruSeq barcodes IL-TP-001 to IL-TP-048 below. Stephen, 12-jan-2012. (Originally used 'ILL-AD' to match wiki for that run. Stephen, 22-Dec-2011):
#   Originally 'ILL-AD-...' was used on wiki page, but aggreed at Solexa meeting to use 'IL-TP-' prefix for 'Illumina-TruseqPairedend-'.
#   TruSeq DNA and RNA libraries use indexes 1-12.
#   TruSeq Small RNA libraries use indexes 1-48.
# Note 'IL-PE-003' same as PhiX below:

# New comment for Illuminatus...
# We'll make a hybrid dict of barocdes from the static file and the LIMS, and maybe
# dump it or load it depending on the options set for -loadbc and -savebc.
my (%barcode_hash,%Dual_P7,%Dual_P5,%Dual_RAND,%Dual_TM_P5);
if($loadbcfrom){
    open(my $BCDUMP, '<', $loadbcfrom) or die $!;
    eval(join('', <$BCDUMP>));
    close $BCDUMP;
}
else{
    &read_barcodes();
    &read_barcodes_from_clarity_lims_database(0, defined $hiSeqRun4000, defined $hiSeqRunX);
}

if($savebcto){
    my $DH;
    if($savebcto ne '-'){
        open($DH, '>', $savebcto) or die $!;
        print $DH "## Saved out by\n## $cmdline\n"
    }
    else{
        $DH = \*STDOUT;
    }
    my $d = Data::Dumper->new([ \%barcode_hash,\%Dual_P7,\%Dual_P5,\%Dual_RAND,\%Dual_TM_P5],
                              [qw(*barcode_hash *Dual_P7  *Dual_P5  *Dual_RAND  *Dual_TM_P5)]);
    $d->Sortkeys(1);
    print $DH $d->Dump();
    close $DH;
    exit(0);
}
# End of new load/save logic.

sub read_barcodes {

  open my $IN, '<', $barcodes_config_file or die "Failed to open Barcodes file : '$barcodes_config_file' : $!";

  my $type;
  while (defined(my $line=<$IN>))
  {
    if ($line=~/^\s*$/) {next;}
    elsif ($line=~/\[(.+)\]/) {$type=$1;}
    else
    {
        chomp $line;
        my ($name,$seq,$altName)=split(/\s+/,$line); # The alternate name is optional and is typically the original name from manufacturer. eg: N701
        if (!defined $seq) {die "Unexpected line: $line";}

        if (defined $hiSeqRunX) { ## hiseqX only considers index1, no dual indexes
          $barcode_hash{$name}=$seq;
        }
        else{
          if    ($type=~/^Dual_End_TM-P5/) {$Dual_TM_P5{$name}=$seq;} # Not using these 'Dual_TM_P5' in the search below at present.
          elsif ($type=~/^RA-ND-/) {$Dual_RAND{$name}=$seq;} # Not using this 'RA-ND-' in the search below, as is just: NNNNNNNNNNNN.
          elsif ($type=~/^Dual_Start/) {$Dual_P7{$name}=$seq;}
          elsif ($type=~/^Dual_End/) {
            if (defined $hiSeqRun4000) { ## hiseq4000 the second index is reverse complemented -> need to rc to original
              $Dual_P5{$name}=&reverseComplement($seq);
            }
            else{
              $Dual_P5{$name}=$seq;
            }
          }
          else {
              $barcode_hash{$name}=$seq;
          }  # So assuming single-ended otherwise.
        }
    }
  }
  close $IN;
  # print "\n\nSingle barcodes:\n";     for my $key (sort keys %barcode_hash) {print "$key=>$barcode_hash{$key}\n";}
  # print "\n\nDual P7 barcodes:\n";    for my $key (sort keys %Dual_P7) {print "$key=>$Dual_P7{$key}\n";}
  # print "\n\nDual P5 barcodes:\n";    for my $key (sort keys %Dual_P5) {print "$key=>$Dual_P5{$key}\n";}
  # print "\n\nDual TM-P5 barcodes:\n"; for my $key (sort keys %Dual_TM_P5) {print "$key=>$Dual_TM_P5{$key}\n";}
  # print "\n\nDual RA-ND barcodes:\n"; for my $key (sort keys %Dual_RAND) {print "$key=>$Dual_RAND{$key}\n";} 
}

sub read_barcodes_from_clarity_lims_database
{
    require DBI; DBI->import();
    require DBD::Pg;
    # Tries to get a list of barcodes from the LIMS, and add them to
    # the barcode hash.
    # If the database connection fails we'll print a warning and carry on regardless.
    #   params: overwrite (default True) - replace barcodes found in the hash (not yet implemented)
    #           revcomp (default False) - reverse complement the second code (!)
    #           onlyP7 (default False) - ignore P5 codes and treat P7 as single (!)
    my ($overwrite, $revcomp, $onlyP7) = @_;
    $overwrite = 1 if !defined($overwrite);
    $revcomp   = 0 if !defined($revcomp);
    $onlyP7    = 0 if !defined($onlyP7);

    # This is a bit of a pain. Because the hashes are in the name->seq format we need to reverse
    # them to be able to detect duplicate sequences. In the first cut I'll just add everything
    # but this might clutter the report.
    #my %rev_barcode_hash; push @{ $rev_barcode_hash{ $barcode_hash{$_} } }, $_ for keys %barcode_hash;
    #my %rev_Dual_P7;      push @{ $rev_Dual_P7{      $Dual_P7{$_} } }, $_      for keys %Dual_P7;
    #my %rev_Dual_P5;      push @{ $rev_Dual_P5{      $Dual_P5{$_} } }, $_      for keys %Dual_P5;

    my $bc_data = [];
    eval{
        #Connectez au database
        my $dbh = DBI->connect('dbi:Pg:host=db2;dbname=clarityDB', 'clarityRO', '',
                               {AutoCommit=>1, RaiseError=>1});

        #Fetchez les barcodes. This relies on the codes being embedded in the labels which
        #is simple but a little hacky.
        $bc_data = $dbh->selectall_arrayref(
            "SELECT DISTINCT ON (barcode)
                    rl.name,
                    substring(rl.name FROM '.*\\((.*)\\)') as barcode
             FROM reagentlabel rl
             WHERE name LIKE '%(%)'
             AND lastmodifieddate > 'today'::date - interval '1 year'
             ORDER BY barcode, lastmodifieddate DESC;");
    } or return 0;

    my(%p5_seen, %p7_seen);

    foreach my $bc (@$bc_data){
        #print("$bc->[0] -> $bc->[1]\n");
        my($bc_label, $bc_code) = @$bc;

        #If there is a hyphen in the code we need to split it and play silly buggers.
        if($bc_code =~ /(.+)-(.+)/) {
            my($p7, $p5) = ($1,$2);

            if(! $p7_seen{$p7}){
                $p7_seen{$p7} = 1;
                if($onlyP7){
                    $barcode_hash{$bc_label} = $p7;
                }
                else{
                    $Dual_P7{$bc_label} = $p7;
                }
            }

            if(!($onlyP7 || $p5_seen{$p5})){
                $p5_seen{$p5} = 1;
                $Dual_P5{$bc_label} = $revcomp ? reverseComplement($p5) : $p5;
            }
        }
        else{
            #Easier case. These will be unique already so no need for that check,
            #or revcomping or anything else.
            $barcode_hash{$bc_label} = $bc_code;
        }
    }
}

# Add these barcodes to the main barcode_hash:
foreach my $p7name (sort keys %Dual_P7)
{
  foreach my $p5name (sort keys %Dual_P5)
  {
    if (substr($p5name,0,4) ne substr($p7name,0,4)) {next;} # So only pair Nextera with NextEra, and TP-D with TP-D.  
    my $barcodeName = "$p7name-$p5name";
    if (exists $barcode_hash{$barcodeName}) {die "Nextera bar code already exists in barcode_hash: name='$barcodeName'";}
    $barcode_hash{$barcodeName} = $Dual_P7{$p7name}.$Dual_P5{$p5name};
  }
}

# Produce reverse lookup hashes:
my %reverse_Dual_P7; foreach my $key (sort keys %Dual_P7) {$reverse_Dual_P7{$Dual_P7{$key}}=$key;}
my %reverse_Dual_P5; foreach my $key (sort keys %Dual_P5) {$reverse_Dual_P5{$Dual_P5{$key}}=$key;}

# foreach my $key (sort keys %barcode_hash) {print "                  '$barcode_hash{$key}'=>'$key',\n";}
my %reverse_barcode_hash;
if (!defined $noprogress) {print STDERR "\nNote: barcodes 'IL-TP-001' to 'IL-TP-012' have same barcode sequence as 'IL-PE-001' to 'IL-PE-012', and 'phix' is 'IL-PE-003'\n\n";}
foreach my $key (sort keys %barcode_hash)
{
  if (exists $reverse_barcode_hash{$barcode_hash{$key}})
  {
    if ($key eq 'phix') {next;}
    $reverse_barcode_hash{$barcode_hash{$key}}.=",$key"; # To append other names with a comma between them.
    if (($key=~/^IL-TP-0(\d\d)$/) and ($1<=12)) {next;}
    if (!defined $noprogress) {print STDERR "Barcode key='$key' is already used by key='$reverse_barcode_hash{$barcode_hash{$key}}', for sequence='$barcode_hash{$key}'\n";}
  }
  else {$reverse_barcode_hash{$barcode_hash{$key}}=$key;}
}

my $unknown_barcode_text='Unknown';
my (%barcodes_count, %unknown_barcodes_count); # To use the sequence as the hash key.
my ($print_reads_processed,$count_step)=(0,1000); # To update progress reading input file.

  # For HiSeq and MiSeq reads from Casava version 1.8.2. But note that the control number can be several digits, eg 4 digits (4870, but from the casava manual it should be even):  @HISEQ1:388:D19MLACXX:5:1101:7793:8599 1:N:4870:CCGTTC
  # Use single quotes around these regexp's otherwise need to escape @, \, etc:
  # Eg: HiSeq       @9L6V3M1:265:C06M9ACXX:5:1101:1387:1954 2:N:0:TAAGCGTT
  # Eg GaII:        @HWI-ST427:150:D0BP3ACXX:7:1101:1317:2491 1:N:0:NNNNNNNN
  # Eg run 130711:  @DHKW5DQ1:310:D27L0ACXX:3:1101:1383:2029 1:N:0:NNNNNNNNNNNGGNNNNNN    So need to increase regexp to 19 bases.
my $casava182Regex='@[A-Za-z0-9\-]+:\d+:[A-Za-z0-9\-]+:\d+:\d+:\d+:\d+ \d:[NY]:\d+:([ACGTN\+]{6,30})\s+';  # The [ACGTN\+]{6,12} is for index sequences: Illumina 6-base indexes, 8-base Sanger indexes, 16 base Nextra indexes (8+8).


if (defined $findsamplesheetbarcodenames) {
    find_samplesheet_barcode_names($findsamplesheetbarcodenames);
}
elsif (defined $collusion) {
    find_barcode_collusions_upto_two_mismatches($collusion);
}
elsif (defined $showbarcodes) {
    show_known_barcodes();
}
elsif ((!defined $extractBarcode) or ($extractBarcode eq 'ALL'))
{
  my $total=&count_barcodes($infile); &print_counts($total,$cutoff,$num_to_output,$reportfile);
  # This uses the values in the '%barcodes_count' hash from '&count_barcodes()'.
  if ((defined $extractBarcode) and ($extractBarcode eq 'ALL')) {&extract_all_barcodes_over_cutoff($infile,$cutoff);}
}
else
{
  if ($extractBarcode=~/,/) {&extract_several_barcodes($infile,$extractBarcode);}  # If 'barcodes' contains comma then extract several barcodes.
  else {&extract_barcode($infile,$extractBarcode);} # To extract only that one barcode
}

if (defined $completedfile) {`touch '$completedfile'`; if ($? != 0) {warn "count_barcodes_in_unassigned_reads2.pl  ** touch '$completedfile' failed **";}}

if (!defined $noprogress) {print STDERR "\nFinished\n";}


sub show_known_barcodes
{
  print "[barcode_hash]\n"; foreach my $key (sort keys %barcode_hash) {print "$key\t$barcode_hash{$key}\n";}
  print "[Dual_P7]\n";      foreach my $key (sort keys %Dual_P7)      {print "$key\t$Dual_P7{$key}\n";}
  print "[Dual_P5]\n";      foreach my $key (sort keys %Dual_P5)      {print "$key\t$Dual_P5{$key}\n";}
  print "[Dual_RAND]\n";    foreach my $key (sort keys %Dual_RAND)    {print "$key\t$Dual_RAND{$key}\n";}
  print "[Dual_TM_P5]\n";   foreach my $key (sort keys %Dual_TM_P5)   {print "$key\t$Dual_TM_P5{$key}\n";}
}


sub find_barcode_collusions_upto_two_mismatches {

  # Tests for 2 mismatches as this allows a mutation in the original and a mutation in the known barcode, which could happen when indexes are in same flowcell lane.
  # Expects either a barcode name or a barcode sequence.
  my ($original)=@_;
  my $original_seq = exists $barcode_hash{$original} ? $barcode_hash{$original} : $original;
  print STDERR "\nSearching 6 and 8 base barcodes for collusions with barcode '$original' : '$original_seq' allowing upto 2 bases mismatch (ie. 1 mutation in input barcode and 1 in known barcode)...\n";

  if ($original_seq=~/-/) {die "find_barcode_collusions_upto_one_mismatch(): Doesn't currently deal with Dual barcodes: $original_seq";}
  if ($original_seq!~/^[ACGTN]+$/) {die "find_barcode_collusions_upto_one_mismatch(): barcodes should only contain bases A,C,G,T or N";}

  my $originalLen=length($original_seq);
  my @bases=('A','C','G','T','N'); # Include 'N' in the msimatches
  my @mutated_barcodes;

  push @mutated_barcodes, $original_seq;   # 0 Mutations (ie. Original).

  # 1 Mutation:
  for (my $i=0; $i<$originalLen; $i++) # So if original barcode is 8-bases, this will change bases at positions 0,1,2,3,4,5,6,7.
  {
    my $ioriginal=substr($original_seq,$i,1);
    for my $ibase (@bases)
    {
      next if ($ibase eq $ioriginal);  # To force a mutation at this position. But might want only 2 mutations
      my $mutated= substr($original_seq,0,$i) . $ibase . substr($original_seq,$i+1); # bases up to position i, then mutated base, then remainder of the original barcode.
      push @mutated_barcodes, $mutated;
    }
  }


  # 2 Mutations:
  for (my $i=0; $i<$originalLen-1; $i++) # So will change bases at positions 0,1,2,3,4,5,6 and not touch base 7.
  {
    my $ioriginal=substr($original_seq,$i,1);
    for my $ibase (@bases)
    {
      next if ($ibase eq $ioriginal);  # To force a mutation at this position. But might want only 2 mutations
      my $iseq=substr($original_seq,0,$i).$ibase; # bases up to position i.
      my $jstart=$i+1;  # The +1 is to skip the position where $ibase has been substituted on the line above.
      for (my $j=$jstart; $j<$originalLen; $j++) # So will change bases at positions 1,2,3,4,5,6,7.
      {
        my $joriginal=substr($original_seq,$j,1);
        for my $jbase (@bases)
        {
          next if ($jbase eq $joriginal);  # To force a mutation at this position.
          my $jseq=$iseq.substr($original_seq,$jstart,$j-$jstart).$jbase;  # bases up to position j.
          my $rest=substr($original_seq,$j+1); # The remainder of the string. The +1 skips the position where $jbase has be substituted on the line above.
          my $mutated=$jseq.$rest;
          if (length($mutated) != $originalLen) {die "Lengths mismatch: mutated='$mutated', at i=$i, j=$j, iseq='$iseq', jseq='$jseq'\n";}
          push @mutated_barcodes, $mutated;
        }
      }
    }
  }

  my $num_collusions=0;
  my %collusions_found; # Use a hash to avoid repeating collusions.
  foreach my $mutated_barcode (@mutated_barcodes)
  {
    if (!defined $noprogress) {print "  Mutated to: $mutated_barcode\n";}
    my $len_mutated_barcode=length($mutated_barcode);

    for my $key (sort keys %barcode_hash)
    {
      my $known_barcode=$barcode_hash{$key};
      my $len_known_barcode=length($known_barcode);
      my $collides;
      if ( ($len_mutated_barcode==$len_known_barcode) and ($mutated_barcode eq $known_barcode) ) {$collides=1;}
      if ( ($len_mutated_barcode >$len_known_barcode) and (substr($mutated_barcode,0,$len_known_barcode) eq $known_barcode) ) {$collides=1;}
      if ( ($len_mutated_barcode <$len_known_barcode) and ($mutated_barcode eq substr($known_barcode,0,$len_mutated_barcode)) )  {$collides=1;}
      if ( (defined $collides) and (! exists $collusions_found{$key}) ) {$collusions_found{$key}=$mutated_barcode;} #Store the first collusion found.
    }

    # Also test against the first index of the dual barcodes:
    for my $key (sort keys %Dual_P7)
    {
      my $known_barcode=$Dual_P7{$key};
      my $len_known_barcode=length($known_barcode);
      my $collides;
      if ( ($len_mutated_barcode==$len_known_barcode) and ($mutated_barcode eq $known_barcode) ) {$collides=1;}
      if ( ($len_mutated_barcode >$len_known_barcode) and (substr($mutated_barcode,0,$len_known_barcode) eq $known_barcode) ) {$collides=1;}
      if ( ($len_mutated_barcode <$len_known_barcode) and ($mutated_barcode eq substr($known_barcode,0,$len_mutated_barcode)) )  {$collides=1;}
      if ( (defined $collides) and (! exists $collusions_found{$key}) ) {$collusions_found{$key}=$mutated_barcode;}
    }

  }
  foreach my $key (sort keys %collusions_found)
  {
    $num_collusions++;
    print "  collides with $key : ".(exists $barcode_hash{$key} ? $barcode_hash{$key} : $Dual_P7{$key}) ." (when $original is mutated to $collusions_found{$key})\n";
  }

  return $num_collusions;
}

sub find_samplesheet_barcode_names {

  my ($samplesheetfilename)=@_;
  if (! defined $samplesheetfilename) {die "find_samplesheet_barcode_names(): ERROR: Sample sheet name NOT defined";}

#  FCID,Lane,SampleID,SampleRef,Index,Description,Control,Recipe,Operator,SampleProject
#  H78L1ADXX,1,1180N0004_1,1180N0004_1,GCCACATA,,N,Robin Allshire#ChIP_seq#344#NT003_2#S pombe,ktroup,1180N
#  H78L1ADXX,1,1180N0004_3,1180N0004_3,GCTAACGA,,N,Robin Allshire#ChIP_seq#344#NT003_4#S pombe,ktroup,1180N
# etc...
  my ($sIndex,$sDesc)=(4,5);
  open my $IN, '<', $samplesheetfilename or die "Failed to open file: '$samplesheetfilename' : $!";
  my $headerline=<$IN>;
  if ($headerline !~ /^FCID,Lane,SampleID,SampleRef/) {
    die "Header format incorrect. Should start with 'FCID,Lane,SampleID,SampleRef', but found: '$headerline'";
  }
  my @h=split(/,/,$headerline);
  if (($h[$sIndex] ne 'Index') or ($h[$sDesc] ne 'Description')) {
    die "Expected column ".($sIndex+1)." to be 'Index', and column ".($sDesc+1)." to be 'Description', but found: '$headerline'";
  }
  print $headerline;
  while (defined(my $line=<$IN>))
  {
    chomp $line;
    my @c=split(/,/,$line);
    my $indexSeq=$c[$sIndex];
    my $indexName=$c[$sDesc];
    if ((defined $indexName) and ($indexName ne '') and ($indexName ne 'custom')) {print $line,"\n"; warn "   [Index name '$indexName' is already specified for this line]\n"; next;}
    if (!exists $reverse_barcode_hash{$indexSeq}) {print $line; warn "Barcode index name NOT found for sequence '$indexSeq' in line '$line'\n"; next}
    $c[$sDesc]=$reverse_barcode_hash{$indexSeq};
    print join(',',@c),"\n";
  }

  close $IN;
#  close $OUT;
  return 0;
}

#======================================================================================================================================================================================

sub add_percentage_of_reads_in_lane {

  my ($infile,$numReadsInLane,$reportfile)=@_;
  open my $IN, "<", $infile or die "Failed to open file: $infile : $!";
  my $REPORT;
  if (defined $reportfile) {open $REPORT, ">", $reportfile or die "Failed to open file: $reportfile : $!"; print STDERR "Writing barcode report to file: '$reportfile'\n";}
  else                     {open $REPORT, ">&STDERR" or die "Failed to open STDERR file: $!";}

#print "INFILE='$infile'\n";

  my ($isInTable,$numColsInHeader); # To indicate if is in tabbed table, where need to add rows.
  # At present this won't work for the wiki formmated output, as $Mh different from $M, (and $R no-longer includes a new-line which is chomp'ed off below, so might work with wiki)
  while (my $line=<$IN>)
  {
    chomp $line;
#print "LINE='$line'\n";

#print STDERR "regexp='/$totalNumberOfUnassignedReadsTextRegExp/' line='$line'\n";
    if ((defined $xmlwiki) and ($line=~/^#TABLE_/)) {next;} # for xml output remove '#TABLE_START' and '#TABLE_END', but keep if giving output to Tim's python wiki upload scripts.
    elsif ($line=~/$totalNumberOfUnassignedReadsTextRegExp/)
    {
      my $unassignedCount=&uncommify($1);
#      warn "A\n";
      $line.=" (".&percentage($unassignedCount,$numReadsInLane)." of the Total ".&commify($numReadsInLane)." reads in the Lane)";
#print STDERR "Found line\n";
      undef $isInTable;
    }
    elsif (($line!~/$Min.+$Min/) and ($line!~/$Mhin.+$Mhin/))  # Not in a table, as two tabs indicates a table columns. Should check for $Mh in header lines if used wiki formatting.
    {
      if (defined $isInTable)
      {
        if (defined $xmlwiki) {print $REPORT "$tableend\n";}
        undef $isInTable;
      }
      if ($line=~/^(Known Barcode counts|Unknown barcodes over|Unknown \d-base barcode sequences)/) {$line="${H5}$line${H5end}";}
    }
    else
    {
      my @c=split($Min,$line); # This $M will be a tab usually unless -wiki option was used.
      my $numCols=scalar @c; # same as $#c+1;
      if (($numCols!=3) and ($numCols!=4) and ($numCols!=5)) {die "Expected 3, 4 or 5 columns, but found $numCols columns";}  # The 5 columns is when dual indexes were used in the run.
      if (!defined $isInTable) # Is column headings line.
      {
        $isInTable=1; # As started a table now.
        # Could also check matches to the regular expressions:
        #if ($line=~$knownTableHeadeRegExp) {...}
        #if ($line=~$unknownBarcodesTableHeaderRegExp) {...}
        if ($numCols==4) {$line=$knownTableHeader.$Mh.$additionalColumn.$Rh;}
        elsif ($numCols==5) {$line=$unknownBarcodesTableHeader.$Mh.$dualIndexsAdditionalColumns.$Mh.$additionalColumn.$Rh;}
        else {$line=$unknownBarcodesTableHeader.$Mh.$additionalColumn.$Rh;}
        $numColsInHeader=$numCols;
        # Don't need to change as already correct format: if ($Mhin ne $Mh) {$line =~ s/$Mhin/$Mh/g;} # This already starts with $Lh, so don't need: $line="${Lh}$line";}
#print "Line='$line'\n";
# This isn't needed, as specifying: "$knownTableHeader.$additionalColumn" and "$unknownBarcodesTableHeader.$additionalColumn" above:  if ((defined $wiki) and ($Mhin eq "\t")) {$line=~s/\t/$Mh/g; $line=$Mh.$line;}  # As converting from tab to wiki format.
      }
      else
      {
        # For Dual indexes, the format is:
        #  GGAATCTCATAGACGC        1,735   0.01 %  (Not NX-P7 nor TP-D)    (Not NX-P5 nor TP-D)

        my $theCountColumn= ($numCols==5) ? $c[$numCols-4] : $c[$numCols-2];
        my $unassignedBarcodeCount=&uncommify($theCountColumn); # The 'Count' column.
#warn "B\n";
        my $percentageOfLane=&percentage($unassignedBarcodeCount,$numReadsInLane);
        if ($Min ne $M) {$line =~ s/$Min/$M/g; $line="${L}$line";}
        if ($numColsInHeader == $numCols+2) {$line.="${M}${M}";} # This is to align the Total percent of lane at bottom of Dual Index table
        $line.="${M}$percentageOfLane${R}"; # $R no longer includes a newline.
        if ((defined $wiki) and ($Min eq "\t")) {$line=~s/\t/$M/g; $line=$M.$line;}  # As converting from tab to wiki format.
      }
    }
    print $REPORT "$line\n" or die"Failed to write to report file : $!";
  }

  if (defined $isInTable)
  {
    if (defined $xmlwiki) {print $REPORT "$tableend\n";}
    undef $isInTable;
  }

  close $IN;
  close $REPORT;
  return 0; # Returing zero for success, as it will be the exit code used in the above calling script code.
}


#======================================================================================================================================================================================

sub count_barcodes {

  my ($infile)=@_;

  my $IN=&open_input($infile);
  if (!defined $noprogress) {print STDERR "Counting reads from input file: $infile\n";}

  my $total=0;
  while (my $line1=<$IN>)
  {
    if (substr($line1,0,1) ne '@') {die "Expected '\@' at start of fastq sequence header, but found '$line1'";}
    my $barcode;
    if    ($line1=~/^$casava182Regex$/) {$barcode=$1; $barcode =~ s/\+//;}
    else {die "Fastq header did't match expected pattern: '$line1'";}

    #print STDOUT "barcode: $barcode\n";
    my $barcodeIL; if (length($barcode)>6) {$barcodeIL=substr($barcode,0,6);}

    my $barcodeSA; if (length($barcode)>8) {$barcodeSA=substr($barcode,0,8);}

    # Is probably easier and faster to just have one barcode_count hash, then sort them out when printing at the end:
    if                               (exists $reverse_barcode_hash{$barcode})    {$barcodes_count{$barcode}++;}
    elsif ( (defined $barcodeSA) and (exists $reverse_barcode_hash{$barcodeSA})) {$barcodes_count{$barcodeSA}++;}
    elsif ( (defined $barcodeIL) and (exists $reverse_barcode_hash{$barcodeIL})) {$barcodes_count{$barcodeIL}++;}
    else                                                                         {$barcodes_count{$unknown_barcode_text}++; $unknown_barcodes_count{$barcode}++;
                                                                                  if (defined $barcodeSA) {$unknown_barcodes_count{$barcodeSA}++;}
                                                                                  if (defined $barcodeIL) {$unknown_barcodes_count{$barcodeIL}++;}
                                                                                 }

    $total++;
    if ( (!defined $noprogress) and ($total>=$print_reads_processed)) {print STDERR "\r$total"; $print_reads_processed+=$count_step;}

    my $line2=<$IN>;
    my $line3=<$IN>; if (substr($line3,0,1) ne '+') {die "Expected '+' at start of fastq quality header, but found '$line3'";}
    my $line4=<$IN>;
  }

  if (!defined $noprogress) {print STDERR "\r$total\n";}
  close $IN;
  return $total;

}


#======================================================================================================================================================================================

sub extract_all_barcodes_over_cutoff {

  # For $extractBarcode eq 'ALL'
  my ($infile,$cutoff)=@_;

  my $IN=&open_input($infile);

  if (!defined $noprogress) {print STDERR "Extracting reads for cutoff >= $cutoff\n";}

  # Open one or more output file(s):
  my %files;    # %files is for outputting for multiple barcodes
  foreach my $barcode (sort keys %barcodes_count)
  {
    if (($barcodes_count{$barcode}<$cutoff) or ($barcode eq $unknown_barcode_text)) {next;}
    my $outfilename = (exists $reverse_barcode_hash{$barcode}) ? $reverse_barcode_hash{$barcode} : $barcode;
    $outfilename=~tr/, /__/; # Replace commas and spaces with _, or case where several barcode names ue the same sequence.
    chomp(my $infilebasename=`basename $infile`);
    $outfilename.="_from_$infilebasename";
    print "  Output file=$outfilename\n";
    $files{$barcode}=&open_output($outfilename);
  }

  my ($total,$extracted_read_count)=(0,0);

  while (my $line1=<$IN>)
  {
    my $barcode;
    if (substr($line1,0,1) ne '@') {die "Expected '\@' at start of fastq sequence header, but found '$line1'";}
    if    ($line1=~/^$casava182Regex$/) {$barcode=$1;$barcode =~ s/\+//;}
    else {die "Fastq header did't match expected pattern: '$line1'";}

    my $line2=<$IN>;
    my $line3=<$IN>; if (substr($line3,0,1) ne '+') {die "Expected '+' at start of fastq quality header, but found '$line3'";}
    my $line4=<$IN>;
    $total++;
    if ( (!defined $noprogress) and ($total>=$print_reads_processed)) {print STDERR "\r$total"; $print_reads_processed+=$count_step;}

    if (exists $files{$barcode}) {my $OUT=$files{$barcode}; print $OUT $line1,$line2,$line3,$line4; $extracted_read_count++;}
    if (length($barcode)>6) {my $barcodeIL=substr($barcode,0,6); if (exists $files{$barcodeIL}) {my $OUT=$files{$barcodeIL}; print $OUT $line1,$line2,$line3,$line4; $extracted_read_count++;}}
  }
  if (!defined $noprogress) {print STDERR "\r$total\n\nExtracted $extracted_read_count reads\n\n";}

  close $IN;
  foreach my $barcode (keys %files) {close $files{$barcode};}

}


#======================================================================================================================================================================================

sub extract_barcode {

  my ($infile,$extractBarcode)=@_;
  if (! defined $extractBarcode) {die "Extract barcode NOT defined. Use: -extractbarcode BarcodeName\n";}

  my $extractBarcodeSequence = (exists $barcode_hash{$extractBarcode}) ? $barcode_hash{$extractBarcode} : $extractBarcode;
  my $barcodeLength=length($extractBarcodeSequence);

  my $IN=&open_input($infile);
  my $OUT=&open_output($outfile);

  if (!defined $noprogress) {print STDERR "Searching for barcode sequence: $extractBarcode\n";}

  my ($total,$extracted_read_count)=(0,0);

  while (my $line1=<$IN>)
  {
    if (substr($line1,0,1) ne '@') {die "Expected '\@' at start of fastq sequence header, but found '$line1'";}
    my $barcode;
    if    ($line1=~/^$casava182Regex$/) {$barcode=$1;$barcode =~ s/\+//;}
    else {die "Fastq header did't match expected pattern: '$line1'";}
    if (length($barcode)>$barcodeLength) {$barcode=substr($barcode,0,$barcodeLength);}

    my $line2=<$IN>;
    my $line3=<$IN>; if (substr($line3,0,1) ne '+') {die "Expected '+' at start of fastq quality header, but found '$line3'";}
    my $line4=<$IN>;

    if ($barcode eq $extractBarcodeSequence) {print $OUT $line1,$line2,$line3,$line4; $extracted_read_count++;}

    $total++;
    if ( (!defined $noprogress) and ($total>=$print_reads_processed)) {print STDERR "\r$total"; $print_reads_processed+=$count_step;}
  }
  if (!defined $noprogress) {print STDERR "\r$total\nExtracted $extracted_read_count reads with barcode '$extractBarcode' into file: '$outfile'\n";}

  close $IN;
  close $OUT;
}

#======================================================================================================================================================================================

# Still to finish this
sub extract_several_barcodes {

  my ($infile,$extractBarcodes)=@_; # Separate barcode names with a comma.
  if (! defined $extractBarcodes) {die "Extract barcode NOT defined. Use: -extractbarcode BarcodeName1,BasecodeName2\n";}

  my (@extractBarcodes, $barcodeLength);
  for my $extractBarcode (split(/,/,$extractBarcodes))
  {
    my $extractBarcodeSequence = (exists $barcode_hash{$extractBarcode}) ? $barcode_hash{$extractBarcode} : $extractBarcode;
    push @extractBarcodes, $extractBarcodeSequence;
    if (!defined $barcodeLength) {$barcodeLength=length($extractBarcodeSequence);}
    elsif ($barcodeLength!=length($extractBarcodeSequence)) {die "The list of barcodes should be the same length $barcodeLength, but found: '$extractBarcodeSequence'";}
  }

  my $IN=&open_input($infile);
  my $OUT=&open_output($outfile);  # Output them all into one file for now.

  if (!defined $noprogress) {print STDERR "Searching for barcode sequence: $extractBarcode\n";}

  my ($total,$extracted_read_count)=(0,0);

  while (my $line1=<$IN>)
  {
    if (substr($line1,0,1) ne '@') {die "Expected '\@' at start of fastq sequence header, but found '$line1'";}
    my $barcode;
    if    ($line1=~/^$casava182Regex$/) {$barcode=$1;$barcode =~ s/\+//;}
    else {die "Fastq header did't match expected pattern: '$line1'";}
    if (length($barcode)>$barcodeLength) {$barcode=substr($barcode,0,$barcodeLength);}

    my $line2=<$IN>;
    my $line3=<$IN>; if (substr($line3,0,1) ne '+') {die "Expected '+' at start of fastq quality header, but found '$line3'";}
    my $line4=<$IN>;

    foreach my $extractBarcodeSequence (@extractBarcodes) {if ($barcode eq $extractBarcodeSequence) {print $OUT $line1,$line2,$line3,$line4; $extracted_read_count++; last;}}

    $total++;
    if ( (!defined $noprogress) and ($total>=$print_reads_processed)) {print STDERR "\r$total"; $print_reads_processed+=$count_step;}
  }
  if (!defined $noprogress) {print STDERR "\r$total\nExtracted $extracted_read_count reads with barcode '$extractBarcode' into file: '$outfile'\n";}

  close $IN;
  close $OUT;
}


#======================================================================================================================================================================================


sub print_counts {

  my ($total,$cutoff,$num_to_output,$reportfile)=@_;

  $barcode_hash{$unknown_barcode_text}=''; # So will print Nothing for the 'Unknown_barcode' below.
  $reverse_barcode_hash{$unknown_barcode_text}="$unknown_barcode_text (See table(s) further below for details)"; # So will print Nothing for the 'Unknown_barcode' below.

  my $REPORT;
  if (defined $reportfile) {open $REPORT, ">", $reportfile or die "Failed to open file: $reportfile : $!";  print STDERR "Writing barcode report to file: '$reportfile'\n";}
  else                     {open $REPORT, ">&STDERR" or die "Failed to open STDERR file: $!";}

  print $REPORT "\n${B}$totalNumberOfUnassignedReadsText".&commify($total)."${Bend}\n";

  if ($total==0) {print $REPORT "No barcodes found to summarise\n"; return;}

  # Sort by name or count:
  my @sortedKeys;
  if    (lc $sortBy eq 'name')  {@sortedKeys=sort {$reverse_barcode_hash{$a} cmp $reverse_barcode_hash{$b}} keys %barcodes_count;}
  elsif (lc $sortBy eq 'count') {@sortedKeys=sort {$barcodes_count{$b} <=> $barcodes_count{$a}} keys %barcodes_count;}
  else {die "Invalid sortBy '$sortBy'";}

#  if (lc $sortBy ne 'name')  {@sortedKeys=sort {$reverse_barcode_hash{$a} cmp $reverse_barcode_hash{$b}} keys %barcodes_count;} # Then need to resort as was sorted by values.


  # Count the number of Known barcodes that are over 6 bases long, so only output the 8-base names for the 6-base barcodes if there are 8-base barcodes:
  my $num_known_barcodes_over_6_bases=0;
  foreach my $barcode (@sortedKeys) {if (length($barcode)>6) {$num_known_barcodes_over_6_bases++;}}
  my %is_at_start_of;
  if ($num_known_barcodes_over_6_bases>0)
    {
    foreach my $ILbarcode (@sortedKeys)
      {
      if (! exists $reverse_barcode_hash{$ILbarcode}) {warn "$ILbarcode='$ILbarcode' not found in reverse_barcode_hash"}
      if (length($ILbarcode)>6) {next;} # So only consider Illumina + phix barcodes.

      my $list='';
      foreach my $SAbarcode (@sortedKeys)
        {
        if (! exists $reverse_barcode_hash{$SAbarcode}) {warn "SAbarcode='$SAbarcode' not found in reverse_barcode_hash";}
        if (length($SAbarcode)<=6) {next;} # To only consider SA barcodes.

        if (substr($SAbarcode,0,6) eq $ILbarcode) {$list.= " $reverse_barcode_hash{$SAbarcode}($SAbarcode)";}
        }
      if ($list ne '') {$is_at_start_of{$ILbarcode}="is at start of: $list";}   # {print $REPORT "$reverse_barcode_hash{$ILbarcode} ($ILbarcode) is at start of: $list\n";}
      }
    }

  if (defined $num_to_output) {print $REPORT "\nOnly the first $num_to_output barcodes will be output in the lists below.\n\n";}

  my $limitText= (defined $num_to_output) ? "(Only the top $num_to_output are listed below, that have count greater than ".&commify($cutoff).")"
                                          : "(Only those with count greater than ".&commify($cutoff)." are listed below)";

  print $REPORT "\n${B}Known Barcode counts:${Bend}\n$limitText\n(The unknown barcode sequences are listed further below)\n";

  if (defined $flagtablestart) {print $REPORT "#TABLE_START\n";}
  print $REPORT "$knownTableHeader${Rh}\n";
  my $number_output=0;
  my ($total_above,$total_under_cutoff)=(0,0);
  foreach my $key (@sortedKeys)
  {
    if (defined $num_to_output) {if (++$number_output>$num_to_output) {$total_under_cutoff+=$barcodes_count{$key}; next;}}
    if ($barcodes_count{$key}<$cutoff) {$total_under_cutoff+=$barcodes_count{$key}; next;} # NOT using elsif... here, as both $num_to_output AND $cutoff are used to terminate the printing of the list.
    $total_above+=$barcodes_count{$key};
    my $percent = &percentage($barcodes_count{$key},$total);
    print $REPORT "${L}$reverse_barcode_hash{$key} ".(exists $is_at_start_of{$key} ? $is_at_start_of{$key} : '')."${M}$key${M}".&commify($barcodes_count{$key})."${M}$percent${R}\n";
  }
  my $percent=&percentage($total_above,$total);  print $REPORT "${L}Total of the above barcodes:${M} ${M}".&commify($total_above)."${M}$percent${R}\n";

  $percent=&percentage($total_under_cutoff,$total);
  print $REPORT "${L}Total of other barcodes with frequency under ".&commify($cutoff)." reads:${M} ${M}".&commify($total_under_cutoff)."${M}$percent${R}\n";
  print $REPORT $tableend;
  # if (defined $flagtablestart) {print $REPORT "#TABLE_END\n";}

  if (defined $knownonly) {return;} # To skip printing of the unknown barcodes.

#  print $REPORT "\n${B}Total number of unassigned reads=".&commify($total)."${Bend}\n";

  print $REPORT "\n${B}where the 'Unknown' barcodes are:${Bend}\n";



  # Count the number of barcodes that are over 6 and over 8 bases long, so only output table if needed:
  my ($num_unknown_barcodes_over_8_bases,$num_unknown_8_base_barcodes,$num_unknown_6_base_barcodes) = (0,0,0);
  foreach my $key (keys %unknown_barcodes_count)
  {
    my $len=length($key);
    if ($len>8) {$num_unknown_barcodes_over_8_bases++;}
    if ($len==8) {$num_unknown_8_base_barcodes++;}
    if ($len==6) {$num_unknown_6_base_barcodes++;}
  }

  $limitText= (defined $num_to_output) ? "(Only the top $num_to_output are listed below, that have count greater than ".&commify($minimun_unknown_barcode_count).")"
                                       : "(Only those with count greater than ".&commify($minimun_unknown_barcode_count)." are listed below)";
  # The following will be output above.
  # Output the Unknown 8 base barcode sequences.
  if ($num_unknown_barcodes_over_8_bases==0) {print $REPORT "\nNo unknown barcodes over 8-bases long were found in this file\n";}
  else
  {
    print $REPORT "\n\n${B}Unknown barcodes over 8-bases, (eg. 8+8 Nextera dual indexes) barcode sequences:${Bend}\n$limitText\n";
    if (defined $flagtablestart) {print $REPORT "#TABLE_START\n";}
    print $REPORT "$unknownBarcodesTableHeader${Mh}$dualIndexsAdditionalColumns${Rh}\n";
    $number_output=0;
    ($total_above,$total_under_cutoff)=(0,0);
    foreach my $key (sort { $unknown_barcodes_count{$b} <=> $unknown_barcodes_count{$a} } keys %unknown_barcodes_count)
    {
      if (length($key)<=8) {next;}  # As will consider the 8 base barcodes further below. 
      if (defined $num_to_output) {if (++$number_output>$num_to_output) {$total_under_cutoff+=$unknown_barcodes_count{$key}; next;}}
      if ($unknown_barcodes_count{$key} < $minimun_unknown_barcode_count) {$total_under_cutoff+=$unknown_barcodes_count{$key}; next;} # Could use 'last' here instead of 'next' as should be ordered by count, but we may want to sort by name (ie. sequence) rather than by count in future. 
      $total_above+=$unknown_barcodes_count{$key};
      my $percent=&percentage($unknown_barcodes_count{$key},$total);
      print $REPORT "${L}$key${M}".&commify($unknown_barcodes_count{$key})."${M}$percent";
      if (length($key)==16)  # For NextEra or TP-P... dual indexes.
      {
        my $key1=substr($key,0,8); if (exists $reverse_Dual_P7{$key1}) {print $REPORT "${M}$reverse_Dual_P7{$key1}";} else {print $REPORT "${M}(Not NX-P7 nor TP-D)";}
        my $key2=substr($key,8);   if (exists $reverse_Dual_P5{$key2}) {print $REPORT "${M}$reverse_Dual_P5{$key2}";} else {print $REPORT "${M}(Not NX-P5 nor TP-D)";}
      }
      print $REPORT "${R}\n";
    }
    $percent=&percentage($total_above,$total);  print $REPORT "${L}Total of the above Unknown over-8-base barcodes: ${M}".&commify($total_above)."${M}$percent${R}\n";

    $percent=&percentage($total_under_cutoff,$total);
    print $REPORT "${L}Total of other Unknown over-8-base barcodes with frequency under ".($minimun_unknown_barcode_count)." reads:${M}".&commify($total_under_cutoff)."${M}$percent${R}\n";
  }
  print $REPORT $tableend;
  # if (defined $flagtablestart) {print $REPORT "#TABLE_END\n";}

  # If the above barcodes are >8 bases, then output the Unknown 8 base barcode sequences:
  if ($num_unknown_8_base_barcodes==0) {print $REPORT "\nNo unknown 8-base barcodes were found in this file\n";}
  else
  {
    print $REPORT "\n\n${B}Unknown 8-base barcode sequences:${Bend}\n$limitText\n";
    if (defined $flagtablestart) {print $REPORT "#TABLE_START\n";}
    print $REPORT "$unknownBarcodesTableHeader${Rh}\n";
    $number_output=0;
    ($total_above,$total_under_cutoff)=(0,0);
    foreach my $key (sort { $unknown_barcodes_count{$b} <=> $unknown_barcodes_count{$a} } keys %unknown_barcodes_count)
    {
      if (length($key)!=8) {next;}  # As will only consider the 8 base barcodes here:
      if (defined $num_to_output) {if (++$number_output>$num_to_output) {$total_under_cutoff+=$unknown_barcodes_count{$key}; next;}}
      if ($unknown_barcodes_count{$key} < $minimun_unknown_barcode_count) {$total_under_cutoff+=$unknown_barcodes_count{$key}; next;} # Could use 'last' here instead of 'next' as should be ordered by count, but we may want to sort by name (ie. sequence) rather than by count in future. 
      $total_above+=$unknown_barcodes_count{$key};
      my $percent=&percentage($unknown_barcodes_count{$key},$total);
      print $REPORT "${L}$key${M}".&commify($unknown_barcodes_count{$key})."${M}$percent${R}\n";
    }
    $percent=&percentage($total_above,$total);  print $REPORT "${L}Total of the above Unknown 8-base barcodes: ${M}".&commify($total_above)."${M}$percent${R}\n";

    $percent=&percentage($total_under_cutoff,$total);
    print $REPORT "${L}Total of other Unknown 8-base barcodes with frequency under ".&commify($minimun_unknown_barcode_count)." reads:${M}".&commify($total_under_cutoff)."${M}$percent${R}\n";
    print $REPORT $tableend;
    # if (defined $flagtablestart) {print $REPORT "#TABLE_END\n";}
  }

  # Output the Unknown 6 base barcode sequences:
  if ($num_unknown_6_base_barcodes==0) {print $REPORT "\nNo unknown 6-base barcodes were found in this file\n";}
  else
  {
    print $REPORT "\n\n${B}Unknown 6-base barcode sequences:${Bend}\n$limitText\n";
    if (defined $flagtablestart) {print $REPORT "#TABLE_START\n";}
    print $REPORT "$unknownBarcodesTableHeader${Rh}\n";
    $number_output=0;
    ($total_above,$total_under_cutoff)=(0,0);
    foreach my $key (sort { $unknown_barcodes_count{$b} <=> $unknown_barcodes_count{$a} } keys %unknown_barcodes_count)
    {
      if (length($key)>6) {next;}  # As will only consider the Illumina 6 base barcodes here:
      if (defined $num_to_output) {if (++$number_output>$num_to_output) {$total_under_cutoff+=$unknown_barcodes_count{$key}; next;}}
      if ($unknown_barcodes_count{$key} < $minimun_unknown_barcode_count) {$total_under_cutoff+=$unknown_barcodes_count{$key}; next;} # Could use 'last' here instead of 'next' as should be ordered by count, but we may want to sort by name (ie. sequence) rather than by count in future. 
      $total_above+=$unknown_barcodes_count{$key};
      my $percent=&percentage($unknown_barcodes_count{$key},$total);
      print $REPORT "${L}$key${M}".&commify($unknown_barcodes_count{$key})."${M}$percent${R}\n";
    }
    $percent=&percentage($total_above,$total);  print $REPORT "${L}Total of the above Unknown 6-base barcodes: ${M}".&commify($total_above)."${M}$percent${R}\n";

    $percent=&percentage($total_under_cutoff,$total);
    print $REPORT "${L}Total of other Unknown 6-base barcodes with frequency under ".&commify($minimun_unknown_barcode_count)." reads:${M}".&commify($total_under_cutoff)."${M}$percent${R}\n";
    print $REPORT $tableend;
    # if (defined $flagtablestart) {print $REPORT "#TABLE_END\n";}
  }

#  print $REPORT "Note: SureSelect XT2 barcodes SS-PE-017 to SS-PE-096 still need to be added\n"; # Are added now.

  close $REPORT;
}


#======================================================================================================================================================================================

sub open_input {

  my ($infile)=@_;
  my $IN;
  if ($infile=~/.gz$/) {open $IN, "gunzip -c '$infile' |" or die "Failed to open pipe from the gzipped input file: '$infile' : $!";}
  else                 {open $IN, "<$infile" or die "Failed to open file: '$infile' $!";}
  return $IN;
}

#======================================================================================================================================================================================

sub open_output {

  my ($outfile)=@_;
  my $OUT;
  if ($outfile=~/.gz$/) {open $OUT, "| gzip -c > '$outfile'" or die "Failed to open pipe to the gzipped output file '$outfile' : $!";}
  else                  {open $OUT, ">$outfile" or die "Failed to open file: '$outfile' $!";}
  return $OUT;
}

#======================================================================================================================================================================================

sub commify {

  # Formats '1234567890.01' with commas as "1,234,567,890.01
  # Based on: http://www.perlmonks.org/?node_id=110137
  my ($number)=@_;
  if ($commify_qc_results!=0) {$number =~ s/(\d)(?=(\d{3})+(\D|$))/$1\,/g;}
  return $number;
}

#======================================================================================================================================================================================

sub uncommify {

  # Removes the commas from numbers
  my ($number)=@_;
  $number=~s/,//g;
  return $number;
}

#======================================================================================================================================================================================

sub percentage {
  # Checks for divide-by-zero error, before dividing. Two decimal places by default unless specify a different 'format' parameter.
  my ($numerator,$divisor,$format)=@_;
  my $percent;
  if (! defined $format) {$format='%.2f %%';}  # Note: need two '%' to display the percentage symbol.

  if    (! defined $numerator)    {warn "Unable to compute percentage as Numerator NOT defined\n";}
  elsif ($numerator!~/^[\d\.]+$/) {warn "Unable to compute percentage as Numerator is NOT numeric: '$numerator'\n";}

  if    (! defined $divisor)   {warn "Unable to compute percentage as Divisor NOT defined\n";}
  elsif (! defined $divisor)   {warn "Unable to compute percentage as Divisor is NOT numeric: '$divisor'\n";}

  if ( (defined $numerator) and (defined $divisor) )
  {
    if    ($numerator==0) {$percent='0.0 %';}  # <-- Need to catch the divide by zero error.
    elsif ($divisor==0) {$percent='Infinity';}
#    else  {$percent=sprintf($format,100*$numerator/$divisor);}  # This gave a warning message:
#    Invalid conversion in sprintf: end of string at /ifs/software/linux_x86_64/Illumina_pipeline_scripts/software_dependencies/Illumina_pipeline/illuminapipe.pl line 806.
# After running:
#   gzip --best /scratch/120126_SN182_0281_AD088PACXX/Unaligned_SampleSheet_120126_lanes12345678_readlen101_index8/120126_0281_AD088PACXX_8_1_Reads_containi$
# So using the following for now instead:
    else  {$percent=sprintf($format,100*$numerator/$divisor);} # &printLog("\npercent(): format='$format' num='$numerator' div='$divisor'\n");}
  }
  return $percent;
}


#======================================================================================================================================================================================
