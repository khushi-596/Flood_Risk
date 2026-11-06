.PHONY: up down restart test test-backend test-contract test-load data clean

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

test-contract:
	pytest services/api/tests/test_contract.py -v

test-load:
	locust -f tests/load/locustfile.py --host http://localhost:8000 --headless -u 10 -r 2 --run-time 15s

data:
	python -m pipelines.load_segments
	python -m pipelines.seed_fake_reports
	python -m pipelines.calibrate_weights
	python -m pipelines.data_quality_report
