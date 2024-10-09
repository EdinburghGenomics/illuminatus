# On the old cluster I decided to put Cutadapt into the VEnv, so I added
# this hook to give me a programmatic way to do it. You can add extra packages to this
# file if they want to be in the VEnv for a specific deployment.

pip_install cutadapt==1.18
