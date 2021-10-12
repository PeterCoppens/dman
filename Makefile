all : develop clean
.PHONY: all


install :
	python setup.py install
.PHONY: install

develop :
	python setup.py develop
.PHONY: develop

clean :
	python setup.py clean
.PHONY: clean

sync :
	pipenv lock -r > requirements.txt
.PHONY: sync