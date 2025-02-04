FROM python:alpine3.7

ARG AWS_ACCESS_KEY_ID
ARG AWS_SECRET_ACCESS_KEY

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY . /app
WORKDIR /app
 
RUN pip install aws-list-all
RUN aws-list-all query --region eu-west-1 --service ec2 --directory ./data/