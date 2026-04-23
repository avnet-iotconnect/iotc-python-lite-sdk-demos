FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/ml/code

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install -r requirements.txt

COPY model.py train.py ./

# SageMaker launches training containers with a "train" argument. The script
# ignores unknown arguments, so a direct Python entrypoint is sufficient here.
ENTRYPOINT ["python", "/opt/ml/code/train.py"]
