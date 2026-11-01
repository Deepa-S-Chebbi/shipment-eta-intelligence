.PHONY: all install starter full validate repro test eval dashboard clean

PYTHON ?= python

all: starter validate test

install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -r requirements-dashboard.txt

starter:
	$(PYTHON) scripts/generate.py --config config/starter.yaml --out data/starter --scale 0.01

full:
	$(PYTHON) scripts/generate.py --config config/default.yaml --out data/full --scale 1.0

validate:
	$(PYTHON) -m eta_data.validate --data data/starter

repro:
	$(PYTHON) scripts/repro_check.py --scale 0.01

test:
	$(PYTHON) -m pytest tests/ -v

eval:
	$(PYTHON) -m eta_data.evaluate --data data/starter

dashboard:
	streamlit run dashboard/app.py

clean:
	rm -rf data/full data/repro_1 data/repro_2 .pytest_cache
