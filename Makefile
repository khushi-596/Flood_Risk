.PHONY: up down restart test test-backend data clean

up:
	docker compose up --build

down:
	docker compose down

restart:
	docker compose down
	docker compose up --build

test: test-backend

test-backend:
	pytest services/api/tests

data:
	python -m pipelines.load_segments
	python -m pipelines.seed_fake_reports
	python -m pipelines.calibrate_weights
	python -m pipelines.data_quality_report
