$env:TESTING="1"
pytest tests/e2e -v | Tee-Object -FilePath e2e_tests_execution_log.txt
