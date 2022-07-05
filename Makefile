lint:
	pipenv run flake8 ses
	pipenv run black --diff -l 79 -S ses
.PHONY: lint

develop:
	pipenv install --dev
.PHONY: develop

format:
	pipenv run black -l 79 -S ses
.PHONY: format

dist:
	rm -f dist/*
	pipenv run python setup.py sdist bdist_wheel
.PHONY: dist

publish: dist
	pipenv run twine upload dist/*
.PHONY: publish
