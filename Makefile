lint:
	poetry run flake8
	poetry run black --diff -l 79 -S ses
.PHONY: lint

develop:
	poetry install
.PHONY: develop

format:
	poetry run black -l 79 -S ses
.PHONY: format

publish: dist
	poetry publish --build
.PHONY: publish
