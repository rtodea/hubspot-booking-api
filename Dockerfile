# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable for the API key (it should be passed during runtime)
ENV HUBSPOT_API_KEY=""

# Run uvicorn when the container launches
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]