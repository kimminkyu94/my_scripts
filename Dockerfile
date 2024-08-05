# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install git and ffmpeg
RUN apt-get update && apt-get install -y git ffmpeg

# Install the required packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container
COPY . .

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable
ENV NAME World

# Run make_subtitle.py when the container launches
CMD ["uvicorn", "make_subtitle:app", "--host", "0.0.0.0", "--port", "8080"]
