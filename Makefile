.PHONY: test test-py test-node lint install

install:
	cd scripts/py && python3 -m pip install -e ".[dev]"

test: test-py

test-py:
	python3 -m pytest tests -v

lint:
	python3 -m ruff check scripts/py

audit:
	python3 -m omnirank.cli audit $(URL)
