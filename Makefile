.PHONY: gcp

# With hashes in requirements.txt, deployment to GCP fails with the following error:
#
#   In --require-hashes mode, all requirements must have their versions pinned with ==. These do not:
#       setuptools>=3.0 from ...
#
# So we disable --require-hashes mode.
gcp:
	@- $(RM) -f deploy/gcp/*.py deploy/gcp/data.csv deploy/gcp/requirements.txt
	cp app.py data.csv deploy/gcp
	rsync -avzP --delete assets deploy/gcp
	sed 's/ \\//; /--hash=/d' requirements.txt > deploy/gcp/requirements.txt
