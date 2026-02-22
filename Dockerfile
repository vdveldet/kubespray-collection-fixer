FROM python:3.11-slim


WORKDIR /app

# Install system dependencies
RUN apt-get update \
	&& apt-get install -y --no-install-recommends rsync git \
	&& rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

# Copy scripts
COPY app/* ./

# copy templates directory
COPY templates ./templates

# Set permissions for scripts
RUN chmod +x fix_galaxy.py fix_role_meta.py fix_role_name.py fix_role_readme.py fix_playbooks.py fix_docs.py push_to_galaxy.py build.py  

VOLUME /data

# # Default command
ENTRYPOINT ["python3", "build.py"]
