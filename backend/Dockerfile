# 1. Use a lightweight version of Python as a base
FROM python:3.10-slim

# 2. Prevent Python from writing pyc files to disc (equivalent to python -B option)
ENV PYTHONDONTWRITEBYTECODE=1
# 3. Prevent Python from buffering stdout and stderr (equivalent to python -u option)
ENV PYTHONUNBUFFERED=1

# 4. Install system dependencies required for OpenCV and MediaPipe
# This is the crucial step that fixes the "It works on my machine" problem!
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 5. Set the working directory in the container
WORKDIR /app

# 6. Copy the requirements file into the container
COPY requirements.txt .

# 7. Install the python libraries
RUN pip install --no-cache-dir -r requirements.txt

# 8. Copy the rest of your application code
COPY . .

# 9. Expose the port your app runs on (Standard is 5000 for Flask, 8000 for FastAPI)
EXPOSE 8000

# 10. The command to run your app
# IMPORTANT: Change 'app.py' to whatever your main python file is named!
CMD ["python", "server.py"]