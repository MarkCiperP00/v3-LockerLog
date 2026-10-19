# config.py
import os
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")
DB = dict(host="localhost", user="root", password=os.environ.get("DB_PASSWORD", ""),
          database="lockerlog")
