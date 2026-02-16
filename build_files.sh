# Build script starting
echo "Build script starting..."
echo "Current directory: $(pwd)"

# Create output directory immediately
mkdir -p staticfiles_build
echo "Created staticfiles_build directory"

# Install dependencies
echo "Installing dependencies..."
python3 -m pip install -r backend/requirements.txt --break-system-packages

# Collect static files
echo "Collecting static files..."
python3 backend/manage.py collectstatic --noinput --clear

# Copy Frontend Assets
echo "Copying frontend assets..."
cp index.html staticfiles_build/
cp -r css staticfiles_build/
cp -r js staticfiles_build/

if [ -d "assets" ]; then
  cp -r assets staticfiles_build/
fi

# Debug output
echo "Build finished. Content of staticfiles_build:"
ls -la staticfiles_build
