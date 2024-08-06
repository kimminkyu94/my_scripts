# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Install git, ffmpeg, and locales
RUN apt-get update && apt-get install -y git ffmpeg locales

# Generate and set UTF-8 locale for Korean
RUN locale-gen ko_KR.UTF-8
ENV LANG ko_KR.UTF-8
ENV LANGUAGE ko_KR:ko
ENV LC_ALL ko_KR.UTF-8

# Install the required packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container
COPY . .

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable
ENV PORT 8080

# Run make_subtitle.py when the container launches
CMD ["uvicorn", "make_subtitle:app", "--host", "0.0.0.0", "--port", "8080"]
