FROM python:3.11-slim

WORKDIR /app

# Install Flask
RUN pip install --no-cache-dir Flask Werkzeug -i https://mirrors.aliyun.com/pypi/simple

# Create directories
RUN mkdir -p /app/collected_data /app/payloads

# Copy server code
COPY server.py .

# Copy HTML pages (from html_server directory)
COPY html_pages /app/html_pages

# Copy payload scripts (from attacker_server directory)
COPY payloads /app/payloads

# Expose both ports
EXPOSE 8080 8081

# Run the server
CMD ["python", "server.py"]
