.PHONY: run test deb

run:
	python3 -m moah_launcher

test:
	QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v

deb:
	./packaging/build-deb.sh
