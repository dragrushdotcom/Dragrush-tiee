PYTHON ?= python3
.PHONY: test functional-check
test:
	$(PYTHON) -m unittest discover -s tests -v
functional-check:
	$(PYTHON) -m benchmark --out results/local-check
