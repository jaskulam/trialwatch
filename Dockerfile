FROM public.ecr.aws/lambda/python:3.12

# Install dependencies
RUN pip install --no-cache-dir \
    playwright==1.44.0 \
    boto3 \
    python-dotenv \
    tenacity \
    pendulum \
 && playwright install chromium

# Copy application code
COPY ctis_harvester.py ./
COPY lambda_handler.py ./

# Set the CMD to your handler
CMD ["lambda_handler.lambda_handler"]
