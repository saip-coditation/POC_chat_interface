# build_files.sh (updated for Vercel Root)
python3 -m pip install -r backend/requirements.txt --break-system-packages
python3 backend/manage.py collectstatic --noinput --clear
