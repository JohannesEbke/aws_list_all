FROM python:3.9-slim

WORKDIR /app
COPY . /app
RUN python setup.py install

ENTRYPOINT ["aws_list_all"]
CMD ["--help"]