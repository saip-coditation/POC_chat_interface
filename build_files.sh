# build_files.sh (updated for Vercel Root)
# Install dependencies
python3 -m pip install -r backend/requirements.txt --break-system-packages

# Create output directory explicitly
mkdir -p staticfiles_build

# Collect static files from Django (admin, rest_framework, etc.)
python3 backend/manage.py collectstatic --noinput --clear

# Copy Frontend Assets to output directory (so Vercel serves them)
cp index.html staticfiles_build/
cp -r css staticfiles_build/
cp -r js staticfiles_build/
# Check if assets dir exists before copying to avoid error
if [ -d "assets" ]; then
  cp -r assets staticfiles_build/
fi

# Debug: List content to confirm it exists
echo "Build Output Content:"
ls -la staticfiles_build
