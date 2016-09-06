import unittest
from BaseMaskExtractor import BaseMaskExtractor

class TestUM(unittest.TestCase):

    def read_bcl2fastq_command_file(self,file):
        with open(file, 'r') as myfile:
            data = myfile.read().replace('\n', '')
	return data
    def miseq_base_mask(self,run_id):
	ss = "/ifs/runqc/" + run_id + "/SampleSheet.csv"
	ri = "/ifs/seqdata/" + run_id + "/RunInfo.xml"
	b2f = "/ifs/runqc/" + run_id + "/qmakeBclToFastqLanes1.sh"

        bme = BaseMaskExtractor(ss,ri)
        basemask = bme.get_base_mask_for_lane( "1" )
        bcl2fastq_command_string = self.read_bcl2fastq_command_file(b2f)
	#print basemask
        assert (basemask in bcl2fastq_command_string)

    def lane8_base_mask(self,run_id):
        ss = "/ifs/runqc/" + run_id + "/SampleSheet.csv"
        ri = "/ifs/seqdata/" + run_id + "/RunInfo.xml"
        b2f = "/ifs/runqc/" + run_id + "/qmakeBclToFastqLanes12345678.sh"

	rapid = False
        bme = BaseMaskExtractor(ss,ri)
	try:
	        bcl2fastq_command_string = self.read_bcl2fastq_command_file(b2f)
	except IOError:
		rapid = True
	        b2f = "/ifs/runqc/" + run_id + "/qmakeBclToFastqLanes12.sh"
                bcl2fastq_command_string = self.read_bcl2fastq_command_file(b2f)

        basemask = bme.get_base_mask_for_lane( "1" )
	#print basemask
        assert (basemask in bcl2fastq_command_string)

	basemask = bme.get_base_mask_for_lane( "2" )
	#print basemask
	assert (basemask in bcl2fastq_command_string)

	if not rapid:
		basemask = bme.get_base_mask_for_lane( "3" )
		assert (basemask in bcl2fastq_command_string)
		basemask = bme.get_base_mask_for_lane( "4" )
		assert (basemask in bcl2fastq_command_string)
		basemask = bme.get_base_mask_for_lane( "5" )
		assert (basemask in bcl2fastq_command_string)
		basemask = bme.get_base_mask_for_lane( "6" )
		assert (basemask in bcl2fastq_command_string)
		basemask = bme.get_base_mask_for_lane( "7" )
		assert (basemask in bcl2fastq_command_string)
		basemask = bme.get_base_mask_for_lane( "8" )

    def test_miseq_base_mask(self):
	test_runs = [
		"160701_M01270_0203_000000000-AMF4F",
                "160711_M01270_0206_000000000-APNCU",
                "160715_M01145_0027_000000000-AUB21",
                "160720_M01145_0029_000000000-ARUDU",
                "160726_M01270_0211_000000000-AUCCT",
                "160704_M01270_0204_000000000-APNLM",
                "160713_M01145_0025_000000000-APNLB",
                "160715_M01270_0208_000000000-ARU85",
                "160728_M01145_0032_000000000-AR4VA",
                "160707_M01145_0024_000000000-APETM",
                "160713_M01270_0207_000000000-AR4B1",
                "160718_M01270_0209_000000000-APND5",
                "160729_M01145_0033_000000000-AR1YY",
                "160707_M01270_0205_000000000-APNND",
                "160714_M01145_0026_000000000-ARUD3",
                "160719_M01145_0028_000000000-ARU7R",
                "160722_M01270_0210_000000000-AUCD1",

		"160802_M01270_0212_000000000-AR2NH",
		"160805_M01270_0215_000000000-ATKRT",
		"160811_M01270_0218_000000000-AT4YH",
		"160819_M01270_0222_000000000-ATH0E",
		"160826_M01270_0225_000000000-ATGYN",
		"160803_M01270_0213_000000000-APUY2",
		"160808_M01145_0036_000000000-ATLBC",
		"160812_M01145_0038_000000000-AT6BN",
		"160822_M01145_0039_000000000-ATNY5",
		"160804_M01145_0034_000000000-AR7AL",
		"160808_M01270_0216_000000000-ATE7V",
		"160822_M01270_0223_000000000-ATNYU",
		"160804_M01270_0214_000000000-ATCKA",
		"160810_M01270_0217_000000000-ATDJ8",
		"160816_M01270_0220_000000000-APVKN",
		"160824_M01145_0040_000000000-ATUKH",
		"160829_M01270_0226_000000000-ARGF3",
		"160805_M01145_0035_000000000-ATDYJ",
		"160811_M01145_0037_000000000-ATDJ3",
		"160824_M01270_0224_000000000-AUKD5",
		]

	for run in test_runs:
		pass
		#print run
		self.miseq_base_mask(run)

    def test_hiseq_base_mask(self):
	test_runs = [ 
		"160704_D00261_0345_AHTWVHBCXX",
		"160701_D00248_0182_AC9JB9ANXX",
		"160707_D00261_0346_AHVKLWBCXX",
		"160713_D00261_0347_AHVKMKBCXX",
		"160718_D00261_0348_BHVMNCBCXX",
		"160720_D00261_0349_AC9JA3ANXX",
		"160726_D00261_0350_AHW3FCBCXX",
		"160726_D00261_0351_BHW352BCXX",
		]
        for run in test_runs:
		pass
                print run
		self.lane8_base_mask(run)

    def test_hiseq4000_base_mask(self):
        test_runs = [
                "160701_K00368_0028_AHF7YFBBXX",
		"160701_K00368_0029_BHFH3GBBXX",
		"160704_K00166_0111_AHFGH2BBXX",
		"160704_K00166_0112_BHFGF3BBXX",
		"160705_K00368_0030_AHFGG2BBXX",
		"160705_K00368_0031_BHFGJ7BBXX",
		"160707_K00166_0113_AHFKWHBBXX",
		"160707_K00166_0114_BHFG2NBBXX",
		"160712_K00368_0032_AHFG7JBBXX",
		"160713_K00166_0116_AHFLJHBBXX",
		"160714_K00368_0033_AHFLFMBBXX",
		"160719_K00166_0117_BHCFTFBBXX",
		"160722_K00166_0118_AHFLL5BBXX",
		"160722_K00368_0035_AHFGCTBBXX",
		"160722_K00368_0036_BHFKH5BBXX",
		"160726_K00166_0119_AHCNTKBBXX",
		"160726_K00166_0120_BHCVH2BBXX",
                ]
        for run in test_runs:
                pass
                #print run
                self.lane8_base_mask(run)



if __name__ == '__main__':
    unittest.main()
