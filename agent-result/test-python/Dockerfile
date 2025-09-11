FROM python:3.11-slim

WORKDIR /app
RUN git clone https://github.com/pytest-dev/pytest.git .
RUN pip install -e .
RUN pytest tests/

CMD ["/bin/bash"]