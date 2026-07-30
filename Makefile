SCHEDULE_URL := https://404.notrollsallowed.com/schedule.csv

.PHONY: download

download:
	curl -fsSL $(SCHEDULE_URL) -o presentations.csv
