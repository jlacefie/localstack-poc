.PHONY: start stop deploy test clean logs

ENV ?= .env.localstack

start:
	localstack start -d
	localstack wait -t 60
	@echo "LocalStack is ready at http://localhost:4566"

stop:
	localstack stop

deploy:
	bash -c 'source $(ENV) && python3 deploy.py'

test:
	bash -c 'source $(ENV) && python3 test_upload.py'

logs:
	localstack logs --tail 100

clean:
	localstack stop
	@echo "LocalStack stopped"
